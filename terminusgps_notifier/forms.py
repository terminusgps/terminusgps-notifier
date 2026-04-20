from django import forms
from django.db import models
from django.utils.translation import gettext_lazy as _


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
        coerce=int,
        choices=[
            ("0", _("Form boundaries for current value")),
            ("1", _("Form boundaries for previous value")),
        ],
    )
    merge = (
        forms.TypedChoiceField(
            coerce=int,
            choices=[
                ("0", _("Calculate separately")),
                ("1", _("Sum up values")),
            ],
        ),
    )
    reversed = forms.TypedChoiceField(
        coerce=int,
        choices=[
            ("0", _("Trigger within range")),
            ("1", _("Trigger outside range")),
        ],
    )
    geozone_ids = forms.CharField()
    type = forms.TypedChoiceField(
        coerce=int,
        choices=[
            ("0", _("Trigger on geofence entry")),
            ("1", _("Trigger on geofence exit")),
        ],
    )
    min_speed = forms.IntegerField(min_value=0, max_value=255)
    max_speed = forms.IntegerField(min_value=0, max_value=255)
    include_lbs = forms.TypedChoiceField(
        coerce=int,
        choices=[
            ("0", _("Do not process LBS messages")),
            ("1", _("Process LBS messages")),
        ],
    )
    lo = forms.ChoiceField(choices=[("AND", _("AND")), ("OR", _("OR"))])


class AddressTriggerForm(forms.Form):
    sensor_type = forms.CharField()
    sensor_name_mask = forms.CharField()
    lower_bound = forms.FloatField()
    upper_bound = forms.FloatField()
    prev_msg_diff = forms.TypedChoiceField()
    merge = forms.TypedChoiceField()
    reversed = forms.TypedChoiceField()
    radius = forms.IntegerField()
    type = forms.TypedChoiceField()
    min_speed = forms.IntegerField()
    max_speed = forms.IntegerField()
    country = forms.CharField()
    region = forms.CharField()
    city = forms.CharField()
    street = forms.CharField()
    house = forms.CharField()
    include_lbs = forms.TypedChoiceField()


class SpeedTriggerForm(forms.Form):
    lower_bound = forms.FloatField()
    max_speed = forms.IntegerField()
    merge = forms.TypedChoiceField()
    min_speed = forms.IntegerField()
    prev_msg_diff = forms.TypedChoiceField()
    reversed = forms.TypedChoiceField()
    sensor_name_mask = forms.CharField()
    sensor_type = forms.CharField()
    upper_bound = forms.FloatField()
    driver = forms.TypedChoiceField()


class AlarmTriggerForm(forms.Form):
    pass


class DigitalInputTriggerForm(forms.Form):
    input_index = forms.IntegerField()
    type = forms.TypedChoiceField()


class ParameterInAMessageTriggerForm(forms.Form):
    kind = forms.TypedChoiceField()
    lower_bound = forms.FloatField()
    param = forms.CharField()
    text_mask = forms.CharField()
    type = forms.TypedChoiceField()
    upper_bound = forms.FloatField()


class SensorValueTriggerForm(forms.Form):
    lower_bound = forms.FloatField()
    merge = forms.TypedChoiceField()
    prev_msg_diff = forms.TypedChoiceField()
    sensor_name_mask = forms.CharField()
    sensor_type = forms.CharField()
    type = forms.TypedChoiceField()
    upper_bound = forms.FloatField()


class ConnectionLossTriggerForm(forms.Form):
    time = forms.IntegerField()
    type = forms.TypedChoiceField()
    include_lbs = forms.TypedChoiceField()
    check_restore = forms.TypedChoiceField()
    geozones_type = forms.TypedChoiceField()
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
    include_lbs = forms.TypedChoiceField()
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
