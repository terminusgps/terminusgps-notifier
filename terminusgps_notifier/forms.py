import datetime

from django import forms
from django.db import models
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


class CreateNotificationForm(forms.Form):
    itemId = forms.IntegerField()
    nm = forms.CharField(min_length=4)
    txt = forms.CharField(max_length=1024)
    ta = forms.DateTimeField(required=False)
    td = forms.DateTimeField(required=False)
    ma = forms.IntegerField(min_value=0)
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
    )
    cdt = forms.IntegerField(min_value=0, max_value=1800)
    mast = forms.IntegerField(min_value=0, max_value=86400)
    mpst = forms.IntegerField(min_value=0, max_value=86400)
    cp = forms.TypedChoiceField(
        choices=[
            (0, _("Any time")),
            (60, _("Last minute")),
            (600, _("Last 10 minutes")),
            (3600, _("Last hour")),
            (86400, _("Last day")),
        ],
        coerce=int,
    )
    fl = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger on first message")),
            (1, _("Trigger on every message")),
            (2, _("Disabled")),
        ],
        coerce=int,
    )
    tz = forms.TypedChoiceField(choices=constants.TIMEZONES, coerce=int)
    la = forms.ChoiceField(choices=[("en", _("English"))])
    un = forms.JSONField()
    sch = forms.JSONField(required=False)
    ctrl_sch = forms.JSONField(required=False)
    trg = forms.JSONField()
    act = forms.JSONField()

    def clean_sch(self):
        if self.cleaned_data["sch"] is None:
            return {"f1": 0, "f2": 0, "t1": 0, "t2": 0, "m": 0, "w": 0, "y": 0}

    def clean_ctrl_sch(self):
        if self.cleaned_data["ctrl_sch"] is None:
            return {"f1": 0, "f2": 0, "t1": 0, "t2": 0, "m": 0, "w": 0, "y": 0}

    def clean_ta(self):
        if ta := self.cleaned_data["ta"]:
            return int(datetime.datetime.timestamp(ta))
        else:
            return 0

    def clean_td(self):
        if td := self.cleaned_data["td"]:
            return int(datetime.datetime.timestamp(td))
        else:
            return 0

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data:
            cleaned_data["callMode"] = "create"
            cleaned_data["id"] = 0


class NotificationScheduleForm(forms.Form):
    f1 = forms.DateTimeField(required=False)
    f2 = forms.DateTimeField(required=False)
    t1 = forms.DateTimeField(required=False)
    t2 = forms.DateTimeField(required=False)
    w = forms.TypedMultipleChoiceField(
        choices=[
            (2**0, _("Monday")),
            (2**1, _("Tuesday")),
            (2**2, _("Wednesday")),
            (2**3, _("Thursday")),
            (2**4, _("Friday")),
            (2**5, _("Saturday")),
            (2**6, _("Sunday")),
        ],
        coerce=int,
        required=False,
    )
    y = forms.TypedMultipleChoiceField(
        choices=[
            (2**0, _("January")),
            (2**1, _("Febuary")),
            (2**2, _("March")),
            (2**3, _("April")),
            (2**4, _("May")),
            (2**5, _("June")),
            (2**6, _("July")),
            (2**7, _("August")),
            (2**8, _("September")),
            (2**9, _("October")),
            (2**10, _("November")),
            (2**11, _("December")),
        ],
        coerce=int,
        required=False,
    )
    m = forms.TypedMultipleChoiceField(
        choices=[
            (2**0, _("1")),
            (2**1, _("2")),
            (2**2, _("3")),
            (2**3, _("4")),
            (2**4, _("5")),
            (2**5, _("6")),
            (2**6, _("7")),
            (2**7, _("8")),
            (2**8, _("9")),
            (2**9, _("10")),
            (2**10, _("11")),
            (2**11, _("12")),
            (2**12, _("13")),
            (2**13, _("14")),
            (2**14, _("15")),
            (2**15, _("16")),
            (2**16, _("17")),
            (2**17, _("18")),
            (2**18, _("19")),
            (2**19, _("20")),
            (2**20, _("21")),
            (2**21, _("22")),
            (2**22, _("23")),
            (2**23, _("24")),
            (2**24, _("25")),
            (2**25, _("26")),
            (2**26, _("27")),
            (2**27, _("28")),
            (2**28, _("29")),
            (2**29, _("30")),
            (2**30, _("31")),
        ],
        coerce=int,
        required=False,
    )

    def clean_f1(self):
        if f1 := self.cleaned_data["f1"]:
            return int(datetime.datetime.timestamp(f1))
        return 0

    def clean_f2(self):
        if f2 := self.cleaned_data["f2"]:
            return int(datetime.datetime.timestamp(f2))
        return 0

    def clean_t1(self):
        if t1 := self.cleaned_data["t1"]:
            return int(datetime.datetime.timestamp(t1))
        return 0

    def clean_t2(self):
        if t2 := self.cleaned_data["t2"]:
            return int(datetime.datetime.timestamp(t2))
        return 0

    def clean_m(self):
        if m := self.cleaned_data["m"]:
            return sum(m)
        return 0

    def clean_y(self):
        if y := self.cleaned_data["y"]:
            return sum(y)
        return 0

    def clean_w(self):
        if w := self.cleaned_data["w"]:
            return sum(w)
        return 0


