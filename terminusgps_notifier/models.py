from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractBaseUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from encrypted_field import EncryptedField
from terminusgps.authorizenet import api
from terminusgps.authorizenet.service import AuthorizenetService


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
    subscription_id = models.IntegerField(blank=True, null=True, default=None)
    customer_profile_id = models.IntegerField(
        blank=True, null=True, default=None
    )
    objects = CustomerQuerySet.as_manager()

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")

    def __str__(self) -> str:
        return str(self.user)

    def get_subscription_status(
        self, service: AuthorizenetService
    ) -> str | None:
        if self.subscription_id is None:
            return
        anet_response = service.execute(
            api.get_subscription_status(subscription_id=self.pk)
        )
        return str(anet_response.status)
