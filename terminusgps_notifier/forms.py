from django import forms

from terminusgps_notifier.validators import validate_is_digit


class WialonUnitNotificationForm(forms.Form):
    unit_id = forms.CharField(
        min_length=8, max_length=8, validators=[validate_is_digit]
    )
    message = forms.CharField(max_length=2048)
