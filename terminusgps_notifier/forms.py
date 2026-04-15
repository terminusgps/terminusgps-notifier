from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _
from terminusgps.wialon.session import WialonAPIError, WialonSession

from terminusgps_notifier.models import TerminusGPSNotifierCustomer


def get_items_from_wialon(
    customer: TerminusGPSNotifierCustomer,
    items_type: str,
    flags: int = 1,
    force: bool = False,
) -> list:
    with WialonSession(token=customer.token) as session:
        response = session.wialon_api.core_search_items(
            **{
                "spec": {
                    "itemsType": items_type,
                    "propName": "sys_name",
                    "propValueMask": "*",
                    "propType": "property",
                    "sortType": "sys_name",
                },
                "force": int(force),
                "from": 0,
                "to": 0,
                "flags": flags,
            }
        )
        return response["items"]


class WialonNotificationTrigger(models.TextChoices):
    GEOFENCE = "geozone", _("Geofence")
    ADDRESS = "address", _("Address")
    SPEED = "speed", _("Speed")
    ALARM = "alarm", _("Alarm")
    DIGITAL_INPUT = "digital_input", _("Digital input")
    PARAMETER = "msg_param", _("Parameter in a message")
    SENSOR = "sensor_value", _("Sensor value")
    OUTAGE = "outage", _("Connection loss")
    SMS = "sms", _("SMS")
    INTERPOSITION = "interposition", _("Interposition")
    EXCESS = "msgs_counter", _("Excess of messages")
    ROUTE = "route_control", _("Route progress")
    DRIVER = "driver", _("Driver")
    TRAILER = "trailer", _("Trailer")
    MAINTENANCE = "service_intervals", _("Maintenance")
    FUEL_FILL = "fuel_filling", _("Fuel filling")
    FUEL_DRAIN = "fuel_theft", _("Fuel draining")
    HEALTH = "health_check", _("Health check")
    COMBO = "expression", _("Combination")


class WialonNotificationAction(models.TextChoices):
    EMAIL = "email", _("Email")
    SMS = "sms", _("SMS")
    MESSAGE = "message", _("Message")
    MOBILE = "mobile_apps", _("Send mobile notification")
    REQUEST = "push_messages", _("Send a request")
    TELEGRAM = "messenger_messages", _("Send notification to Telegram")
    EVENT = "event", _("Register event for unit")
    COMMAND = "exec_cmd", _("Send a command")
    ACCESS = "user_access", _("Change access to units")
    SET_COUNTER = "counter", _("Set counter value")
    STORE_COUNTER = "store_counter", _("Store counter value as a parameter")
    STATUS = "status", _("Register unit status")
    GROUPS = "group_manipulation", _("Add or remove units from groups")
    REPORT = "email_report", _("Send a report by email")
    RIDE = "route_control", _("Create a ride")
    SEPARATE_DRIVER = "drivers_reset", _("Separate driver")
    SEPARATE_TRAILER = "trailers_reset", _("Separate trailer")
    TASK = "create_task", _("Create task")


class NotificationDispatchForm(forms.Form):
    """
    A form for dispatching Wialon unit notifications.

    Attributes:
        Required:
            - unit_id: An 8-digit Wialon unit id for phone number lookup.
            - user_id: A user id for Wialon API token retrieval.
            - message: A 1024-character max message to dispatch.
            - msg_time_int: Notification trigger time as a UNIX-timestamp.

        Optional:
            - dry_run: Whether to dispatch the notification as a dry run.
            - unit_name: Name of the unit that triggered the notification.
            - location: Location of the notification trigger.
            - date_format: Date format string.

    """

    user_id = forms.IntegerField()
    unit_id = forms.IntegerField()
    message = forms.CharField(max_length=1024)
    msg_time_int = forms.IntegerField()
    dry_run = forms.BooleanField(initial=False, required=False)
    unit_name = forms.CharField(required=False)
    location = forms.CharField(required=False)
    date_format = forms.CharField(required=False, initial="%Y-%m-%d %H:%M:%S")


class WialonTokenForm(forms.Form):
    access_token = forms.CharField()


class WialonResourceSelectForm(forms.Form):
    resource = forms.ChoiceField(choices=[])

    def __init__(self, **kwargs) -> None:
        try:
            user = kwargs.pop("user")
        except KeyError:
            raise ValueError("'user' kwarg is required")
        try:
            items = get_items_from_wialon(
                customer=user.notifier_customer, items_type="avl_resource"
            )
            choices = [(int(item["id"]), str(item["nm"])) for item in items]
        except WialonAPIError as error:
            print(error)
            choices = []
        self.base_fields["resource"].choices = choices
        super().__init__(**kwargs)


class WialonUnitSelectForm(forms.Form):
    units = forms.MultipleChoiceField(choices=[])

    def __init__(self, **kwargs) -> None:
        try:
            user = kwargs.pop("user")
        except KeyError:
            raise ValueError("'user' kwarg is required")
        try:
            items = get_items_from_wialon(
                customer=user.notifier_customer, items_type="avl_unit"
            )
            choices = [(int(item["id"]), str(item["nm"])) for item in items]
        except WialonAPIError as error:
            print(error)
            choices = []
        self.base_fields["units"].choices = choices
        super().__init__(**kwargs)


class WialonUnitGroupSelectForm(forms.Form):
    unit_groups = forms.MultipleChoiceField(choices=[])

    def __init__(self, **kwargs) -> None:
        try:
            user = kwargs.pop("user")
        except KeyError:
            raise ValueError("'user' kwarg is required")
        try:
            items = get_items_from_wialon(
                customer=user.notifier_customer, items_type="avl_unit_group"
            )
            choices = [(int(item["id"]), str(item["nm"])) for item in items]
        except WialonAPIError as error:
            print(error)
            choices = []
        self.base_fields["unit_groups"].choices = choices
        super().__init__(**kwargs)
