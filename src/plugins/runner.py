from __future__ import absolute_import

import logging
import os
import subprocess
import sys
import time
import traceback
from threading import Lock, Thread

import cherrypy
import six
import ujson as json
from six.moves.queue import Empty, Full, Queue

import constants

from gateway.daemon_thread import BaseThread
from platform_utils import System
from toolbox import PluginIPCReader, PluginIPCWriter
from plugin_runtime.base import PluginWebRequest, PluginWebResponse

if False:  # MYPY
    from typing import Any, Dict, Callable, List, Optional, AnyStr
    from gateway.webservice import WebInterface

logger_ = logging.getLogger(__name__)

class Service(object):
    def __init__(self, runner, webinterface):
        # type: (PluginRunner, WebInterface) -> None
        self.runner = runner
        # Set the user controller, required to check the auth token
        self._user_controller = webinterface._user_controller

    def _cp_dispatch(self, vpath):
        # type: (List[str]) -> Any
        request = cherrypy.request
        response = cherrypy.response
        path = '/'.join(vpath)
        method = vpath[0]
        # Clear vpath completely, The rest is not needed anymore
        # The complete path is stored in the path variable
        # This is needed to not call this function recursively until this variable is empty
        while len(vpath) > 0:
            vpath.pop(0)
        for exposed in self.runner._exposes:
            if exposed['name'] == method:
                request.params['method'] = method
                if exposed['version'] == 1:
                    response.headers['Content-Type'] = exposed['content_type']
                # Creating the plugin web request object here, since
                # we have the path variable in this function scope
                # Body is also empty since this is passed in the params as 'request_body'
                # This is parsed out of the request in the index function below
                request.params['plugin_web_request'] = PluginWebRequest(
                    method=request.method,
                    body=None,
                    headers=request.headers,
                    path=path,
                    version=exposed['version']
                )
                if exposed['auth'] is True:
                    request.hooks.attach('before_handler', cherrypy.tools.authenticated.callable)
                request.hooks.attach('before_handler', cherrypy.tools.params.callable)
                return self
        return None

    @cherrypy.expose
    def index(self, method, plugin_web_request, *args, **kwargs):
        # type: (str, PluginWebRequest, Any, Any) -> Optional[AnyStr]
        try:
            # This has been placed under the 'request_body' in the webservice.py file
            # Here it is read out when necessary and put in the PluginWebRequest object at the correct place
            if 'request_body' in kwargs:
                plugin_web_request.body = kwargs['request_body']
                del kwargs['request_body']
            # Embed the params that where given with the call into the PluginWebResponse object and pass it as one object
            plugin_web_request.params = kwargs
            kwargs = {'plugin_web_request': plugin_web_request.serialize()}

            # Perform the request with the set PluginWebRequest object
            contents = self.runner.request(method, args=args, kwargs=kwargs)

            # Deserialize the response contents to a PluginWebResponse object
            plugin_response = PluginWebResponse.deserialize(contents)
            # Only read out all the data from the PluginWebResponse when the version is higher than 1
            # otherwise, let cherrypy figure out how to return it to keep it similar to the previous implementation
            if plugin_response.version > 1:
                cp_response = cherrypy.response
                for key in plugin_response.headers.keys():
                    cp_response.headers[key] = plugin_response.headers[key]
                cp_response.status = plugin_response.status_code
            if plugin_response.body is not None:
                return plugin_response.body.encode()
            else:
                return None
        except Exception as ex:
            self.runner._logger('Exception when dispatching API call ({}): {}'.format(plugin_web_request.path, ex))
            cherrypy.response.headers["Content-Type"] = "application/json"
            cherrypy.response.status = 500
            contents = json.dumps({"success": False, "msg": str(ex)})
            return contents.encode()


