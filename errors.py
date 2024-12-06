class InvalidTwilioMethodError(Exception):
    """Raised when an invalid Twilio method is supplied to a TwilioCaller instance."""


class InvalidPhoneNumber(Exception):
    """Raised when a phone number is invalid for use with the Twilio API."""
