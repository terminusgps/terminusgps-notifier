import decimal
import typing

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from encrypted_field import EncryptedField
from terminusgps.wialon.session import WialonSession


class TerminusGPSNotifierCustomer(models.Model):
    messages_count = models.PositiveIntegerField(default=0)
    messages_limit = models.PositiveIntegerField(default=500)
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="notifier_customer",
    )
    tax_rate = models.DecimalField(
        decimal_places=2,
        default=decimal.Decimal("0.0825"),
        help_text=_("Enter a tax rate as a decimal."),
        max_digits=12,
    )
    sub_total = models.DecimalField(
        decimal_places=2,
        default=decimal.Decimal("60.00"),
        help_text=_("Enter a sub total as a decimal."),
        max_digits=12,
    )
    tax_total = models.GeneratedField(
        db_persist=True,
        expression=(F("sub_total") * (F("tax_rate") + 1)) - F("sub_total"),
        help_text=_("Automatically generated tax amount."),
        output_field=models.DecimalField(decimal_places=2, max_digits=12),
    )
    grand_total = models.GeneratedField(
        db_persist=True,
        expression=F("sub_total") * (F("tax_rate") + 1),
        help_text=_("Automatically generated grand total amount (sub+tax)."),
        output_field=models.DecimalField(decimal_places=2, max_digits=12),
    )
    subscription = models.ForeignKey(
        "terminusgps_payments.Subscription",
        blank=True,
        default=None,
        help_text=_("Select an Authorizenet subscription from the list."),
        null=True,
        on_delete=models.CASCADE,
        related_name="notifier_customer",
    )
    token = models.OneToOneField(
        "terminusgps_notifier.WialonToken",
        blank=True,
        default=None,
        help_text=_("Select a Wialon API token from the list."),
        null=True,
        on_delete=models.CASCADE,
        related_name="notifier_customer",
    )

    class Meta:
        verbose_name = _("customer")
        verbose_name_plural = _("customers")

    def __str__(self) -> str:
        return str(self.user)


class WialonToken(models.Model):
    name = EncryptedField(max_length=72)
    crt_date = models.DateTimeField(auto_now_add=True)
    mod_date = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"WialonToken #{self.pk}"


class WialonNotification(models.Model):
    class NotificationFlag(models.IntegerChoices):
        FIRST_MESSAGE = 0x0
        EVERY_MESSAGE = 0x1
        DISABLED = 0x2

    notification_id = models.IntegerField(blank=True)
    resource_id = models.IntegerField(blank=True)
    e = models.IntegerField(blank=True, default=1, verbose_name=_("enabled"))
    n = models.CharField(blank=True, max_length=50)
    txt = models.CharField(blank=True, max_length=1024)
    ta = models.IntegerField(blank=True, default=0)
    td = models.IntegerField(blank=True, default=0)
    ma = models.IntegerField(blank=True, default=0)
    mmtd = models.IntegerField(blank=True, default=0)
    cdt = models.IntegerField(blank=True, default=0)
    mast = models.IntegerField(blank=True, default=0)
    mpst = models.IntegerField(blank=True, default=0)
    cp = models.IntegerField(blank=True, default=0)
    fl = models.IntegerField(choices=NotificationFlag.choices, default=0x0)
    tz = models.IntegerField(blank=True, default=0)
    la = models.CharField(blank=True, default="en", max_length=2)
    un = models.JSONField(blank=True, default=list)
    d = models.CharField(blank=True)
    sch = models.JSONField(blank=True, default=dict)
    ctrl_sch = models.JSONField(blank=True, default=dict)
    trg = models.JSONField(blank=True, default=dict)
    act = models.JSONField(blank=True, default=dict)
    ct = models.IntegerField(blank=True, default=0)
    mt = models.IntegerField(blank=True, default=0)

    class Meta:
        verbose_name = _("wialon notification")
        verbose_name_plural = _("wialon notifications")

    def __str__(self) -> str:
        return f"{self.n or self.notification_id}"

    def save(self, **kwargs) -> None:
        if session := kwargs.pop("session", None):
            data = self.pull(session)[0]
            self.notification_id = data["id"]
            self.n = data["n"]
            self.txt = data["txt"]
            self.ta = data["ta"]
            self.td = data["td"]
            self.ma = data["ma"]
            self.mmtd = data["mmtd"]
            self.cdt = data["cdt"]
            self.mast = data["mast"]
            self.mpst = data["mpst"]
            self.cp = data["cp"]
            self.fl = data["fl"]
            self.tz = data["tz"]
            self.la = data["la"]
            self.ac = data["ac"]
            self.d = data["d"]
            self.sch = data["sch"]
            self.ctrl_sch = data["ctrl_sch"]
            self.un = data["un"]
            self.act = data["act"]
            self.trg = data["trg"]
            self.ct = data["ct"]
            self.mt = data["mt"]
        return super().save(**kwargs)

    def pull(self, session: WialonSession) -> list[dict[str, typing.Any]]:
        return session.wialon_api.resource_get_notification_data(
            **{"itemId": self.resource_id, "col": [self.notification_id]}
        )


class WialonObject(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    nm = models.CharField(blank=True, max_length=50)
    mu = models.IntegerField(blank=True, default=0)
    uacl = models.IntegerField(blank=True, default=0)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.nm or self.pk}"

    def save(self, **kwargs) -> None:
        if session := kwargs.pop("session", None):
            if self.pk:
                data = self.pull(session)
                self.sync(data)
        return super().save(**kwargs)

    def pull(
        self, session: WialonSession, flags: int = 0x00000001
    ) -> dict[str, typing.Any]:
        return session.wialon_api.core_search_item(
            **{"id": self.pk, "flags": flags}
        )

    def sync(self, data: dict[str, typing.Any]) -> None:
        self.nm = data["item"]["nm"]
        self.mu = data["item"]["mu"]
        self.uacl = data["item"]["uacl"]


class WialonUser(WialonObject):
    class Meta:
        verbose_name = _("wialon user")
        verbose_name_plural = _("wialon users")


class WialonUnit(WialonObject):
    class Meta:
        verbose_name = _("wialon unit")
        verbose_name_plural = _("wialon units")


class WialonResource(WialonObject):
    class Meta:
        verbose_name = _("wialon resource")
        verbose_name_plural = _("wialon resources")
