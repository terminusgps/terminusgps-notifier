from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from encrypted_field import EncryptedField

from terminusgps_notifier.wialon import get_phones


class Profile(models.Model):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="notifier_profile",
    )
    messages_count = models.PositiveIntegerField(default=0)
    messages_limit = models.PositiveIntegerField(default=500)
    token = EncryptedField(blank=True, null=True, default=None)

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")

    def __str__(self) -> str:
        return str(self.user)

    def get_wialon_destination_phone_numbers(self, unit_id: int) -> list[str]:
        """Returns destination phone numbers for a Wialon unit by id."""
        return get_phones(self.token, unit_id)

    def set_wialon_api_token_and_save(self, token: str) -> None:
        """Sets :py:attr:`token` to ``token`` then saves."""
        self.token = str(token)
        self.save(update_fields=["token"])

    def update_messages_count_and_save(self, num_messages: int) -> None:
        """Increments :py:attr:`messages_count` by ``num_messages`` then saves."""
        self.messages_count = models.F("messages_count") + num_messages
        self.save(update_fields=["messages_count"])

    def has_available_messages(self) -> bool:
        """Returns whether the profile has reached its messaging limit."""
        return self.messages_count < self.messages_limit

    def has_active_subscription(self) -> bool:
        """Returns whether the profile has an active subscription."""
        return True


class DispatchLog(models.Model):
    user_id = models.IntegerField()
    unit_id = models.IntegerField()
    message = models.CharField(max_length=1024)
    msg_time_int = models.IntegerField()
    phones = models.JSONField(default=list)
    method = models.CharField(
        choices=[("sms", _("SMS")), ("voice", _("Voice"))]
    )
    pub_date = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("dispatch log")
        verbose_name_plural = _("dispatch logs")

    def __str__(self) -> str:
        return f"DispatchLog #{self.pk}"
