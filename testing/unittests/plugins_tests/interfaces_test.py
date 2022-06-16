# Copyright (C) 2016 OpenMotics BV
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
Tests for plugins.interfaces.
"""

from __future__ import absolute_import
import unittest
from plugin_runtime.base import OMPluginBase, PluginException, om_expose
from plugin_runtime.interfaces import check_interfaces



class CheckInterfacesTest(unittest.TestCase):
    """ Tests for check_interfaces. """

    def test_no_interfaces(self):
        """ Test a plugin without interfaces. """
        _ = self

        class P1(OMPluginBase):
            """ Plugin without interfaces. """
            name = 'P1'
            version = '1.0'
            interfaces = []

        check_interfaces(P1)  # Should not raise exceptions

    def test_wrong_interface_format(self):
        """ Test a plugin with the wrong interface format. """
        class P1(OMPluginBase):
            """ Plugin with invalid interface. """
            name = 'P1'
            version = '1.0'
            interfaces = 'interface1'

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P1)
        self.assertEqual('The interfaces attribute on plugin \'P1\' is not a list.', str(ctx.exception))

        class P2(OMPluginBase):
            """ Plugin with invalid interface. """
            name = 'P2'
            version = '1.0'
            interfaces = ['interface1']

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P2)
        self.assertEqual('Interface \'interface1\' on plugin \'P2\' is not a tuple of (name, version).', str(ctx.exception))

        class P3(OMPluginBase):
            """ Plugin with invalid interface. """
            name = 'P3'
            version = '1.0'
            interfaces = [('interface1',)]

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P3)
        self.assertEqual('Interface \'(\'interface1\',)\' on plugin \'P3\' is not a tuple of (name, version).', str(ctx.exception))

    def test_interface_not_found(self):
        """ Test a plugin with an interface that is not known. """
        class P1(OMPluginBase):
            """ Plugin with unknown interface. """
            name = 'P1'
            version = '1.0'
            interfaces = [('myinterface', '2.0')]

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P1)
        self.assertEqual('Interface \'myinterface\' with version \'2.0\' was not found.', str(ctx.exception))

    def test_missing_method_interface(self):
        """ Test a plugin with a missing method. """
        class P1(OMPluginBase):
            """ Plugin with valid interface and missing methods. """
            name = 'P1'
            version = '1.0'
            interfaces = [('webui', '1.0')]

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P1)
        self.assertEqual('Plugin \'P1\' has no method named \'html_index\'', str(ctx.exception))

    def test_not_a_method(self):
        """ Test where a name of an interface method is used for something else. """
        class P1(OMPluginBase):
            """ Plugin with valid interface and missing methods. """
            name = 'P1'
            version = '1.0'
            interfaces = [('webui', '1.0')]
            html_index = 'hello'

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P1)
        self.assertEqual('Plugin \'P1\' has no method named \'html_index\'', str(ctx.exception))

    def test_not_exposed_interface(self):
        """ Test a non-exposed method on a plugin. """
        class P1(OMPluginBase):
            """ Plugin with valid interface and unexposed methods. """
            name = 'P1'
            version = '1.0'
            interfaces = [('webui', '1.0')]

            def html_index(self):
                _ = self
                return 'hello'

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P1)
        self.assertEqual('Plugin \'P1\' does not expose method \'html_index\'', str(ctx.exception))

    def test_wrong_authentication_interface(self):
        """ Test a plugin with wrong authentication on a method. """
        class P1(OMPluginBase):
            """ Plugin with valid interface and methods without authentication. """
            name = 'P1'
            version = '1.0'
            interfaces = [('webui', '1.0')]

            @om_expose(auth=False)
            def html_index(self):
                return 'hello'

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P1)
        self.assertEqual('Plugin \'P1\': authentication for method \'html_index\' does not match the interface authentication (required).', str(ctx.exception))

    def test_wrong_arguments(self):
        """ Test a plugin with wrong arguments to a method. """
        class P1(OMPluginBase):
            """ Plugin with interface and methods with the wrong arguments. """
            name = 'P1'
            version = '1.0'
            interfaces = [('config', '1.0')]

            @om_expose(auth=True)
            def get_config_description(self):
                """ Method arguments are fine. """
                pass

            @om_expose(auth=True)
            def get_config(self):
                """ Method arguments are fine. """
                pass

            @om_expose(auth=True)
            def set_config(self, test):
                """ Method arguments: expected config instead of test. """
                pass

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P1)
        self.assertEqual('Plugin \'P1\': the arguments for method \'set_config\': [\'test\'] do not match the interface arguments: [\'config\'].', str(ctx.exception))

    def test_missing_self(self):
        """ Test a plugin that is missing 'self' for a method. """
        class P1(OMPluginBase):
            """ Plugin with interface method without self. """
            name = 'P1'
            version = '1.0'
            interfaces = [('webui', '1.0')]

            @om_expose(auth=True)
            def html_index():  # pylint: disable=E0211
                """ Without self. """
                pass

        with self.assertRaises(PluginException) as ctx:
            check_interfaces(P1)
        self.assertEqual('Method \'html_index\' on plugin \'P1\' lacks \'self\' as first argument.', str(ctx.exception))

    def test_ok(self):
        """ Test an interface check that succeeds. """
        _ = self

        class P1(OMPluginBase):
            """ Plugin with multiple interfaces that are well implemented. """
            name = 'P1'
            version = '1.0'
            interfaces = [('config', '1.0'), ('webui', '1.0')]

            @om_expose(auth=True)
            def get_config_description(self):
                """ No implementation. """
                pass

            @om_expose(auth=True)
            def get_config(self):
                """ No implementation. """
                pass

            @om_expose(auth=True)
            def set_config(self, config):
                """ No implementation. """
                pass

            @om_expose(auth=True)
            def html_index(self):
                """ No implementation. """
                pass

        check_interfaces(P1)
