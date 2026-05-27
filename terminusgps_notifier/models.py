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
    subscription_id = models.PositiveIntegerField(
        blank=True, null=True, default=None
    )

    class Meta:
        verbose_name = _("profile")
        verbose_name_plural = _("profiles")

    def __str__(self) -> str:
        return str(self.user)
