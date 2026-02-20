from django.contrib import admin

from . import models


@admin.register(models.TerminusGPSNotifierCustomer)
class TerminusGPSCustomerAdmin(admin.ModelAdmin):
    list_display = ["user"]


@admin.register(models.MessagePackage)
class MessagePackageAdmin(admin.ModelAdmin):
    list_display = ["customer", "count", "limit"]


@admin.register(models.WialonNotification)
class WialonNotificationAdmin(admin.ModelAdmin):
    list_display = ["resource", "wialon_id"]


@admin.register(models.WialonResource)
class WialonResource(admin.ModelAdmin):
    list_display = ["nm"]


@admin.register(models.WialonUnit)
class WialonUnitAdmin(admin.ModelAdmin):
    list_display = ["nm"]


@admin.register(models.WialonUnitGroup)
class WialonUnitGroupAdmin(admin.ModelAdmin):
    list_display = ["nm"]
