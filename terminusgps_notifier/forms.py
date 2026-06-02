from django import forms
from django.contrib.auth.forms import BaseUserCreationForm
from django.db import models
from django.forms import widgets
from django.utils.translation import gettext_lazy as _

from terminusgps_notifier import constants


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


class WialonSensorType(models.TextChoices):
    ANY = "", _("Any")
    # Mileage
    MILEAGE = "mileage", _("Mileage sensor")
    ODOMETER = "odometer", _("Relative odometer")
    # Digital
    IGNITION = "engine operation", _("Engine ignition sensor")
    ALARM = "alarm trigger", _("Alarm trigger")
    PRIVATE = "private mode", _("Private mode")
    RTMOTION = "real-time motion sensor", _("Real-time motion sensor")
    DIGITAL = "digital", _("Custom digital sensor")
    # Gauges
    VOLTAGE = "voltage", _("Voltage sensor")
    WEIGHT = "weight", _("Weight sensor")
    ACCELEROMETER = "accelerometer", _("Accelerometer")
    TEMPERATURE = "temperature", _("Temperature sensor")

    TEMPERATURE_COEF = "temperature coefficient", _("Temperature coefficient")
    # Engine
    ENGINE_RPM = "engine rpm", _("Engine revolution sensor")
    ENGINE_EFF = "engine efficiency", _("Engine efficiency sensor")
    ENGINE_HOURS_ABS = "engine hours", _("Absolute engine hours")
    ENGINE_HOURS_REL = "relative engine hours", _("Relative engine hours")
    # Fuel
    FUEL_CONS_IMP = (
        "impulse fuel consumption",
        _("Impulse fuel consumption sensor"),
    )
    FUEL_CONS_ABS = (
        "absolute fuel consumption",
        _("Absolute fuel consumption sensor"),
    )
    FUEL_CONS_INT = (
        "instant fuel consumption",
        _("Instant fuel consumption sensor"),
    )
    FUEL_LEVEL = "fuel level", _("Fuel level sensor")
    FUEL_LEVEL_IMP = (
        "fuel level impulse sensor",
        _("Impulse fuel level sensor"),
    )
    BATTERY_LEVEL = "battery level", _("Battery level sensor")
    # Other
    COUNTER = "counter", _("Counter sensor")

    CUSTOM = "custom", _("Custom sensor")
    DRIVER = "driver", _("Driver assignment")

    TRAILER = "trailer", _("Trailer assignment")
    TAG = "tag", _("Passenger sensor")


class UserCreationForm(BaseUserCreationForm):
    first_name = forms.CharField(label=_("First name"), max_length=64)
    last_name = forms.CharField(label=_("Last name"), max_length=64)
    email = forms.EmailField(
        label=_("Email address"),
        help_text=_("Required. Provide a valid email address."),
    )


