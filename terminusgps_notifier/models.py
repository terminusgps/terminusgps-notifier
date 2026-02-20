import decimal
import typing
from collections.abc import Sequence

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

    def get_resources_from_wialon(
        self, session: WialonSession, force: bool = False
    ) -> list[dict[str, typing.Any]]:
        params = {
            "spec": {
                "itemsType": "avl_resource",
                "propName": "sys_name",
                "propValueMask": "*",
                "sortType": "sys_name",
                "propType": "property",
            },
            "flags": 1,
            "force": int(force),
            "from": 0,
            "to": 0,
        }
        return session.wialon_api.core_search_items(**params).get("items", [])


class MessagePackage(models.Model):
    price = models.DecimalField(decimal_places=2, max_digits=12)
    count = models.IntegerField(default=0)
    limit = models.IntegerField(default=500)
    customer = models.ForeignKey(
        "terminusgps_notifier.TerminusGPSNotifierCustomer",
        on_delete=models.CASCADE,
        related_name="packages",
    )

    class Meta:
        verbose_name = _("message package")
        verbose_name_plural = _("message packages")

    def __str__(self) -> str:
        return f"MessagePackage #{self.pk}"


class WialonToken(models.Model):
    name = EncryptedField(max_length=72)

    class Meta:
        verbose_name = _("wialon token")
        verbose_name_plural = _("wialon tokens")

    def __str__(self) -> str:
        return f"WialonToken #{self.pk}"


class WialonNotification(models.Model):
    class NotificationFlag(models.IntegerChoices):
        FIRST_MESSAGE = 0x0
        EVERY_MESSAGE = 0x1
        DISABLED = 0x2

    resource = models.ForeignKey(
        "terminusgps_notifier.WialonResource",
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    wialon_id = models.IntegerField(blank=True)
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
    ac = models.IntegerField(blank=True, default=0)
    un = models.JSONField(blank=True, default=list)
    d = models.CharField(blank=True)
    sch = models.JSONField(blank=True, default=dict)
    ctrl_sch = models.JSONField(blank=True, default=dict)
    trg = models.JSONField(blank=True, default=dict)
    act = models.JSONField(blank=True, default=list)
    ct = models.IntegerField(blank=True, default=0)
    mt = models.IntegerField(blank=True, default=0)

    class Meta:
        verbose_name = _("wialon notification")
        verbose_name_plural = _("wialon notifications")

    def __str__(self) -> str:
        return f"{self.n or self.wialon_id}"

    def save(self, **kwargs) -> None:
        if session := kwargs.pop("session", None):
            if self.wialon_id is not None:
                data = self.pull(session)[0]
                self.sync(data)
        return super().save(**kwargs)

    def pull(self, session: WialonSession) -> list[dict[str, typing.Any]]:
        return session.wialon_api.resource_get_notification_data(
            **{"itemId": self.resource.pk, "col": [self.wialon_id]}
        )

    def sync(self, data: dict[str, typing.Any]) -> None:
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


class WialonObject(models.Model):
    id = models.PositiveBigIntegerField(primary_key=True)
    nm = models.CharField(blank=True, max_length=50)
    mu = models.IntegerField(blank=True, default=0)
    uacl = models.IntegerField(blank=True, default=0)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return f"{self.nm or self.id}"

    def save(self, **kwargs) -> None:
        if session := kwargs.pop("session", None):
            if self.pk:
                data = self.pull(session)
                self.sync(data)
        return super().save(**kwargs)

    def pull(
        self, session: WialonSession, flags: int = 1
    ) -> dict[str, typing.Any]:
        return session.wialon_api.core_search_item(
            **{"id": self.pk, "flags": flags}
        )

    def sync(self, data: dict[str, typing.Any]) -> None:
        self.nm = data["item"]["nm"]
        self.mu = data["item"]["mu"]
        self.uacl = data["item"]["uacl"]


class WialonResource(WialonObject):
    class Meta:
        verbose_name = _("wialon resource")
        verbose_name_plural = _("wialon resources")

    def get_notification_data(
        self, session: WialonSession, ids: Sequence[str] | None = None
    ) -> list[dict[str, typing.Any]]:
        params = {"itemId": self.pk}
        if ids is not None:
            params["col"] = ids
        return session.wialon_api.resource_get_notification_data(**params)


class WialonUnit(WialonObject):
    class Meta:
        verbose_name = _("wialon unit")
        verbose_name_plural = _("wialon units")


class WialonUnitGroup(WialonObject):
    class Meta:
        verbose_name = _("wialon unit group")
        verbose_name_plural = _("wialon unit groups")