class PluginRunner(object):
    class State(object):
        RUNNING = 'RUNNING'
        STOPPED = 'STOPPED'

    def __init__(self, name, runtime_path, plugin_path, logger, command_timeout=5.0, state_callback=None):
        self.runtime_path = runtime_path
        self.plugin_path = plugin_path
        self.command_timeout = command_timeout

        self._logger = logger
        self._cid = 0
        self._proc = None  # type: Optional[subprocess.Popen[bytes]]
        self._running = False
        self._process_running = False
        self._command_lock = Lock()
        self._response_queue = Queue()  # type: Queue[Dict[str,Any]]
        self._writer = None  # type: Optional[PluginIPCWriter]
        self._reader = None  # type: Optional[PluginIPCReader]
        self._state_callback = state_callback  # type: Optional[Callable[[str, str], None]]

        self.name = name
        self.version = None
        self.interfaces = None

        self._decorators_in_use = {}
        self._exposes = []
        self._metric_collectors = []
        self._metric_receivers = []

        self._async_command_thread = None
        self._async_command_queue = None  # type: Optional[Queue[Optional[Dict[str, Any]]]]

        self._commands_executed = 0
        self._commands_failed = 0

        self.__collector_runs = {}  # type: Dict[str,float]

    def start(self):
        # type: () -> None
        if self._running:
            raise Exception('PluginRunner is already running')

        self.logger('[Runner] Starting')

        python_executable = sys.executable
        if python_executable is None or len(python_executable) == 0:
            python_executable = '/usr/bin/python'

        self._proc = subprocess.Popen([python_executable, 'runtime.py', 'start_plugin', self.plugin_path],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
                                      cwd=self.runtime_path, close_fds=True)
        assert self._proc.stdout, 'Plugin stdout not available'
        self._process_running = True

        self._commands_executed = 0
        self._commands_failed = 0

        assert self._proc.stdin, 'Plugin stdin not defined'
        self._writer = PluginIPCWriter(stream=self._proc.stdin)
        self._reader = PluginIPCReader(stream=self._proc.stdout,
                                       logger=lambda message, ex: self.logger('{0}: {1}'.format(message, ex)),
                                       command_receiver=self._process_command,
                                       name=self.name)
        self._reader.start()

        start_out = self._do_command('start', timeout=180)
        self.name = start_out['name']
        self.version = start_out['version']
        self.interfaces = start_out['interfaces']

        self._decorators_in_use = start_out['decorators']
        self._exposes = start_out['exposes']
        self._metric_collectors = start_out['metric_collectors']
        self._metric_receivers = start_out['metric_receivers']

        exception = start_out.get('exception')
        if exception is not None:
            raise RuntimeError(exception)

        self._async_command_queue = Queue(1000)
        self._async_command_thread = BaseThread(name='plugincmd{0}'.format(self.plugin_path),
                                                target=self._perform_async_commands)
        self._async_command_thread.daemon = True
        self._async_command_thread.start()

        self._running = True
        if self._state_callback is not None:
            self._state_callback(self.name, PluginRunner.State.RUNNING)
        self.logger('[Runner] Started')

    def logger(self, message):
        # type: (str) -> None
        self._logger(message)
        logger_.info('Plugin {0} - {1}'.format(self.name, message))

    def get_webservice(self, webinterface):
        # type: (WebInterface) -> Service
        return Service(self, webinterface)

    def is_running(self):
        # type: () -> bool
        return self._running

    def stop(self):
        # type: () -> None
        if self._process_running:
            self._running = False

            self.logger('[Runner] Sending stop command')
            try:
                self._do_command('stop')
            except Exception as exception:
                self.logger('[Runner] Exception during stopping plugin: {0}'.format(exception))
            time.sleep(0.1)

            if self._reader:
                self._reader.stop()
            self._process_running = False
            if self._async_command_queue is not None:
                self._async_command_queue.put(None)  # Triggers an abort on the read thread

            if self._proc and self._proc.poll() is None:
                self.logger('[Runner] Terminating process')
                try:
                    self._proc.terminate()
                except Exception as exception:
                    self.logger('[Runner] Exception during terminating plugin: {0}'.format(exception))
                time.sleep(0.5)

                if self._proc.poll() is None:
                    self.logger('[Runner] Killing process')
                    try:
                        self._proc.kill()
                    except Exception as exception:
                        self.logger('[Runner] Exception during killing plugin: {0}'.format(exception))

            if self._state_callback is not None:
                self._state_callback(self.name, PluginRunner.State.STOPPED)
            self.logger('[Runner] Stopped')

    def process_input_status(self, data, action_version=1):
        if action_version in [1, 2]:
            if action_version == 1:
                payload = {'status': data}
            else:
                event_json = data.serialize()
                payload = {'event': event_json}
            self._do_async(action='input_status', payload=payload, should_filter=True, action_version=action_version)
        else:
            self.logger('Input status version {} not supported.'.format(action_version))

    def process_output_status(self, data, action_version=1):
        if action_version in [1, 2]:
            if action_version == 1:
                payload = {'status': data}
            else:
                event_json = data.serialize()
                payload = {'event': event_json}
            self._do_async(action='output_status', payload=payload, should_filter=True, action_version=action_version)
        else:
            self.logger('Output status version {} not supported.'.format(action_version))

    def process_shutter_status(self, data, action_version=1):
        if action_version in [1, 2, 3]:
            if action_version == 1:
                payload = {'status': data}
            elif action_version == 2:
                status, detail = data
                payload = {'status': {'status': status, 'detail': detail}}
            else:
                event_json = data.serialize()
                payload = {'event': event_json}
            self._do_async(action='shutter_status', payload=payload, should_filter=True, action_version=action_version)
        else:
            self.logger('Shutter status version {} not supported.'.format(action_version))

    def process_ventilation_status(self, data, action_version=1):
        if action_version in [1]:
            event_json = data.serialize()
            payload = {'event': event_json}
            self._do_async(action='ventilation_status', payload=payload, should_filter=True, action_version=action_version)
        else:
            self.logger('Ventilation status version {} not supported.'.format(action_version))

    def process_thermostat_status(self, data, action_version=1):
        if action_version in [1]:
            event_json = data.serialize()
            payload = {'event': event_json}
            self._do_async(action='thermostat_status', payload=payload, should_filter=True, action_version=action_version)
        else:
            self.logger('Thermostat status version {} not supported.'.format(action_version))

    def process_thermostat_group_status(self, data, action_version=1):
        if action_version in [1]:
            event_json = data.serialize()
            payload = {'event': event_json}
            self._do_async(action='thermostat_group_status', payload=payload, should_filter=True, action_version=action_version)
        else:
            self.logger('Thermostat group status version {} not supported.'.format(action_version))

    def process_event(self, code):
        self._do_async('receive_events', {'code': code}, should_filter=True)

    def collect_metrics(self):
        for mc in self._metric_collectors:
            try:
                now = time.time()
                (name, interval) = (mc['name'], mc['interval'])

                if self.__collector_runs.get(name, 0.0) < now - interval:
                    self.__collector_runs[name] = now
                    metrics = self._do_command('collect_metrics', {'name': name})['metrics']
                    for metric in metrics:
                        if metric is None:
                            continue
                        metric['source'] = self.name
                        yield metric
            except Exception as exception:
                self.logger('[Runner] Exception while collecting metrics {0}: {1}'.format(exception, traceback.format_exc()))

    def get_metric_receivers(self):
        return self._metric_receivers

    def distribute_metrics(self, method, metrics):
        self._do_async('distribute_metrics', {'name': method,
                                              'metrics': metrics})

    def get_metric_definitions(self):
        return self._do_command('get_metric_definitions')['metric_definitions']

    def request(self, method, args=None, kwargs=None):
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        ret = self._do_command('request', {'method': method,
                                           'args': args,
                                           'kwargs': kwargs})
        if ret['success']:
            return ret['response']
        elif 'stacktrace' in ret:
            raise Exception('{0}: {1}'.format(ret['exception'], ret['stacktrace']))
        raise Exception(ret['exception'])

    def remove_callback(self):
        # type: () -> None
        self._do_command('remove_callback')

    def _process_command(self, response):
        # type: (Dict[str,Any]) -> None
        if not self._process_running:
            return
        assert self._proc, 'Plugin process not defined'
        exit_code = self._proc.poll()
        if exit_code is not None:
            self.logger('[Runner] Stopped with exit code {0}'.format(exit_code))
            self._process_running = False
            return

        if response['cid'] == 0:
            self._handle_async_response(response)
        elif response['cid'] == self._cid:
            self._response_queue.put(response)
        else:
            self.logger('[Runner] Received message with unknown cid: {0}'.format(response))

    def _handle_async_response(self, response):
        # type: (Dict[str,Any]) -> None
        if response['action'] == 'logs':
            self.logger(response['logs'])
        else:
            self.logger('[Runner] Unkown async message: {0}'.format(response))

    def _do_async(self, action, payload, should_filter=False, action_version=1):
        # type: (str, Dict[str,Any], bool, int) -> None
        has_receiver = False
        for decorator_name, decorator_versions in six.iteritems(self._decorators_in_use):
            # the action version is linked to a specific decorator version
            has_receiver |= (action == decorator_name and action_version in decorator_versions)
        if not self._process_running or (should_filter and not has_receiver):
            return
        try:
            assert self._async_command_queue, 'Command Queue not defined'
            self._async_command_queue.put({'action': action, 'payload': payload, 'action_version': action_version}, block=False)
        except Full:
            self.logger('Async action cannot be queued, queue is full')

    def _perform_async_commands(self):
        # type: () -> None
        while self._process_running:
            try:
                # Give it a timeout in order to check whether the plugin is not stopped.
                assert self._async_command_queue, 'Command Queue not defined'
                command = self._async_command_queue.get(block=True, timeout=10)
                if command is None:
                    continue  # Used to exit this thread
                self._do_command(command['action'], payload=command['payload'], action_version=command['action_version'])
            except Empty:
                self._do_async('ping', {})
            except Exception as exception:
                self.logger('[Runner] Failed to perform async command: {0}'.format(exception))

    def _do_command(self, action, payload=None, timeout=None, action_version=1):
        # type: (str, Dict[str,Any], Optional[float], int) -> Dict[str,Any]
        if payload is None:
            payload = {}
        self._commands_executed += 1
        if timeout is None:
            timeout = self.command_timeout

        if not self._process_running:
            raise Exception('Plugin was stopped')

        with self._command_lock:
            try:
                command = self._create_command(action, payload, action_version)
                assert self._writer, 'Plugin stdin not defined'
                self._writer.write(command)
            except Exception:
                self._commands_failed += 1
                raise

            try:
                response = self._response_queue.get(block=True, timeout=timeout)
                while response['cid'] != self._cid:
                    response = self._response_queue.get(block=False)
                exception = response.get('_exception')
                if exception is not None:
                    raise RuntimeError(exception)
                return response
            except Empty:
                metadata = ''
                if action == 'request':
                    metadata = ' {0}'.format(payload['method'])
                if self._running:
                    self.logger('[Runner] No response within {0}s ({1}{2})'.format(timeout, action, metadata))
                self._commands_failed += 1
                raise Exception('Plugin did not respond')

    def _create_command(self, action, payload=None, action_version=1):
        # type: (str, Dict[str,Any], int) -> Dict[str,Any]
        if payload is None:
            payload = {}
        self._cid += 1
        command = {'cid': self._cid,
                   'action': action,
                   'action_version': action_version}
        command.update(payload)
        return command

    def error_score(self):
        # type: () -> float
        if self._commands_executed == 0:
            return 0.0
        else:
            score = float(self._commands_failed) / self._commands_executed
            self._commands_failed = 0
            self._commands_executed = 0
            return score

    def get_queue_length(self):
        # type: () -> int
        if self._async_command_queue is None:
            return 0
        return self._async_command_queue.qsize()


