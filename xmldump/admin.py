from django.contrib import admin

from models import *


class MenuItemAdmin(admin.ModelAdmin):
    list_display = ( 'name', 'menu', 'price', )


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0


class MenuAdmin(admin.ModelAdmin):
    list_display = ( 'name', )
    inlines = [ MenuItemInline, ]


class OrderEntryAdmin(admin.ModelAdmin):
    list_display = ( 'menuitem', 'count', )


class OrderEntryInline(admin.TabularInline):
    model = OrderEntry
    extra=0


class OrderAdmin(admin.ModelAdmin):
    fields = [ 'customer', 'date', ]
    inlines = [ OrderEntryInline, ]
    list_display = ( 'date', 'customer', 'total', )


admin.site.register(MenuItem, MenuItemAdmin)
admin.site.register(Menu, MenuAdmin)
admin.site.register(Order, OrderAdmin)

