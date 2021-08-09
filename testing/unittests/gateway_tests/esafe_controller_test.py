# Copyright (C) 2021 OpenMotics BV
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
eSafe controller tests
"""


from __future__ import absolute_import
import unittest

import mock
from mock import call
import six

from gateway.apartment_controller import ApartmentController
from gateway.authentication_controller import AuthenticationController, TokenStore
from gateway.dto import MailBoxDTO, ParcelBoxDTO, DoorbellDTO
from gateway.esafe_controller import EsafeController
from gateway.delivery_controller import DeliveryController
from gateway.pubsub import PubSub
from gateway.rfid_controller import RfidController
from gateway.user_controller import UserController, AuthenticationToken
from ioc import SetTestMode, SetUpTestInjections


try:
    import rebus
    from rebus import RebusComponentEsafeLock, RebusComponentEsafeEightChannelOutput, RebusComponentEsafeCollector
    from rebus.general.enums import EsafeBoxType, EsafeBoxSize
except ImportError:
    pass


@unittest.skipIf(six.PY2, "Not running when in py2")
class EsafeControllerTest(unittest.TestCase):
    """ Tests for EsafeController. """

    @classmethod
    def setUpClass(cls):
        SetTestMode()

    def setUp(self):
        self.pubsub = PubSub()
        SetUpTestInjections(pubsub=self.pubsub)
        self.apartment_controller = mock.Mock(ApartmentController())
        # Set custom return values for apartments
        self.apartment_controller.load_apartment_by_doorbell_id.return_value = None
        self.apartment_controller.load_apartment_by_mailbox_id.return_value = None
        SetUpTestInjections(apartment_controller=self.apartment_controller)
        SetUpTestInjections(token_timeout=3)
        self.token_store = TokenStore(token_timeout=3)
        SetUpTestInjections(token_store=self.token_store)
        self.rfid_controller = mock.Mock(RfidController)
        self.auth_controller = AuthenticationController(token_timeout=3, token_store=self.token_store, rfid_controller=self.rfid_controller)
        SetUpTestInjections(authentication_controller=self.auth_controller)
        SetUpTestInjections(config={'username': 'test', 'password': 'test'})
        self.user_controller = mock.Mock(UserController)
        SetUpTestInjections(user_controller=self.user_controller)
        self.delivery_controller = mock.Mock(DeliveryController)
        SetUpTestInjections(delivery_controller=self.delivery_controller)
        SetUpTestInjections(rebus_device='TEST_DEVICE')
        self.esafe_controller = EsafeController()
        self.delivery_controller.set_esafe_controller(self.esafe_controller)
        self.rebus = mock.Mock()

        # Set the esafe controller in a ready to use state:
        self.esafe_controller.done_discovering = True
        self.esafe_controller.devices = {
            0: RebusComponentEsafeCollector(None, [0], None, None, None, None),
            16: RebusComponentEsafeEightChannelOutput(None, [1, 0], None, None, None, None),
            32: RebusComponentEsafeLock(None, [2, 0], EsafeBoxType.MAILBOX, EsafeBoxSize.S, None, None, None, None),
            48: RebusComponentEsafeLock(None, [3, 0], EsafeBoxType.MAILBOX, EsafeBoxSize.M, None, None, None, None),
            64: RebusComponentEsafeLock(None, [4, 0], EsafeBoxType.PARCELBOX, EsafeBoxSize.S, None, None, None, None),
            80: RebusComponentEsafeLock(None, [5, 0], EsafeBoxType.PARCELBOX, EsafeBoxSize.M, None, None, None, None),
            128: RebusComponentEsafeLock(None, [8, 0], EsafeBoxType.PARCELBOX, EsafeBoxSize.XL, None, None, None, None)
        }
        # mock all existing functions of the components
        for device in self.esafe_controller.devices.values():
            if isinstance(device, RebusComponentEsafeLock):
                # Get lock status
                get_lock_status_mock = mock.Mock()
                get_lock_status_mock.return_value = False
                device.get_lock_status = get_lock_status_mock
                # open lock
                device.open_lock = lambda: True
        self.esafe_controller.rebus_device = self.rebus

    def tearDown(self):
        pass

    def test_get_mailboxes(self):
        """ Test the get mailboxes functionality """
        result = self.esafe_controller.get_mailboxes()
        self.assertEqual(len(result), 2)

        result = self.esafe_controller.get_mailboxes(32)
        self.assertEqual(len(result), 1)
        self.assertEqual([self.esafe_controller._rebus_mailbox_to_dto(self.esafe_controller.devices[32])], result)

        result = self.esafe_controller.get_mailboxes(64)
        self.assertEqual(len(result), 0)  # Should be zero, id 64 is not a mailbox

    def test_get_parcelboxes(self):
        """ Test the get mailboxes functionality """
        result = self.esafe_controller.get_parcelboxes()
        self.assertEqual(len(result), 3)

        result = self.esafe_controller.get_parcelboxes(64)
        self.assertEqual(len(result), 1)
        self.assertEqual([self.esafe_controller._rebus_parcelbox_to_dto(self.esafe_controller.devices[64])], result)

        result = self.esafe_controller.get_parcelboxes(32)
        self.assertEqual(len(result), 0)  # Should be zero, id 32 is not a parcelbox

        result = self.esafe_controller.get_parcelboxes(size='m')
        self.assertEqual(len(result), 1)
        self.assertEqual([self.esafe_controller._rebus_parcelbox_to_dto(self.esafe_controller.devices[80])], result)

        # Test case insensitive
        result = self.esafe_controller.get_parcelboxes(size='M')
        self.assertEqual(len(result), 1)
        self.assertEqual([self.esafe_controller._rebus_parcelbox_to_dto(self.esafe_controller.devices[80])], result)

        with mock.patch.object(self.delivery_controller, 'parcel_id_available') as parcel_available_func:
            # Setting the return values for the parcel available function. This will filter out only the second parcelbox since a dictionary is ordered.
            parcel_available_func.side_effect = [False, True, False, True, True]  # Fist 3 for looping over all the parcelboxes, then 1 for serializing the object, and one for serializing it again for testing the result
            result = self.esafe_controller.get_parcelboxes(available=True)
            self.assertEqual(len(result), 1)
            self.assertEqual([self.esafe_controller._rebus_parcelbox_to_dto(self.esafe_controller.devices[80])], result)

    def test_open_box(self):
        id_to_open = 64
        device = self.esafe_controller.devices[id_to_open]
        open_lock_mock = mock.Mock()
        open_lock_mock.return_value = True
        device.open_lock = open_lock_mock

        result = self.esafe_controller.open_box(id_to_open)
        open_lock_mock.assert_called_once()  # Assert that this one specific mock is called, not any of the other devices open functions
        self.assertEqual(self.esafe_controller._rebus_parcelbox_to_dto(self.esafe_controller.devices[id_to_open]), result)

        with self.assertRaises(ValueError):
            result = self.esafe_controller.open_box(37)

    def test_get_doorbells(self):
        result = self.esafe_controller.get_doorbells()
        self.assertEqual(len(result), 8)  # one output module should produce 8 doorbells
        doorbells = [DoorbellDTO(doorbell_id, label=str(doorbell_id), apartment=None) for doorbell_id in range(17, 25)]
        self.assertEqual(result, doorbells)

    def test_ring_doorbell(self):
        set_output_mock = mock.Mock()
        set_output_mock.return_value = True  # Always send true as success feedback
        device = self.esafe_controller.devices[16]  # Get the doorbell device
        device.set_output = set_output_mock

        self.esafe_controller.ring_doorbell(17)
        set_output_mock.assert_has_calls([call(1, True), call(1, False)], any_order=False)
        self.assertEqual(set_output_mock.call_count, 2)

        set_output_mock.reset_mock()

        self.esafe_controller.ring_doorbell(24)
        set_output_mock.assert_has_calls([call(8, True), call(8, False)], any_order=False)
        self.assertEqual(set_output_mock.call_count, 2)

        with self.assertRaises(ValueError):
            self.esafe_controller.ring_doorbell(37)