class SubscriptionCreationForm(forms.Form):
    payment_id = forms.ChoiceField(choices=[], label=_("Payment Method"))
    address_id = forms.ChoiceField(choices=[], label=_("Shipping Address"))

    def __init__(
        self, payment_choices, address_choices, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.fields["payment_id"].choices = payment_choices
        self.fields["address_id"].choices = address_choices


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


class CreateNotificationStepFourForm(forms.Form):
    ta = forms.DateTimeField(
        label=_("Activation Time"),
        required=False,
        widget=widgets.DateInput(attrs={"type": "datetime-local"}),
    )
    td = forms.DateTimeField(
        label=_("Deactivation Time"),
        required=False,
        widget=widgets.DateInput(attrs={"type": "datetime-local"}),
    )
    tz = forms.TypedChoiceField(
        choices=constants.TIMEZONES, coerce=int, label=_("Timezone")
    )
    ma = forms.IntegerField(min_value=0, label=_("Max Alarms"))
    mmtd = forms.TypedChoiceField(
        choices=[
            (0, _("Any time")),
            (60, _("1 minute")),
            (600, _("10 minutes")),
            (1800, _("30 minutes")),
            (3600, _("1 hour")),
            (21600, _("6 hours")),
            (43200, _("12 hours")),
            (86400, _("1 day")),
            (864000, _("10 days")),
        ],
        coerce=int,
        label=_("Max Time Interval Between Messages"),
    )
    cdt = forms.IntegerField(
        min_value=0, max_value=1800, label=_("Alarm Timeout")
    )
    mast = forms.IntegerField(
        min_value=0,
        max_value=86400,
        label=_("Minimum Duration of Alarm State"),
    )
    mpst = forms.IntegerField(
        min_value=0,
        max_value=86400,
        label=_("Minimum Duration of Previous State"),
    )
    cp = forms.TypedChoiceField(
        choices=[
            (0, _("Any time")),
            (60, _("Last minute")),
            (600, _("Last 10 minutes")),
            (3600, _("Last hour")),
            (86400, _("Last day")),
        ],
        coerce=int,
        label=_("Control Period"),
    )
    fl = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger on first message")),
            (1, _("Trigger on every message")),
            (2, _("Disabled")),
        ],
        coerce=int,
        label=_("Flags"),
    )
    la = forms.ChoiceField(choices=[("en", _("English"))], label=_("Language"))

    def clean_ta(self):
        if ta := self.cleaned_data.get("ta"):
            return int(ta.timestamp())
        return 0

    def clean_td(self):
        if td := self.cleaned_data.get("td"):
            return int(td.timestamp())
        return 0


