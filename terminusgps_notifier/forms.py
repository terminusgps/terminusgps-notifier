from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_is_digit(value: str) -> None:
    if not value.isdigit():
        raise ValidationError(
            _("Value must be a digit, got '%(value)s'."),
            code="invalid",
            params={"value": value},
        )


class WialonUnitNotificationForm(forms.Form):
    unit_id = forms.CharField(max_length=8, validators=[validate_is_digit])
    message = forms.CharField(max_length=2048)