class NotificationTriggerForm(forms.Form):
    t = forms.ChoiceField(choices=WialonNotificationTrigger.choices)
    p = forms.JSONField()


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


class GeofenceTriggerForm(forms.Form):
    sensor_type = forms.ChoiceField(choices=WialonSensorType.choices)
    sensor_name_mask = forms.CharField(min_length=1)
    lower_bound = forms.FloatField()
    upper_bound = forms.FloatField()
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
    )
    merge = (
        forms.TypedChoiceField(
            choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
            coerce=int,
        ),
    )
    reversed = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger within range")),
            (1, _("Trigger outside range")),
        ],
        coerce=int,
    )
    geozone_ids = forms.CharField()
    type = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger on geofence entry")),
            (1, _("Trigger on geofence exit")),
        ],
        coerce=int,
    )
    min_speed = forms.IntegerField(min_value=0, max_value=255)
    max_speed = forms.IntegerField(min_value=0, max_value=255)
    include_lbs = forms.TypedChoiceField(
        choices=[
            (0, _("Do not process LBS messages")),
            (1, _("Process LBS messages")),
        ],
        coerce=int,
    )
    lo = forms.ChoiceField(choices=[("AND", _("AND")), ("OR", _("OR"))])


class AddressTriggerForm(forms.Form):
    sensor_type = forms.ChoiceField(choices=WialonSensorType.choices)
    sensor_name_mask = forms.CharField()
    lower_bound = forms.FloatField(step_size=0.1)
    upper_bound = forms.FloatField(step_size=0.1)
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
    )
    merge = (
        forms.TypedChoiceField(
            choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
            coerce=int,
        ),
    )
    reversed = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger within range")),
            (1, _("Trigger outside range")),
        ],
        coerce=int,
    )
    radius = forms.IntegerField(min_value=1)
    type = forms.TypedChoiceField(
        choices=[
            (0, _("Control within radius")),
            (1, _("Control outside radius")),
        ],
        coerce=int,
    )
    min_speed = forms.IntegerField(max_value=255)
    max_speed = forms.IntegerField(max_value=255)
    country = forms.CharField(required=False)
    region = forms.CharField(required=False)
    city = forms.CharField(required=False)
    street = forms.CharField(required=False)
    house = forms.CharField(required=False)
    include_lbs = forms.TypedChoiceField(
        choices=[
            (0, _("Do not process LBS messages")),
            (1, _("Process LBS messages")),
        ],
        coerce=int,
    )


class SpeedTriggerForm(forms.Form):
    lower_bound = forms.FloatField(step_size=0.1)
    max_speed = forms.IntegerField(max_value=255)
    merge = (
        forms.TypedChoiceField(
            choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
            coerce=int,
        ),
    )
    min_speed = forms.IntegerField(max_value=255)
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
    )
    reversed = forms.TypedChoiceField(
        choices=[
            (0, _("Trigger within range")),
            (1, _("Trigger outside range")),
        ],
        coerce=int,
    )
    sensor_name_mask = forms.CharField()
    sensor_type = forms.ChoiceField(choices=WialonSensorType.choices)
    upper_bound = forms.FloatField(step_size=0.1)
    driver = forms.TypedChoiceField(
        choices=[
            (0, _("Ignore driver assignment")),
            (1, _("Trigger when no driver assigned")),
            (2, _("Trigger only when driver assigned")),
        ],
        coerce=int,
    )


class AlarmTriggerForm(forms.Form):
    pass


class DigitalInputTriggerForm(forms.Form):
    input_index = forms.IntegerField(min_value=1, max_value=32)
    type = forms.TypedChoiceField(
        choices=[
            (0, _("Check for activation")),
            (1, _("Check for deactivation")),
        ],
        coerce=int,
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
    )
    lower_bound = forms.FloatField(step_size=0.1)
    param = forms.CharField()
    text_mask = forms.CharField()
    type = forms.TypedChoiceField(
        choices=[(0, _("Within range")), (1, _("Outside range"))], coerce=int
    )
    upper_bound = forms.FloatField(step_size=0.1)


