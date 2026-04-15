from django.contrib import admin

from . import models


@admin.register(models.TerminusGPSNotifierCustomer)
class TerminusGPSCustomerAdmin(admin.ModelAdmin):
    list_display = ["user", "messages_count", "messages_limit"]
