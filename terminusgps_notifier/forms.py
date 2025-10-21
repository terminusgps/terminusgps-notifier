from django import forms

from terminusgps_notifier.validators import validate_is_digit


class WialonUnitNotificationForm(forms.Form):
    """
    A form for dispatching Wialon unit notifications.

    Attributes:
        - unit_id: An 8-digit Wialon unit id for phone number lookup. Required.
        - user_id: A user id for Wialon API token retrieval. Required.
        - message: A 1024-character max message to dispatch. Required.
        - dry_run: Whether to dispatch the notification as a dry run. Optional.

    """

    unit_id = forms.CharField(
        min_length=8, max_length=8, validators=[validate_is_digit]
    )
    user_id = forms.CharField(max_length=8, validators=[validate_is_digit])
    message = forms.CharField(max_length=1024)
    dry_run = forms.BooleanField(required=False, initial=False)
