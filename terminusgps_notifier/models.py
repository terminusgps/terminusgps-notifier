from functools import cached_property

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from encrypted_field import EncryptedField


class TerminusGPSNotifierCustomer(models.Model):
    messages_count = models.PositiveIntegerField(default=0)
    messages_limit = models.PositiveIntegerField(default=500)
    token = EncryptedField(blank=True, null=True, default=None)
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="notifier_customer",
    )
    subscription = models.ForeignKey(
        "terminusgps_payments.Subscription",
        blank=True,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="notifier_customer",
    )

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")

    def __str__(self) -> str:
        return str(self.user)

    @cached_property
    def has_token(self) -> bool:
        return self.token is not None
