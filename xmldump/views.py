
import datetime
import logging
from   xml.etree import ElementTree as ET

from   django.shortcuts import render

from   serializable import models_to_xml, xml_to_models, delete_all_models_in_db
from   models import Menu, Order, MenuItem, OrderEntry
from   test_serializable import indent_xml


def index(request):
    if request.POST.get('cmd') == 'Load XML':
        delete_all_models_in_db([Menu,Order])
        xml = ET.fromstring(request.POST['xml'])
        xml_to_models(xml)
    elif request.POST.get('cmd') == 'Clear XML':
        delete_all_models_in_db([Menu,Order])
    elif request.POST.get('cmd') == 'Default XML':
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
    elif request.POST.get('cmd') in (None, 'Refresh'):
        pass
    else:
        raise Exception('Unrecognized command')

    xml = indent_xml( models_to_xml([Menu, Order]) )

    context = dict( xml = xml
                  )

    return render(request, 'xmldump/xmldump.html', context)

