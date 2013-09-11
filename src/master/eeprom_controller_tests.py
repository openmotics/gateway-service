'''
Tests for the eeprom_controller module.
Created on Sep 2, 2013

@author: fryckbos
'''
import unittest

from eeprom_controller import EepromController, EepromFile, EepromModel, EepromId, EepromString, EepromByte, EepromWord, EepromData, EepromAddress
import master_api


class Model1(EepromModel):
    """ Dummy model with an id. """
    id = EepromId(10)
    name = EepromString(100, lambda id: (1, 2 + id))


class Model2(EepromModel):
    """ Dummy model without an id. """
    name = EepromString(100, (3, 4))


class Model3(EepromModel):
    """ Dummy model with multiple fields. """
    name = EepromString(10, (3, 4))
    link = EepromByte((3, 14))
    out = EepromWord((3, 15))


class Model4(EepromModel):
    """ Dummy model with a dynamic maximum id. """
    id = EepromId(10, address=EepromAddress(0,0,1), multiplier=2)
    name = EepromString(10, lambda id: (1, 2 + id * 10))


def get_eeprom_file_dummy(banks):
    """ Create an EepromFile when the bank data is provided.
    
    @param banks: list of string of bytes.
    """
    def list(data):
        return { "data" : banks[data["bank"]] }
    
    def write(data):
        bank = banks[data["bank"]]
        address = data["address"]
        bytes = data["data"]
        
        for i in range(len(bytes)):
            bank[i + address] = bytes[i]
    
    return EepromFile(MasterCommunicatorDummy(list, write))
    

class EepromControllerTest(unittest.TestCase):
    """ Tests for EepromController. """

    def test_read(self):
        """ Test read. """
        controller = EepromController(get_eeprom_file_dummy([ "\x00" * 256, "\x00" * 2 + "hello" + "\x00" * 249 ]))
        model = controller.read(Model1, 0)
        self.assertEquals(0, model.id)
        self.assertEquals("hello" + "\x00" * 95, model.name)
        
        controller = EepromController(get_eeprom_file_dummy([ "", "", "", "\x00" * 4 + "hello" + "\x00" * 249 ]))
        model = controller.read(Model2)
        self.assertEquals("hello" + "\x00" * 95, model.name)

    def test_read_batch(self):
        """ Test read_batch. """
        controller = EepromController(get_eeprom_file_dummy([ "\x00" * 256, "\x00" * 2 + "hello" + "\x00" * 249 ]))
        
        models = controller.read_batch(Model1, [0,3,8])
        
        self.assertEquals(0, models[0].id)
        self.assertEquals("hello" + "\x00" * 95, models[0].name)
        
        self.assertEquals(3, models[1].id)
        self.assertEquals("lo" + "\x00" * 98, models[1].name)
        
        self.assertEquals(8, models[2].id)
        self.assertEquals("\x00" * 100, models[2].name)        

    def test_read_all_without_id(self):
        """ Test read_all for EepromModel without id. """
        controller = EepromController(get_eeprom_file_dummy([ ]))
        
        try:
            controller.read_all(Model2)
            self.fail('Expected TypeError.')
        except TypeError as e:
            self.assertTrue('id' in str(e))
    
    def test_read_all(self):
        """ Test read_all. """
        controller = EepromController(get_eeprom_file_dummy([ "\x00" * 256, "\x00" * 2 + "hello" + "\x00" * 249 ]))
        models = controller.read_all(Model1)
        
        self.assertEquals(10, len(models))
        self.assertEquals("hello" + "\x00" * 95, models[0].name)
        self.assertEquals("ello" + "\x00" * 96, models[1].name)
        self.assertEquals("llo" + "\x00" * 97, models[2].name)
        self.assertEquals("lo" + "\x00" * 98, models[3].name)
        self.assertEquals("o" + "\x00" * 99, models[4].name)
        self.assertEquals("\x00" * 100, models[5].name)
        self.assertEquals("\x00" * 100, models[6].name)
        self.assertEquals("\x00" * 100, models[7].name)
        self.assertEquals("\x00" * 100, models[8].name)
        self.assertEquals("\x00" * 100, models[9].name)
    
    def test_get_max_id(self):
        """ Test get_max_id. """
        controller = EepromController(get_eeprom_file_dummy([ "\x05" + "\x00" * 254 ]))
        self.assertEquals(10, controller.get_max_id(Model4))
        
        controller = EepromController(get_eeprom_file_dummy([ "\x10" + "\x00" * 254 ]))
        self.assertEquals(32, controller.get_max_id(Model4))

        controller = EepromController(get_eeprom_file_dummy([ ]))
        self.assertEquals(10, controller.get_max_id(Model1))
        
        try:
            controller.get_max_id(Model2)
            self.fail('Expected TypeError.')
        except TypeError as e:
            self.assertTrue('id' in str(e))

    def test_write_one(self):
        """ Test write with one model. """
        controller = EepromController(get_eeprom_file_dummy([ "\x00" * 256, "\x00" * 256, "\x00" * 256, "\x00" * 256 ]))
        controller.write([ Model1(id=1, name="\xff" * 100) ])
        ## TODO Check the result with read
        
    
    def test_write_multiple(self):
        """ Test write with multiple models. """
        controller = EepromController(get_eeprom_file_dummy([ "\x00" * 256, "\x00" * 256, "\x00" * 256, "\x00" * 256 ]))
        controller.write([ Model1(id=1, name="\xff" * 100), Model2(name="\x01"*256) ])
        ## TODO Check the result with read
        


