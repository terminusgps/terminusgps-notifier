from django import forms


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

    """

    user_id = forms.IntegerField()
    unit_id = forms.IntegerField()
    message = forms.CharField(max_length=1024)
    msg_time_int = forms.IntegerField()
    dry_run = forms.BooleanField(initial=False, required=False)
    unit_name = forms.CharField(required=False)
    location = forms.CharField(required=False)


class WialonNotificationScheduleForm(forms.Form):
    f1 = forms.IntegerField(required=False)
    f2 = forms.IntegerField(required=False)
    t1 = forms.IntegerField(required=False)
    t2 = forms.IntegerField(required=False)
    m = forms.IntegerField(min_value=2**0, max_value=2**30, required=False)
    y = forms.IntegerField(min_value=2**0, max_value=2**11, required=False)
    w = forms.IntegerField(min_value=2**0, max_value=2**6, required=False)
