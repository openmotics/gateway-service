import time
import logging
from ioc import Injectable, Singleton, Inject, INJECTED
from threading import Thread
from bus.om_bus_events import OMBusEvents

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

        self._thread = Thread(target=self.led_driver)
        self._thread.setName("Serial led driver thread")
        self._thread.daemon = True

    def start(self):
        logger.info("Starting commmunications led controller...")
        self._thread.start()
        logger.info("Starting commmunications led controller... Done")

    def led_driver(self):
        master_stats = (0, 0)
        power_stats = (0, 0)

        while True:
            stats = self._master_controller.get_communication_statistics()
            new_master_stats = (stats['bytes_read'], stats['bytes_written'])

            if self._power_communicator is None:
                new_power_stats = (0, 0)
            else:
                stats = self._power_communicator.get_communication_statistics()
                new_power_stats = (stats['bytes_read'], stats['bytes_written'])

            if master_stats[0] != new_master_stats[0] or master_stats[1] != new_master_stats[1]:
                self._message_client.send_event(OMBusEvents.SERIAL_ACTIVITY, 5)
            if power_stats[0] != new_power_stats[0] or power_stats[1] != new_power_stats[1]:
                self._message_client.send_event(OMBusEvents.SERIAL_ACTIVITY, 4)

            master_stats = new_master_stats
            power_stats = new_power_stats
            time.sleep(0.1)
