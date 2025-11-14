import os
import sys
from pathlib import Path
from socket import gethostbyname, gethostname

from terminusgps.authorizenet.constants import Environment, ValidationMode
from terminusgps.wialon.flags import TokenFlag

BASE_DIR = Path(__file__).resolve().parent.parent

ALLOWED_HOSTS = [
    ".terminusgps.com",
    ".elb.amazonaws.com",
    gethostbyname(gethostname()),
]
ASGI_APPLICATION = "src.asgi.application"
AWS_PINPOINT_CONFIGURATION_ARN = os.getenv("AWS_PINPOINT_CONFIGURATION_ARN")
AWS_PINPOINT_MAX_PRICE_SMS = os.getenv("AWS_PINPOINT_MAX_PRICE_SMS")
AWS_PINPOINT_MAX_PRICE_VOICE = os.getenv("AWS_PINPOINT_MAX_PRICE_VOICE")
AWS_PINPOINT_POOL_ARN = os.getenv("AWS_PINPOINT_POOL_ARN")
AWS_PINPOINT_PROTECT_ID = os.getenv("AWS_PINPOINT_PROTECT_ID")
CSRF_COOKIE_SECURE = True
DEBUG = False
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
MERCHANT_AUTH_ENVIRONMENT = Environment.PRODUCTION
MERCHANT_AUTH_LOGIN_ID = os.getenv("MERCHANT_AUTH_LOGIN_ID")
MERCHANT_AUTH_TRANSACTION_KEY = os.getenv("MERCHANT_AUTH_TRANSACTION_KEY")
MERCHANT_AUTH_VALIDATION_MODE = ValidationMode.LIVE
ROOT_URLCONF = "src.urls"
SECRET_KEY = os.getenv("SECRET_KEY")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
STATIC_URL = "static/"
TIME_ZONE = "US/Central"
USE_I18N = True
USE_TZ = True
USE_X_FORWARDED_HOST = True
WIALON_RESOURCE_NAME = "Terminus GPS Notifications"
WIALON_TOKEN_ACCESS_TYPE = (
    TokenFlag.VIEW_ACCESS
    | TokenFlag.MANAGE_NONSENSITIVE
    | TokenFlag.MANAGE_SENSITIVE
)
WSGI_APPLICATION = "src.wsgi.application"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": "test" in sys.argv,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s [%(process)d] [%(module)s] [%(levelname)s] %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S%z]",
            "class": "logging.Formatter",
        },
        "simple": {
            "format": "%(asctime)s [%(levelname)s] %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S%z]",
            "class": "logging.Formatter",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "console_verbose": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "terminusgps_notifier": {
            "handlers": ["console_verbose"],
            "level": os.getenv("NOTIFIER_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "HOST": os.getenv("DB_HOST"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "PORT": os.getenv("DB_PORT", 5432),
        "OPTIONS": {"client_encoding": "UTF8"},
        "CONN_MAX_AGE": None,
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379",
        "TIMEOUT": 60 * 5,
    }
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
