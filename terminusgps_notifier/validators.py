from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

__all__ = ["validate_e164_phone_number"]


def validate_e164_phone_number(value: str) -> None:
    """Raises :py:exec:`~django.core.exceptions.ValidationError` if the value wasn't a properly formatted E.164 phone number."""
    if not value.startswith("+"):
        raise ValidationError(
            _("E.164 phone number must start with a '+', got '%(char)s'"),
            code="invalid",
            params={"char": value[0]},
        )
    if not value.removeprefix("+").isdigit():
        raise ValidationError(
            _(
                "E.164 phone number must be entirely digits following '+', got '%(value)s'"
            ),
            code="invalid",
            params={"value": value.removeprefix("+")},
        )
    if len(value.removeprefix("+")) > 15:
        raise ValidationError(
            _(
                "E.164 phone number cannot be greater than 15 characters in length, got %(len)s."
            ),
            code="invalid",
            params={"len": len(value.removeprefix("+"))},
        )
