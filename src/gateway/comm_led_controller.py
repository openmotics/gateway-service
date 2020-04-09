import logging
import time

from bus.om_bus_events import OMBusEvents
from gateway.daemon_thread import DaemonThread
from ioc import INJECTED, Inject, Injectable, Singleton

logger = logging.getLogger("openmotics")


@Injectable.named('communication_led_controller')
@Singleton
class CommunicationLedController(object):

    @Inject
    def __init__(self, master_controller=INJECTED, power_communicator=INJECTED, message_client=INJECTED):
        """
        Blink the serial leds if necessary.
        :type message_client: bus.om_bus_client.MessageClient
        :type master_controller: gateway.hal.master_controller.MasterController
        :type power_communicator: power.power_communicator.PowerCommunicator
        """
        self._master_controller = master_controller
        self._power_communicator = power_communicator
        self._message_client = message_client

        self._master_stats = (0, 0)
        self._power_stats = (0, 0)
        self._thread = DaemonThread(name='CommunicationLedController driver',
                                    target=self.led_driver,
                                    interval=0.1)

    def start(self):
        # type: () -> None
        self._thread.start()

    def stop(self):
        # type: () -> None
        self._thread.stop()

    def led_driver(self):
        # type: () -> None
        stats = self._master_controller.get_communication_statistics()
        new_master_stats = (stats['bytes_read'], stats['bytes_written'])

        if self._power_communicator is None:
            new_power_stats = (0, 0)
        else:
            stats = self._power_communicator.get_communication_statistics()
            new_power_stats = (stats['bytes_read'], stats['bytes_written'])

        if self._master_stats[0] != new_master_stats[0] or self._master_stats[1] != new_master_stats[1]:
            self._message_client.send_event(OMBusEvents.SERIAL_ACTIVITY, 5)
        if self._power_stats[0] != new_power_stats[0] or self._power_stats[1] != new_power_stats[1]:
            self._message_client.send_event(OMBusEvents.SERIAL_ACTIVITY, 4)

        self._master_stats = new_master_stats
        self._power_stats = new_power_stats