class MasterCommunicatorDummy:
    """ Dummy for the MasterCommunicator. """
    
    def __init__(self, list_function=None, write_function=None):
        self.__list_function = list_function
        self.__write_function = write_function
    
    def do_command(self, cmd, data):
        if cmd == master_api.eeprom_list():
            return self.__list_function(data)
        elif cmd == master_api.write_eeprom():
            return self.__write_function(data)
        else:
            raise Exception("Command %s not found" % cmd)


class EepromFileTest(unittest.TestCase):
    """ Tests for EepromFile. """

    def test_read_one_bank_one_address(self):
        """ Test read from one bank with one address """
        def read(data):
            if data["bank"] == 1:
                return { "data" : "abc" + "\xff" * 200 + "def" + "\xff" * 48 }
            else:
                raise Exception("Wrong page")
        
        file = EepromFile(MasterCommunicatorDummy(read)) 
        address = EepromAddress(1, 0, 3)
        data = file.read([ address ])
        
        self.assertEquals(1, len(data))
        self.assertEquals(address, data[0].address)
        self.assertEquals("abc", data[0].bytes)
    
    def test_read_one_bank_two_addresses(self):
        """ Test read from one bank with two addresses. """
        def read(data):
            if data["bank"] == 1:
                return { "data" : "abc" + "\xff" * 200 + "def" + "\xff" * 48 }
            else:
                raise Exception("Wrong page")
        
        file = EepromFile(MasterCommunicatorDummy(read))
        
        address1 = EepromAddress(1, 2, 10)
        address2 = EepromAddress(1, 203, 4)
        data = file.read([ address1, address2 ])
        
        self.assertEquals(2, len(data))
        
        self.assertEquals(address1, data[0].address)
        self.assertEquals("c" + "\xff" * 9, data[0].bytes)
        
        self.assertEquals(address2, data[1].address)
        self.assertEquals("def\xff", data[1].bytes)
    
    def test_read_multiple_banks(self):
        """ Test read from multiple banks. """
        def read(data):
            if data["bank"] == 1:
                return { "data" : "abc" + "\xff" * 200 + "def" + "\xff" * 48 }
            if data["bank"] == 100:
                return { "data" : "hello" + "\x00" * 100 + "world" + "\x00" * 146 }
            else:
                raise Exception("Wrong page")
        
        file = EepromFile(MasterCommunicatorDummy(read))
        
        address1 = EepromAddress(1, 2, 10)
        address2 = EepromAddress(100, 4, 10)
        address3 = EepromAddress(100, 105, 5)
        data = file.read([ address1, address2, address3 ])
        
        self.assertEquals(3, len(data))
        
        self.assertEquals(address1, data[0].address)
        self.assertEquals("c" + "\xff" * 9, data[0].bytes)
        
        self.assertEquals(address2, data[1].address)
        self.assertEquals("o" + "\x00" * 9, data[1].bytes)
        
        self.assertEquals(address3, data[2].address)
        self.assertEquals("world", data[2].bytes)

    def test_write_single_field(self):
        """ Write a single field to the eeprom file. """
        done = {}
        
        def read(data):
            if data["bank"] == 1:
                done['read1'] =  True
                return { "data" : "\xff" * 256 }
            else:
                raise Exception("Wrong page")
        
        def write(data):
            self.assertEquals(1, data["bank"])
            self.assertEquals(2, data["address"])
            self.assertEquals("abc", data["data"])
            done['write'] = True
        
        mc = MasterCommunicatorDummy(read, write)
        
        file = EepromFile(mc)
        file.write([ EepromData(EepromAddress(1, 2, 3), "abc") ])
        
        self.assertTrue('read1' in done)
        self.assertTrue('write' in done)
    
    def test_write_multiple_fields(self):
        """ Test writing multiple fields to the eeprom file. """
        done = {}
        
        def read(data):
            if data["bank"] == 1:
                done['read1'] =  True
                return { "data" : "\xff" * 256 }
            elif data["bank"] == 2:
                done['read2'] =  True
                return { "data" : "\x00" * 256 }
            else:
                raise Exception("Wrong page")
        
        def write(data):
            if 'write1' not in done:
                done['write1'] = True
                self.assertEquals(1, data["bank"])
                self.assertEquals(2, data["address"])
                self.assertEquals("abc", data["data"])
            elif 'write2' not in done:
                done['write2'] = True
                self.assertEquals(2, data["bank"])
                self.assertEquals(123, data["address"])
                self.assertEquals("More bytes", data["data"])
            elif 'write3' not in done:
                done['write3'] = True
                self.assertEquals(2, data["bank"])
                self.assertEquals(133, data["address"])
                self.assertEquals(" than 10", data["data"])
            else:
                raise Exception("Too many writes")
        
        mc = MasterCommunicatorDummy(read, write)
        
        file = EepromFile(mc)
        file.write([ EepromData(EepromAddress(1, 2, 3), "abc"), 
                     EepromData(EepromAddress(2, 123, 18), "More bytes than 10") ])
        
        self.assertTrue('read1' in done)
        self.assertTrue('read2' in done)
        self.assertTrue('write1' in done)
        self.assertTrue('write2' in done)
        self.assertTrue('write3' in done)
    
    def test_write_multiple_fields_same_batch(self):
        """ Test writing multiple fields to the eeprom file. """
        done = {}
        
        def read(data):
            if data["bank"] == 1:
                done['read'] =  True
                return { "data" : "\xff" * 256 }
            else:
                raise Exception("Wrong page")
        
        def write(data):
            if 'write1' not in done:
                done['write1'] = True
                self.assertEquals(1, data["bank"])
                self.assertEquals(2, data["address"])
                self.assertEquals("abc\xff\xff\xffdefg", data["data"])
            elif 'write2' not in done:
                done['write2'] = True
                self.assertEquals(1, data["bank"])
                self.assertEquals(12, data["address"])
                self.assertEquals("hijklmn", data["data"])
            else:
                raise Exception("Too many writes")
        
        mc = MasterCommunicatorDummy(read, write)
        
        file = EepromFile(mc)
        file.write([ EepromData(EepromAddress(1, 2, 3), "abc"), 
                     EepromData(EepromAddress(1, 8, 11), "defghijklmn") ])
        
        self.assertTrue('read' in done)
        self.assertTrue('write1' in done)
        self.assertTrue('write2' in done)


