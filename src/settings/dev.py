import base64
import os
from pathlib import Path

from terminusgps.authorizenet.constants import Environment, ValidationMode
from terminusgps.wialon.flags import TokenFlag

BASE_DIR = Path(__file__).resolve().parent.parent

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
ASGI_APPLICATION = "src.asgi.application"
AWS_PINPOINT_CONFIGURATION_ARN = os.getenv("AWS_PINPOINT_CONFIGURATION_ARN")
AWS_PINPOINT_MAX_PRICE_SMS = os.getenv("AWS_PINPOINT_MAX_PRICE_SMS")
AWS_PINPOINT_MAX_PRICE_VOICE = os.getenv("AWS_PINPOINT_MAX_PRICE_VOICE")
AWS_PINPOINT_POOL_ARN = os.getenv("AWS_PINPOINT_POOL_ARN")
AWS_PINPOINT_PROTECT_ID = os.getenv("AWS_PINPOINT_PROTECT_ID")
CSRF_COOKIE_SECURE = False
DEBUG = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
MERCHANT_AUTH_ENVIRONMENT = Environment.SANDBOX
MERCHANT_AUTH_LOGIN_ID = os.getenv("MERCHANT_AUTH_LOGIN_ID")
MERCHANT_AUTH_TRANSACTION_KEY = os.getenv("MERCHANT_AUTH_TRANSACTION_KEY")
MERCHANT_AUTH_VALIDATION_MODE = ValidationMode.TEST
DJANGO_ENCRYPTED_FIELD_ALGORITHM = os.getenv(
    "DJANGO_ENCRYPTED_FIELD_ALGORITHM", "SS20"
)
DJANGO_ENCRYPTED_FIELD_KEY = base64.b64decode(
    os.getenv("DJANGO_ENCRYPTED_FIELD_KEY", "")
)
ROOT_URLCONF = "src.urls"
SECRET_KEY = "k_il7ce@&k-=n9zo+7_^^b4kb+k$7##aa&z#=3(s7jkc_w5j9l"
SESSION_COOKIE_SECURE = False
STATIC_URL = "static/"
TIME_ZONE = "US/Central"
USE_I18N = True
USE_TZ = True
WIALON_TOKEN_ACCESS_TYPE = (
    TokenFlag.VIEW_ACCESS
    | TokenFlag.MANAGE_NONSENSITIVE
    | TokenFlag.MANAGE_SENSITIVE
)
WIALON_RESOURCE_NAME = "Terminus GPS Notifications"
WSGI_APPLICATION = "src.wsgi.application"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{asctime} {levelname}] {message}",
            "style": "{",
        },
        "verbose": {
            "format": "[{asctime} {levelname}] {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "loggers": {
        "django": {"handlers": ["console"], "propagate": True},
        "django.request": {"handlers": ["console"], "propagate": True},
        "terminusgps_notifier": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/home/blake/Projects/terminusgps-notifications/src/db.sqlite3",
    }
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.admindocs",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.forms",
    "terminusgps_payments.apps.TerminusgpsPaymentsConfig",
    "terminusgps_notifications.apps.TerminusgpsNotificationsConfig",
    "terminusgps_notifier.apps.TerminusgpsNotifierConfig",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