class RunnerWatchdog(object):
    def __init__(self, plugin_runner, threshold=0.25, check_interval=60):
        # type: (PluginRunner, float, int) -> None
        self._plugin_runner = plugin_runner
        self._threshold = threshold
        self._check_interval = check_interval
        self._stopped = False
        self._thread = None  # type: Optional[Thread]

    def stop(self):
        # type: () -> None
        self._stopped = True
        if self._thread is not None:
            self._thread.join()

    def start(self):
        # type: () -> bool
        self._stopped = False
        success = self._run()  # Initial sync run
        self._thread = BaseThread(name='watchdog{0}'.format(self._plugin_runner.name), target=self.run)
        self._thread.daemon = True
        self._thread.start()
        return success

    def run(self):
        self._plugin_runner.logger('[Watchdog] Started')
        while not self._stopped:
            self._run()
            for _ in range(self._check_interval * 2):
                # Small sleep cycles, to be able to finish the thread quickly
                time.sleep(0.5)
                if self._stopped:
                    break
        self._plugin_runner.logger('[Watchdog] Stopped')

    def _run(self):
        starting = False
        try:
            score = self._plugin_runner.error_score()
            if score > self._threshold:
                starting = False
                self._plugin_runner.logger('[Watchdog] Stopping unhealthy runner')
                self._plugin_runner.stop()
            if not self._plugin_runner.is_running():
                starting = True
                self._plugin_runner.logger('[Watchdog] Starting stopped runner')
                self._plugin_runner.start()
            return True
        except Exception as e:
            self._plugin_runner.logger('[Watchdog] Exception while {0} runner: {1}'.format(
                'starting' if starting else 'stopping', e
            ))
            try:
                self._plugin_runner.logger('[Watchdog] Stopping failed runner')
                self._plugin_runner.stop()
            except Exception as se:
                self._plugin_runner.logger('[Watchdog] Exception while stopping failed runner: {0}'.format(se))
            return False