class SensorValueTriggerForm(forms.Form):
    lower_bound = forms.FloatField(step_size=0.1)
    merge = forms.TypedChoiceField(
        choices=[(0, _("Calculate separately")), (1, _("Sum up values"))],
        coerce=int,
    )
    prev_msg_diff = forms.TypedChoiceField(
        choices=[
            (0, _("Form boundaries for current value")),
            (1, _("Form boundaries for previous value")),
        ],
        coerce=int,
    )
    sensor_name_mask = forms.CharField()
    sensor_type = forms.ChoiceField(choices=WialonSensorType.choices)
    type = forms.TypedChoiceField(
        choices=[(0, _("Within range")), (1, _("Outside range"))], coerce=int
    )
    upper_bound = forms.FloatField(step_size=0.1)


class ConnectionLossTriggerForm(forms.Form):
    time = forms.IntegerField()
    type = forms.TypedChoiceField(
        choices=[(0, _("Coordinates Loss")), (1, _("Connection Loss"))],
        coerce=int,
    )
    include_lbs = forms.TypedChoiceField(
        choices=[
            (0, _("Do not process LBS messages")),
            (1, _("Process LBS messages")),
        ],
        coerce=int,
    )
    check_restore = forms.TypedChoiceField(
        choices=[
            (0, _("Connection Lost")),
            (1, _("Connection Lost and Restored")),
            (2, _("Connection Restored")),
        ],
        coerce=int,
    )
    geozones_type = forms.TypedChoiceField(
        choices=[(0, _("Out of Geofence")), (1, _("Within Geofence"))],
        coerce=int,
    )
    geozones_list = forms.CharField()


class SMSTriggerForm(forms.Form):
    mask = forms.CharField()


class InterpositionTriggerForm(forms.Form):
    sensor_name_mask = forms.CharField()
    sensor_type = forms.CharField()
    lower_bound = forms.FloatField()
    upper_bound = forms.FloatField()
    merge = forms.TypedChoiceField()
    max_speed = forms.IntegerField()
    min_speed = forms.IntegerField()
    reversed = forms.TypedChoiceField()
    prev_msg_diff = forms.TypedChoiceField()
    radius = forms.IntegerField()
    type = forms.TypedChoiceField()
    unit_guids = forms.CharField()
    include_lbs = forms.TypedChoiceField(
        choices=[
            (0, _("Do not process LBS messages")),
            (1, _("Process LBS messages")),
        ],
        coerce=int,
    )
    lo = forms.ChoiceField()


class ExcessOfMessagesTriggerForm(forms.Form):
    flags = forms.TypedChoiceField()
    msgs_limit = forms.IntegerField()
    time_offset = forms.IntegerField(max_value=86400)


class RouteProgressTriggerForm(forms.Form):
    mask = forms.CharField()
    round_mask = forms.CharField()
    schedule_mask = forms.CharField()
    types = forms.CharField()


class DriverTriggerForm(forms.Form):
    driver_code_mask = forms.CharField()
    flags = forms.TypedChoiceField()


class TrailerTriggerForm(forms.Form):
    driver_code_mask = forms.CharField()
    flags = forms.TypedChoiceField()


class MaintenanceTriggerForm(forms.Form):
    days = forms.IntegerField()
    engine_hours = forms.IntegerField()
    flags = forms.IntegerField()
    mask = forms.CharField()
    mileage = forms.IntegerField()
    val = forms.TypedChoiceField()


class FuelFillingTriggerForm(forms.Form):
    sensor_name_mask = forms.CharField()
    geozones_type = forms.TypedChoiceField()
    geozones_list = forms.CharField()
    realtime_only = forms.TypedChoiceField()


class FuelDrainingTriggerForm(forms.Form):
    sensor_name_mask = forms.CharField()
    geozones_type = forms.TypedChoiceField()
    geozones_list = forms.CharField()
    realtime_only = forms.TypedChoiceField()


class HealthCheckTriggerForm(forms.Form):
    healthy = forms.TypedChoiceField()
    unhealthy = forms.TypedChoiceField()
    needAttention = forms.TypedChoiceField()
    triggerForEachIncident = forms.TypedChoiceField()


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


def get_trigger_form_fields() -> list[str]:
    fields = []
    for form_cls in TRIGGER_FORMS_MAP.values():
        form = form_cls()
        fields.extend(form.fields)
    return fields
