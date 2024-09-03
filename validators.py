import re


class ValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)


def validate_phone_number(value: str) -> None:
    """Returns value if it's a valid phone number, otherwise raises `ValidationError`."""
    pattern = re.compile(r"\+1\d\d\d\d\d\d\d\d\d\d", re.IGNORECASE)
    if not pattern.match(value):
        raise ValidationError("Invalid phone number.")


def validate_to_number(value: str) -> None:
    """Validates the 'to_number' parameter."""
    if "," in value:
        for number in value.split(","):
            validate_phone_number(number)
    else:
        validate_phone_number(value)
