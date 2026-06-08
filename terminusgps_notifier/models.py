from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from encrypted_field import EncryptedField


class Profile(models.Model):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="notifier_profile",
    )
    messages_count = models.PositiveIntegerField(default=0)
    messages_limit = models.PositiveIntegerField(default=500)
    token = EncryptedField(blank=True, null=True, default=None)
    profile_id = models.CharField(blank=True, max_length=50)
    description = models.CharField(blank=True, max_length=50)
    merchant_id = models.CharField(blank=True, max_length=50)
    subscription_id = models.CharField(blank=True, max_length=50)

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")

    def __str__(self) -> str:
        return str(self.user)


class DispatchLog(models.Model):
    user_id = models.IntegerField()
    unit_id = models.IntegerField()
    message = models.CharField(max_length=1024)
    msg_time_int = models.IntegerField()
    dry_run = models.BooleanField()
    unit_name = models.CharField(blank=True)
    location = models.CharField(blank=True)
    date_format = models.CharField(blank=True, default="%Y-%m-%d %H:%M:%S")

    class Meta:
        verbose_name = _("dispatch log")
        verbose_name_plural = _("dispatch logs")

    def __str__(self) -> str:
        return f"DispatchLog #{self.pk}"