class GeofenceTriggerForm(forms.Form):
    sensor_type = forms.ChoiceField(
        choices=WialonSensorType.choices,
        help_text=_("Select a sensor type."),
        label=_("Sensor type"),
    )
    sensor_name_mask = forms.CharField(
        help_text=_("Provide a wildcard-based sensor name mask."),
        label=_("Sensor name mask"),
        max_length=50,
        min_length=1,
        widget=widgets.TextInput(attrs={"placeholder": "*ign*"}),
    )
    lower_bound = forms.FloatField(
        help_text=_("Provide the sensor value's lower bound."),
        label=_("Lower boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "0.0"}),
    )
    upper_bound = forms.FloatField(
        help_text=_("Provide the sensor value's upper bound."),
        label=_("Upper boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "1.0"}),
    )
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to form boundaries based on the current sensor value or previous sensor value."
        ),
        label=_("Boundary formation"),
    )
    merge = forms.TypedChoiceField(
        choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
        coerce=int,
        help_text=_(
            "Select whether to calculate sensor values separately or sum up their values."
        ),
        label=_("Merge sensor values"),
    )
    reversed = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger within range")),
            (1, _("Trigger outside range")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger when the sensor value is within or outside of the specified boundaries."
        ),
        label=_("Reversed boundaries"),
    )
    geozone_ids = forms.CharField(
        label=_("Geofences"),
        help_text=_("Select geofences for notification trigger."),
    )
    type = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger on geofence entry")),
            (1, _("Trigger on geofence exit")),
        ],
        coerce=int,
        help_text=_("Select whether to trigger on geofence entry or exit."),
        label=_("Geofence trigger behavior"),
    )
    min_speed = forms.IntegerField(
        help_text=_(
            "Provide the minimum speed required to trigger the notification in km/h."
        ),
        label=_("Minimum speed"),
        max_value=255,
        min_value=0,
    )
    max_speed = forms.IntegerField(
        min_value=0,
        max_value=255,
        label=_("Maximum speed"),
        help_text=_(
            "Provide the maximum speed required to trigger the notification in km/h."
        ),
    )
    include_lbs = forms.TypedChoiceField(
        choices=[
            (0, _("Do not process LBS messages")),
            (1, _("Process LBS messages")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to include location-based service messages."
        ),
        label=_("Include LBS messages"),
    )
    lo = forms.ChoiceField(
        choices=[("", _("Ignore")), ("AND", _("AND")), ("OR", _("OR"))],
        label=_("Logical operator"),
        required=False,
    )


class AddressTriggerForm(forms.Form):
    sensor_type = forms.ChoiceField(
        choices=WialonSensorType.choices,
        help_text=_("Select a sensor type."),
        label=_("Sensor type"),
    )
    sensor_name_mask = forms.CharField(
        help_text=_("Provide a wildcard-based sensor name mask."),
        label=_("Sensor name mask"),
        max_length=50,
        min_length=1,
        widget=widgets.TextInput(attrs={"placeholder": "*ign*"}),
    )
    lower_bound = forms.FloatField(
        help_text=_("Provide the sensor value's lower bound."),
        label=_("Lower boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "0.0"}),
    )
    upper_bound = forms.FloatField(
        help_text=_("Provide the sensor value's upper bound."),
        label=_("Upper boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "1.0"}),
    )
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to form boundaries based on the current sensor value or previous sensor value."
        ),
        label=_("Boundary formation"),
    )
    merge = forms.TypedChoiceField(
        choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
        coerce=int,
        help_text=_(
            "Select whether to calculate sensor values separately or sum up their values."
        ),
        label=_("Merge sensor values"),
    )
    reversed = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger within range")),
            (1, _("Trigger outside range")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger when the sensor value is within or outside of the specified boundaries."
        ),
        label=_("Reversed boundaries"),
    )
    radius = forms.IntegerField(
        help_text=_("Provide a radius in feet. 1ft minimum."),
        label=_("Radius"),
        min_value=1,
        widget=widgets.NumberInput(attrs={"placeholder": "1"}),
    )
    type = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger when within radius")),
            (1, _("Trigger when outside radius")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger the notification when the triggering unit is within or outside of the address radius."
        ),
    )
    min_speed = forms.IntegerField(
        help_text=_(
            "Provide the minimum speed required to trigger the notification in km/h."
        ),
        label=_("Minimum speed"),
        max_value=255,
        min_value=0,
    )
    max_speed = forms.IntegerField(
        min_value=0,
        max_value=255,
        label=_("Maximum speed"),
        help_text=_(
            "Provide the maximum speed required to trigger the notification in km/h."
        ),
    )
    country = forms.CharField(
        help_text=_("Optional. Provide a country."),
        required=False,
        widget=widgets.TextInput(attrs={"placeholder": "USA"}),
    )
    region = forms.CharField(
        help_text=_("Provide a region/state."),
        required=False,
        widget=widgets.TextInput(attrs={"placeholder": "Texas"}),
    )
    city = forms.CharField(
        help_text=_("Provide a city."),
        required=False,
        widget=widgets.TextInput(attrs={"placeholder": "Cypress"}),
    )
    street = forms.CharField(
        help_text=_("Provide a street name."),
        required=False,
        widget=widgets.TextInput(attrs={"placeholder": "South Dr."}),
    )
    house = forms.CharField(
        help_text=_("Provide a house number."),
        required=False,
        widget=widgets.TextInput(attrs={"placeholder": "17610"}),
    )
    include_lbs = forms.TypedChoiceField(
        choices=[
            (0, _("Do not process LBS messages")),
            (1, _("Process LBS messages")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to include location-based service messages."
        ),
        label=_("Include LBS messages"),
    )


class SpeedTriggerForm(forms.Form):
    lower_bound = forms.FloatField(
        help_text=_("Provide the sensor value's lower bound."),
        label=_("Lower boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "0.0"}),
    )
    max_speed = forms.IntegerField(
        min_value=0,
        max_value=255,
        label=_("Maximum speed"),
        help_text=_(
            "Provide the maximum speed required to trigger the notification in km/h."
        ),
    )
    merge = forms.TypedChoiceField(
        choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
        coerce=int,
        help_text=_(
            "Select whether to calculate sensor values separately or sum up their values."
        ),
        label=_("Merge sensor values"),
    )
    min_speed = forms.IntegerField(
        help_text=_(
            "Provide the minimum speed required to trigger the notification in km/h."
        ),
        label=_("Minimum speed"),
        max_value=255,
        min_value=0,
    )
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to form boundaries based on the current sensor value or previous sensor value."
        ),
        label=_("Boundary formation"),
    )
    reversed = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger within range")),
            (1, _("Trigger outside range")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger when the sensor value is within or outside of the specified boundaries."
        ),
        label=_("Reversed boundaries"),
    )
    sensor_name_mask = forms.CharField(
        help_text=_("Provide a wildcard-based sensor name mask."),
        label=_("Sensor name mask"),
        max_length=50,
        min_length=1,
        widget=widgets.TextInput(attrs={"placeholder": "*ign*"}),
    )
    sensor_type = forms.ChoiceField(
        choices=WialonSensorType.choices,
        help_text=_("Select a sensor type."),
        label=_("Sensor type"),
    )
    upper_bound = forms.FloatField(
        help_text=_("Provide the sensor value's upper bound."),
        label=_("Upper boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "1.0"}),
    )
    driver = forms.TypedChoiceField(
        label=_("Driver assignment"),
        choices=[
            (0, _("Ignore driver assignment")),
            (1, _("Trigger only when driver unassigned")),
            (2, _("Trigger only when driver assigned")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger only when a driver is assigned or not."
        ),
    )


class AlarmTriggerForm(forms.Form):
    pass


class DigitalInputTriggerForm(forms.Form):
    input_index = forms.IntegerField(
        min_value=1,
        max_value=32,
        help_text=_("Select a digital input index between 1 and 32."),
    )
    type = forms.TypedChoiceField(
        choices=[
            (0, _("Check for activation")),
            (1, _("Check for deactivation")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger notification on activation or deactivation."
        ),
    )


class ParameterInAMessageTriggerForm(forms.Form):
    kind = forms.TypedChoiceField(
        choices=[
            (0, _("Value range")),
            (1, _("Text mask")),
            (2, _("Parameter availability")),
            (3, _("Parameter lack")),
        ],
        coerce=int,
        help_text=_("Select a parameter control type."),
    )
    lower_bound = forms.FloatField(
        help_text=_("Provide the sensor value's lower bound."),
        label=_("Lower boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "0.0"}),
    )
    param = forms.CharField(
        label=_("Parameter name"), help_text=_("Provide the parameter name.")
    )
    text_mask = forms.CharField(
        help_text=_("Provide a wildcard-based text mask."),
        label=_("Text mask"),
        widget=widgets.TextInput(attrs={"placeholder": "*"}),
    )
    type = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger when within range")),
            (1, _("Trigger when outside range")),
        ],
        coerce=int,
        label=_("Trigger range"),
        help_text=_(
            "Select whether to trigger the notification when the sensor value is within range or outside of range."
        ),
    )
    upper_bound = forms.FloatField(
        help_text=_("Provide the sensor value's upper bound."),
        label=_("Upper boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "1.0"}),
    )


class SensorValueTriggerForm(forms.Form):
    lower_bound = forms.FloatField(
        help_text=_("Provide the sensor value's lower bound."),
        label=_("Lower boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "0.0"}),
    )
    merge = forms.TypedChoiceField(
        choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
        coerce=int,
        help_text=_(
            "Select whether to calculate sensor values separately or sum up their values."
        ),
        label=_("Merge sensor values"),
    )
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to form boundaries based on the current sensor value or previous sensor value."
        ),
        label=_("Boundary formation"),
    )
    sensor_name_mask = forms.CharField(
        help_text=_("Provide a wildcard-based sensor name mask."),
        label=_("Sensor name mask"),
        max_length=50,
        min_length=1,
        widget=widgets.TextInput(attrs={"placeholder": "*ign*"}),
    )
    sensor_type = forms.ChoiceField(
        choices=WialonSensorType.choices,
        help_text=_("Select a sensor type."),
        label=_("Sensor type"),
    )
    type = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger when within range")),
            (1, _("Trigger when outside range")),
        ],
        coerce=int,
        label=_("Trigger range"),
        help_text=_(
            "Select whether to trigger the notification when the sensor value is within range or outside of range."
        ),
    )
    upper_bound = forms.FloatField(
        help_text=_("Provide the sensor value's upper bound."),
        label=_("Upper boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "1.0"}),
    )


class ConnectionLossTriggerForm(forms.Form):
    time = forms.IntegerField(
        help_text=_("Provide a time interval in seconds."),
        label=_("Time interval"),
    )
    type = forms.TypedChoiceField(
        choices=[(0, _("Coordinates Loss")), (1, _("Connection Loss"))],
        coerce=int,
        help_text=_("Select a control type."),
        label=_("Control type"),
    )
    include_lbs = forms.TypedChoiceField(
        choices=[
            (0, _("Do not process LBS messages")),
            (1, _("Process LBS messages")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to include location-based service messages."
        ),
        label=_("Include LBS messages"),
    )
    check_restore = forms.TypedChoiceField(
        choices=[
            (0, _("Connection Lost")),
            (1, _("Connection Lost and Restored")),
            (2, _("Connection Restored")),
        ],
        coerce=int,
        help_text=_(
            "Select a connection state to trigger the notification on."
        ),
        label=_("Connection state"),
    )
    geozones_type = forms.TypedChoiceField(
        choices=[(0, _("Out of Geofence")), (1, _("Within Geofence"))],
        coerce=int,
    )
    geozones_list = forms.CharField()


class SMSTriggerForm(forms.Form):
    mask = forms.CharField(help_text=_("Provide a wildcard-based mask."))


class InterpositionTriggerForm(forms.Form):
    sensor_name_mask = forms.CharField(
        help_text=_("Provide a wildcard-based sensor name mask."),
        label=_("Sensor name mask"),
        max_length=50,
        min_length=1,
        widget=widgets.TextInput(attrs={"placeholder": "*ign*"}),
    )
    sensor_type = forms.ChoiceField(
        choices=WialonSensorType.choices,
        help_text=_("Select a sensor type."),
        label=_("Sensor type"),
    )
    lower_bound = forms.FloatField(
        help_text=_("Provide the sensor value's lower bound."),
        label=_("Lower boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "0.0"}),
    )
    upper_bound = forms.FloatField(
        help_text=_("Provide the sensor value's upper bound."),
        label=_("Upper boundary"),
        widget=widgets.NumberInput(attrs={"placeholder": "1.0"}),
    )
    merge = forms.TypedChoiceField(
        choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
        coerce=int,
        help_text=_(
            "Select whether to calculate sensor values separately or sum up their values."
        ),
        label=_("Merge sensor values"),
    )
    max_speed = forms.IntegerField(
        min_value=0,
        max_value=255,
        label=_("Maximum speed"),
        help_text=_(
            "Provide the maximum speed required to trigger the notification in km/h."
        ),
    )
    min_speed = forms.IntegerField(
        help_text=_(
            "Provide the minimum speed required to trigger the notification in km/h."
        ),
        label=_("Minimum speed"),
        max_value=255,
        min_value=0,
    )
    reversed = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger within range")),
            (1, _("Trigger outside range")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger when the sensor value is within or outside of the specified boundaries."
        ),
        label=_("Reversed boundaries"),
    )
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to form boundaries based on the current sensor value or previous sensor value."
        ),
        label=_("Boundary formation"),
    )
    radius = forms.IntegerField(
        help_text=_("Provide a radius in feet. 1ft minimum."),
        label=_("Radius"),
        min_value=1,
        widget=widgets.NumberInput(attrs={"placeholder": "1"}),
    )
    type = forms.TypedChoiceField(
        choices=[(0, _("On approach")), (1, _("On withdrawl"))],
        coerce=int,
        label=_("Control type"),
        help_text=_(
            "Select whether to trigger notification on approach or withdrawl."
        ),
    )
    unit_guids = forms.CharField()
    include_lbs = forms.TypedChoiceField(
        choices=[
            (0, _("Do not process LBS messages")),
            (1, _("Process LBS messages")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to include location-based service messages."
        ),
        label=_("Include LBS messages"),
    )
    lo = forms.ChoiceField(
        choices=[("", _("Ignore")), ("AND", _("AND")), ("OR", _("OR"))],
        label=_("Logical operator"),
        required=False,
    )


class ExcessOfMessagesTriggerForm(forms.Form):
    flags = forms.TypedChoiceField(
        choices=[(1, _("Data messages")), (2, _("SMS messages"))],
        coerce=int,
        help_text=_("Select a message type."),
        label=_("Message type"),
    )
    msgs_limit = forms.IntegerField(
        label=_("Message limit"), help_text=_("Provide a message limit.")
    )
    time_offset = forms.IntegerField(
        help_text=_(
            "Provide a time offset in seconds. Maximum is 86400 (1 day)."
        ),
        label=_("Time offset"),
        max_value=86400,
    )


class RouteProgressTriggerForm(forms.Form):
    mask = forms.CharField(
        help_text=_("Provide a wildcard-based route name mask."),
        label=_("Route name mask"),
        widget=widgets.TextInput(attrs={"placeholder": "*"}),
    )
    round_mask = forms.CharField(
        help_text=_("Provide a wildcard-based ride name mask."),
        label=_("Ride name name"),
        widget=widgets.TextInput(attrs={"placeholder": "*"}),
    )
    schedule_mask = forms.CharField(
        help_text=_("Provide a wildcard-based schedule name mask."),
        label=_("Schedule name name"),
        widget=widgets.TextInput(attrs={"placeholder": "*"}),
    )
    types = forms.TypedMultipleChoiceField(
        choices=[
            (1, _("Ride started")),
            (2, _("Ride finished")),
            (4, _("Ride aborted")),
            (8, _("Arrival at checkpoint")),
            (16, _("Checkpoint skipped")),
            (32, _("Departure from checkout")),
            (64, _("Delay")),
            (128, _("Outrunning")),
            (256, _("Return to schedule")),
        ],
        coerce=int,
        label=_("Route control types"),
        help_text=_("Ctrl+click to select multiple. Cmd+click on Mac."),
    )


class DriverTriggerForm(forms.Form):
    driver_code_mask = forms.CharField(
        help_text=_("Provide a wildcard-based driver code mask."),
        label=_("Driver code mask"),
        widget=widgets.TextInput(attrs={"placeholder": "*"}),
    )
    flags = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger on driver assignment")),
            (1, _("Trigger on driver separation")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger notification on driver assignment or separation."
        ),
        label=_("Control type"),
    )


