from terminusgps.aws.secrets import get_secret

secret: dict[str, str] = get_secret("terminusgps-site-live-env")
DEBUG = False
MERCHANT_AUTH_LOGIN_ID = secret.get("MERCHANT_AUTH_LOGIN_ID", "")
MERCHANT_AUTH_TRANSACTION_KEY = secret.get("MERCHANT_AUTH_TRANSACTION_KEY", "")
TWILIO_TOKEN = secret.get("TWILIO_TOKEN", "")
TWILIO_SID = secret.get("TWILIO_SID", "")
TWILIO_MESSAGING_SID = secret.get("TWILIO_MESSAGING_SID", "")
TWILIO_FROM_NUMBER = secret.get("TWILIO_FROM_NUMBER", "")
WIALON_TOKEN = secret.get("WIALON_TOKEN", "")
WIALON_ADMIN_ID = secret.get("WIALON_ADMIN_ID", "")
