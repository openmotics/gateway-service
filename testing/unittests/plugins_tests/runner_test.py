# Copyright (C) 2019 OpenMotics BV
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Tests for plugin runner
"""

from __future__ import absolute_import
import os
import plugin_runtime
import shutil
import tempfile
import unittest
import xmlrunner
import mock
from plugins.runner import PluginRunner, RunnerWatchdog


class PluginRunnerTest(unittest.TestCase):
    """ Tests for the PluginRunner. """

    PLUGIN_PATH = None
    RUNTIME_PATH = os.path.dirname(plugin_runtime.__file__)

    @classmethod
    def setUpClass(cls):
        cls.RUNTIME_PATH = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        try:
            if cls.PLUGIN_PATH is not None:
                shutil.rmtree(cls.PLUGIN_PATH)
        except Exception:
            pass

    def _log(self, *args, **kwargs):
        print(args)
        print(kwargs)
        _ = self, args, kwargs

    def test_queue_length(self):
        runner = PluginRunner(name='foo',
                              runtime_path=self.RUNTIME_PATH,
                              plugin_path=self.PLUGIN_PATH,
                              logger=self._log)
        self.assertEqual(runner.get_queue_length(), 0)

    def test_watchog_always_stops_runner(self):

        def _set_side_effects(effects):
            error_score.side_effect = effects[0]
            start.side_effect = effects[1]
            stop.side_effect = effects[2]
            is_running.side_effect = effects[3]

        def _reset():
            error_score.reset_mock()
            start.reset_mock()
            stop.reset_mock()
            is_running.reset_mock()

        runner = PluginRunner(name='foo',
                              runtime_path=self.RUNTIME_PATH,
                              plugin_path=self.PLUGIN_PATH,
                              logger=self._log)
        watchdog = RunnerWatchdog(plugin_runner=runner)
        watchdog.logger = self._log
        with mock.patch.object(runner, 'error_score') as error_score, \
                mock.patch.object(runner, 'start') as start, \
                mock.patch.object(runner, 'stop') as stop, \
                mock.patch.object(runner, 'is_running') as is_running:
            for scenario in [{'side_effects': [[0.0], [None], [None], [True]],  # Everything is good
                              'result': True,
                              'calls': [1, 0, 0, 1]},
                             {'side_effects': [[0.0], [None], [None], [False]],  # The runner was not running and is started
                              'result': True,
                              'calls': [1, 1, 0, 1]},
                             {'side_effects': [[1.0], [None], [None], [False]],  # The runner is unhealthy and is stopped, and then started again
                              'result': True,
                              'calls': [1, 1, 1, 1]},
                             {'side_effects': [[RuntimeError()], [None], [None], [False]],  # Exception while requesting score, unhealthy runner is stopped
                              'result': False,
                              'calls': [1, 0, 1, 0]},
                             {'side_effects': [[1.0], [None], [RuntimeError()], [False]],  # Exception while stopping unhealthy runner, failed runner is stopped
                              'result': False,
                              'calls': [1, 0, 2, 0]},
                             {'side_effects': [[0.0], [RuntimeError()], [None], [False]],  # Exception while starting stopped runner, failed runner is stopped
                              'result': False,
                              'calls': [1, 1, 1, 1]},
                             {'side_effects': [[1.0], [None], [RuntimeError(), RuntimeError()], [False]],  # Exception while stopping unhealthy runner, failed runner is stopped. And that stop also fails
                              'result': False,
                              'calls': [1, 0, 2, 0]}]:
                _reset()
                _set_side_effects(scenario['side_effects'])
                result = watchdog._run()
                self.assertEqual(scenario['result'], result)
                for i, _mock in enumerate([error_score, start, stop, is_running]):
                    if scenario['calls'][i] == 0:
                        _mock.assert_not_called()
                    elif scenario['calls'][i] == 1:
                        _mock.assert_called_once()
                    else:
                        self.assertEqual(scenario['calls'][i], _mock.call_count)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='../gw-unit-reports'))
