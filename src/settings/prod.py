import os
from pathlib import Path
from socket import gethostbyname, gethostname

import requests


def get_public_ip() -> str | None:
    try:
        response = requests.get("https://checkip.amazonaws.com/")
        return response.text.removesuffix("\n")
    except Exception:
        return


BASE_DIR = Path(__file__).resolve().parent.parent

ALLOWED_HOSTS = [
    ".terminusgps.com",
    ".elb.amazonaws.com",
    gethostbyname(gethostname()),
]
if public_ip := get_public_ip():
    ALLOWED_HOSTS.append(public_ip)
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
ROOT_URLCONF = "src.urls"
SECRET_KEY = os.getenv("SECRET_KEY")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
STATIC_URL = "static/"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True
USE_X_FORWARDED_HOST = True
WIALON_TOKEN = os.getenv("WIALON_TOKEN")
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
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        }
    },
    "loggers": {
        "django": {"handlers": ["console"], "propagate": True},
        "terminusgps_notifier": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
    },
}


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CACHES = {
    "default": {
        "ENGINE": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379",
        "TIMEOUT": 60 * 3,
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.forms",
    "terminusgps_notifier.apps.TerminusgpsNotifierConfig",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
    }
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
