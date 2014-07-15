#Copyright 2014 Mark Santesson
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


import datetime
import logging
import re
from   xml.etree import ElementTree as ET

from   django.db import models
from   django.test import TestCase
from   django import forms

from   serializable import models_to_xml, xml_to_models, delete_all_models_in_db
import serializable
from   utils import indent_xml
from   models import *


###
### Test Classes
###


class TestHelpers(TestCase):
    def test_datetime_conversions(self):
        self.assertEquals( 'datetime(2014,1,2,3,12,13,1456)'
                         , serializable._datetime_to_str(
                                datetime.datetime(2014,1,2,3,12,13,1456)) )
        self.assertEquals( datetime.datetime(2014,1,2,3,12,13,1456)
                         , serializable._str_to_datetime(
                                'datetime(2014,1,2,3,12,13,1456)'))


class TestXmlSerialization(TestCase):
    def add_test_data(self):
        def s(o):
            o.save()
            return o

        menu    = s(Menu(name='Breakfast'))
        menui1  = s(MenuItem(menu=menu, name='Spam and Eggs', price=4.00))
        menui2  = s(MenuItem(menu=menu, name='Eggs and Spam', price=4.50))
        menui3  = s(MenuItem(menu=menu, name='Spammity Spam', price=5.00))
        menui4  = s(MenuItem(menu=menu, name='Spam'         , price=3.00))
        order   = s(Order(customer='Brian', date=datetime.date.today()))
        orderi1 = s(OrderEntry(order=order, menuitem=menui1, count=1))
        orderi2 = s(OrderEntry(order=order, menuitem=menui2, count=1))
        orderi3 = s(OrderEntry(order=order, menuitem=menui4, count=2))

    def verify_test_data_present(self):
        self.assertEquals( 1, len(Menu      .objects.all()) )
        self.assertEquals( 4, len(MenuItem  .objects.all()) )
        self.assertEquals( 1, len(Order     .objects.all()) )
        self.assertEquals( 3, len(OrderEntry.objects.all()) )
        self.assertTrue ( Menu      .objects.get(name='Breakfast') )
        self.assertTrue ( MenuItem  .objects.get(name='Spam and Eggs') )
        self.assertTrue ( MenuItem  .objects.get(name='Eggs and Spam') )
        self.assertTrue ( MenuItem  .objects.get(name='Spammity Spam') )
        self.assertTrue ( MenuItem  .objects.get(name='Spam') )
        self.assertTrue ( Order     .objects.get(customer='Brian') )
        self.assertEquals( 3, len(OrderEntry.objects
                                    .filter(order__customer='Brian')) )

    def verify_test_data_not_present(self):
        for cls in ( Menu, MenuItem, Order, OrderEntry, ):
            self.assertEquals(0, len(cls.objects.all()))

    def test_price(self):
        self.add_test_data()
        self.assertEquals( 1, len(Order     .objects.all()) )
        self.assertEquals( 14.50, Order.objects.all()[0].total() )

    def test_creation(self):
        self.add_test_data()
        self.verify_test_data_present()
        with delete_all_models_in_db.logging_filter:
            delete_all_models_in_db([Menu, Order])

    def test_wipe_db(self):
        self.add_test_data()
        self.assertFalse( Menu.objects.filter(name='invalid name') )
        self.verify_test_data_present()

        with delete_all_models_in_db.logging_filter:
            delete_all_models_in_db([Menu, Order])
        self.assertFalse( Menu.objects.filter(name='invalid name') )
        self.assertFalse( Menu.objects.filter(name='Breakfast') )

        self.verify_test_data_not_present()

    def test_model_to_xml_and_back(self):
        self.add_test_data()
        self.verify_test_data_present()

        xml1 = models_to_xml([Menu, Order])
        print indent_xml(xml1)

        with delete_all_models_in_db.logging_filter:
            delete_all_models_in_db([Menu, Order])
        self.verify_test_data_not_present()

        xml_to_models(xml1)
        self.verify_test_data_present()

        xml2 = models_to_xml([Menu])
        self.assertEquals(indent_xml(xml1), indent_xml(xml2))

