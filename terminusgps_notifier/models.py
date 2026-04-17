from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from encrypted_field import EncryptedField


class CustomerQuerySet(models.QuerySet):
    async def afrom_user(self, user: AbstractBaseUser):
        return await self.aget(user=user)

    def from_user(self, user: AbstractBaseUser):
        return self.get(user=user)


class Customer(models.Model):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="notifier_customer",
    )
    token = EncryptedField(blank=True, null=True, default=None)
    messages_count = models.PositiveIntegerField(default=0)
    messages_limit = models.PositiveIntegerField(default=500)
    subscription = models.ForeignKey(
        "terminusgps_payments.Subscription",
        blank=True,
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="notifier_customer",
    )
    objects = CustomerQuerySet.as_manager()

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")

    def __str__(self) -> str:
        return str(self.user)