class TrailerTriggerForm(forms.Form):
    driver_code_mask = forms.CharField(
        help_text=_("Provide a wildcard-based trailer code mask."),
        label=_("Trailer code mask"),
        widget=widgets.TextInput(attrs={"placeholder": "*"}),
    )
    flags = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger on trailer assignment")),
            (1, _("Trigger on trailer separation")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger notification on trailer assignment or separation."
        ),
        label=_("Control type"),
    )


class MaintenanceTriggerForm(forms.Form):
    days = forms.IntegerField(
        label=_("Days interval"), help_text=_("Provide a days interval.")
    )
    engine_hours = forms.IntegerField(
        label=_("Engine hours interval"),
        help_text=_("Provide an engine hours interval in hours."),
    )
    flags = forms.TypedChoiceField(
        choices=[
            (0, _("Control all service intervals")),
            (1, _("Mileage interval")),
            (2, _("Engine hours interval")),
            (4, _("Days interval")),
        ],
        coerce=int,
        label=_("Control type"),
        help_text=_("Select the interval to trigger the notification on."),
    )
    mask = forms.CharField(help_text=_("Provide a wildcard-based mask."))
    mileage = forms.IntegerField(
        label=_("Milage interval"),
        help_text=_("Provide a mileage interval in km."),
    )
    val = forms.TypedChoiceField(
        choices=[
            (1, _("Service term approaches")),
            (2, _("Service term expired")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to trigger the notification when the service term approaches or expired."
        ),
        label=_("Service term"),
    )


class FuelFillingTriggerForm(forms.Form):
    sensor_name_mask = forms.CharField(
        help_text=_("Provide a wildcard-based sensor name mask."),
        label=_("Sensor name mask"),
        max_length=50,
        min_length=1,
        widget=widgets.TextInput(attrs={"placeholder": "*ign*"}),
    )
    geozones_type = forms.TypedChoiceField(
        choices=[
            (0, _("Ignore geofence(s)")),
            (1, _("Only trigger when within geofence(s)")),
        ],
        coerce=int,
        label=_("Geofence control"),
        help_text=_(
            "Select whether to ignore geofences or only trigger when within geofence(s)."
        ),
    )
    geozones_list = forms.CharField()
    realtime_only = forms.TypedChoiceField(
        choices=[
            (0, _("Recalculate historical data")),
            (1, _("Ignore historical data (real-time only)")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to recalculate historical data on trigger."
        ),
        label=_("Real-time only"),
    )


class FuelDrainingTriggerForm(forms.Form):
    sensor_name_mask = forms.CharField(
        help_text=_("Provide a wildcard-based sensor name mask."),
        label=_("Sensor name mask"),
        max_length=50,
        min_length=1,
        widget=widgets.TextInput(attrs={"placeholder": "*ign*"}),
    )
    geozones_type = forms.TypedChoiceField(
        choices=[
            (0, _("Ignore geofence(s)")),
            (1, _("Only trigger when within geofence(s)")),
        ],
        coerce=int,
        label=_("Geofence control"),
        help_text=_(
            "Select whether to ignore geofences or only trigger when within geofence(s)."
        ),
    )
    geozones_list = forms.CharField()
    realtime_only = forms.TypedChoiceField(
        choices=[
            (0, _("Recalculate historical data")),
            (1, _("Ignore historical data (real-time only)")),
        ],
        coerce=int,
        help_text=_(
            "Select whether to recalculate historical data on trigger."
        ),
        label=_("Real-time only"),
    )


class HealthCheckTriggerForm(forms.Form):
    healthy = forms.TypedChoiceField(
        choices=[
            (0, _("Ignore whether device is healthy")),
            (1, _("Trigger when device is healthy")),
        ],
        coerce=int,
        label=_("Healthy"),
    )
    unhealthy = forms.TypedChoiceField(
        choices=[
            (0, _("Ignore whether device is unhealthy")),
            (1, _("Trigger when device is unhealthy")),
        ],
        coerce=int,
        label=_("Unhealthy"),
    )
    needAttention = forms.TypedChoiceField(
        choices=[
            (0, _("Ignore whether device needs attention")),
            (1, _("Trigger when device needs attention")),
        ],
        coerce=int,
        label=_("Needs attention"),
    )
    triggerForEachIncident = forms.TypedChoiceField(
        choices=[
            (0, _("Ignore each incident")),
            (1, _("Trigger for each incident")),
        ],
        coerce=int,
        label=_("Trigger for each incident"),
    )


TRIGGER_FORMS_MAP = {
    WialonNotificationTrigger.GEOFENCE: GeofenceTriggerForm,
    WialonNotificationTrigger.ADDRESS: AddressTriggerForm,
    WialonNotificationTrigger.SPEED: SpeedTriggerForm,
    WialonNotificationTrigger.ALARM: AlarmTriggerForm,
    WialonNotificationTrigger.DIGITAL_INPUT: DigitalInputTriggerForm,
    WialonNotificationTrigger.PARAMETER: ParameterInAMessageTriggerForm,
    WialonNotificationTrigger.SENSOR: SensorValueTriggerForm,
    WialonNotificationTrigger.OUTAGE: ConnectionLossTriggerForm,
    WialonNotificationTrigger.SMS: SMSTriggerForm,
    WialonNotificationTrigger.INTERPOSITION: InterpositionTriggerForm,
    WialonNotificationTrigger.EXCESS: ExcessOfMessagesTriggerForm,
    WialonNotificationTrigger.ROUTE: RouteProgressTriggerForm,
    WialonNotificationTrigger.DRIVER: DriverTriggerForm,
    WialonNotificationTrigger.TRAILER: TrailerTriggerForm,
    WialonNotificationTrigger.MAINTENANCE: MaintenanceTriggerForm,
    WialonNotificationTrigger.FUEL_FILL: FuelFillingTriggerForm,
    WialonNotificationTrigger.FUEL_DRAIN: FuelDrainingTriggerForm,
    WialonNotificationTrigger.HEALTH: HealthCheckTriggerForm,
}