class EepromModelTest(unittest.TestCase):
    """ Tests for EepromModel. """
    
    def test_get_fields(self):
        """ Test get_fields. """
        fields = Model1.get_fields()
        
        self.assertEquals(1, len(fields))
        self.assertEquals("name", fields[0][0])
        
        fields = Model1.get_fields(include_id=True)
        
        self.assertEquals(2, len(fields))
        self.assertEquals("id", fields[0][0])
        self.assertEquals("name", fields[1][0])
        
    def test_has_id(self):
        """ Test has_id. """
        self.assertTrue(Model1.has_id())
        self.assertFalse(Model2.has_id())
    
    def test_get_name(self):
        """ Test get_name. """
        self.assertEquals("Model1", Model1.get_name())
        self.assertEquals("Model2", Model2.get_name())
    
    def test_check_id(self):
        """ Test check_id. """
        Model1.check_id(0) ## Should just work
        
        try:
            Model1.check_id(100)
            self.fail("Expected TypeError")
        except TypeError as e:
            self.assertTrue("maximum" in str(e))
        
        try:
            Model1.check_id(None)
            self.fail("Expected TypeError")
        except TypeError as e:
            self.assertTrue("id" in str(e))
            
        Model2.check_id(None) ## Should just work    
        
        try:
            Model2.check_id(0)
            self.fail("Expected TypeError")
        except TypeError as e:
            self.assertTrue("id" in str(e))
        
    def test_to_dict(self):
        """ Test to_dict. """
        self.assertEquals({'id':1, 'name':'test'}, Model1(id=1, name="test").to_dict())
        self.assertEquals({'name':'hello world'}, Model2(name="hello world").to_dict())
    
    def test_from_dict(self):
        """ Test from_dict. """
        model1 = Model1.from_dict({'id':1, 'name':'test'})
        self.assertEquals(1, model1.id)
        self.assertEquals('test', model1.name)
        
        model2 = Model2.from_dict({'name':'test'})
        self.assertEquals('test', model2.name)
    
    def test_from_dict_error(self):
        """ Test from_dict when the dict does not contain the right keys. """
        try:
            Model1.from_dict({'id':1, 'junk':'test'})
            self.fail("Should have received KeyError")
        except KeyError as e:
            self.assertTrue("name" in str(e))
    
    def test_to_eeprom_data(self):
        """ Test to_eeprom_data. """
        model1 = Model1(id=1, name="test")
        data = model1.to_eeprom_data()
        
        self.assertEquals(1, len(data))
        self.assertEquals(1, data[0].address.bank)
        self.assertEquals(3, data[0].address.offset)
        self.assertEquals(100, data[0].address.length)
        self.assertEquals("test" + "\xff" * 96, data[0].bytes)
        
        model2 = Model2(name="test")
        data = model2.to_eeprom_data()
        
        self.assertEquals(1, len(data))
        self.assertEquals(3, data[0].address.bank)
        self.assertEquals(4, data[0].address.offset)
        self.assertEquals(100, data[0].address.length)
        self.assertEquals("test" + "\xff" * 96, data[0].bytes)
        
        model3 = Model3(name="test", link=123, out=456)
        data = model3.to_eeprom_data()
        
        self.assertEquals(3, len(data))
        
        self.assertEquals(3, data[0].address.bank)
        self.assertEquals(14, data[0].address.offset)
        self.assertEquals(1, data[0].address.length)
        self.assertEquals(str(chr(123)), data[0].bytes)
        
        self.assertEquals(3, data[1].address.bank)
        self.assertEquals(4, data[1].address.offset)
        self.assertEquals(10, data[1].address.length)
        self.assertEquals("test" + "\xff" * 6, data[1].bytes)
        
        self.assertEquals(3, data[2].address.bank)
        self.assertEquals(15, data[2].address.offset)
        self.assertEquals(2, data[2].address.length)
        self.assertEquals(str(chr(1) + chr(200)), data[2].bytes)
        
    
    def test_from_eeprom_data(self):
        """ Test from_eeprom_data. """
        model1_data = [ EepromData(EepromAddress(1, 3, 100), "test" + "\xff" * 96)]
        model1 = Model1.from_eeprom_data(model1_data, 1)
        self.assertEquals(1, model1.id)
        self.assertEquals("test", model1.name)
        
        model2_data = [ EepromData(EepromAddress(3, 4, 100), "hello world" + "\xff" * 89)]
        model2 = Model2.from_eeprom_data(model2_data)
        self.assertEquals("hello world", model2.name)
    
        model3_data = [ EepromData(EepromAddress(3, 4, 10), "hello worl"),
                        EepromData(EepromAddress(3, 14, 1), str(chr(123))),
                        EepromData(EepromAddress(3, 15, 2), str(chr(1) + chr(200))) ]
        model3 = Model3.from_eeprom_data(model3_data)
        self.assertEquals("hello worl", model3.name)
        self.assertEquals(123, model3.link)
        self.assertEquals(456, model3.out)
    
    def test_from_eeprom_wrong_address(self):
        """ Test from_eeprom_data with wrong address. """
        
        try:
            model1_data = [ EepromData(EepromAddress(3, 4, 100), "test" + "\xff" * 96)]
            Model1.from_eeprom_data(model1_data, 1)
            self.fail("Should have receive KeyError.")
        except KeyError as e:
            self.assertTrue("(B1 A3 L100)" in str(e))
    
    def test_from_eeprom_wrong_data(self):
        """ Test from_eeprom_data with wrong data. """
        
        try:
            model3_data = [ EepromData(EepromAddress(3, 4, 10), "hello worljkfdsjklsadfjklsadf"),
                            EepromData(EepromAddress(3, 14, 1), str(chr(123))),
                            EepromData(EepromAddress(3, 15, 2), str(chr(1) + chr(200))) ]
            
            Model3.from_eeprom_data(model3_data)
            self.fail("Should have receive TypeError.")
        except TypeError as e:
            self.assertTrue("Length" in str(e))

    def test_get_addresses(self):
        """ Test get_addresses. """
        addresses = Model1.get_addresses(1)
        
        self.assertEquals(1, len(addresses))
        self.assertEquals(1, addresses[0].bank)
        self.assertEquals(3, addresses[0].offset)
        self.assertEquals(100, addresses[0].length)
        
        addresses = Model2.get_addresses()
        
        self.assertEquals(1, len(addresses))
        self.assertEquals(3, addresses[0].bank)
        self.assertEquals(4, addresses[0].offset)
        self.assertEquals(100, addresses[0].length)
        
        addresses = Model3.get_addresses()
        
        self.assertEquals(3, len(addresses))
        
        self.assertEquals(3, addresses[0].bank)
        self.assertEquals(14, addresses[0].offset)
        self.assertEquals(1, addresses[0].length)
        
        self.assertEquals(3, addresses[1].bank)
        self.assertEquals(4, addresses[1].offset)
        self.assertEquals(10, addresses[1].length)
        
        self.assertEquals(3, addresses[2].bank)
        self.assertEquals(15, addresses[2].offset)
        self.assertEquals(2, addresses[2].length)

    def test_get_addresses_wrong_id(self):
        """ Test get_addresses with a wrong id. """
        try:
            Model1.get_addresses(None)
            self.fail("Expected TypeError.")
        except TypeError as e:
            self.assertTrue("id" in str(e))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()