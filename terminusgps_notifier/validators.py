from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_is_digit(value: str) -> None:
    if not value.isdigit():
        raise ValidationError(
            _("Value must be a digit, got '%(value)s'."),
            code="invalid",
            params={"value": value},
        )
