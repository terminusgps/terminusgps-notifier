from django.contrib import admin

from . import models


@admin.register(models.Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "messages_count", "messages_limit"]


@admin.register(models.DispatchLog)
class DispatchLogAdmin(admin.ModelAdmin):
    list_display = ["unit_id", "method", "message"]
