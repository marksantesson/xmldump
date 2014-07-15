
from   django.db import models


class Menu(models.Model):
    name = models.CharField(max_length=128)

class MenuItem(models.Model):
    menu  = models.ForeignKey(Menu)
    name  = models.CharField(max_length=128)
    price = models.FloatField()

class Order(models.Model):
    customer = models.CharField(max_length=128)
    date = models.DateField()
    def total(self):
        return sum([ entry.count*entry.menuitem.price
                     for entry in OrderEntry.objects.filter(order__id=self.id)
                   ])

class OrderEntry(models.Model):
    order    = models.ForeignKey(Order)
    menuitem = models.ForeignKey(MenuItem)
    count    = models.IntegerField()


