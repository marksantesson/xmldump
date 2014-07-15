
from   django.db import models


from   serializable import owned_models


class Menu(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    menu  = models.ForeignKey(Menu)
    name  = models.CharField(max_length=128)
    price = models.FloatField()

    @classmethod
    def owned_models(cls):
        '''This isn't necessary but it makes the xml more orderly.'''
        ret = owned_models(cls, delegate=False)
        return [ x for x in ret if x[0] != OrderEntry ]

    def __str__(self):
        return '{} - {} - ${}'.format(self.name, self.menu.name, self.price)


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

