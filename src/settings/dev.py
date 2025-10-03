import os
from pathlib import Path

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
ROOT_URLCONF = "src.urls"
SECRET_KEY = "k_il7ce@&k-=n9zo+7_^^b4kb+k$7##aa&z#=3(s7jkc_w5j9l"
SESSION_COOKIE_SECURE = False
STATIC_URL = "static/"
TIME_ZONE = "US/Central"
USE_I18N = True
USE_TZ = True
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
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.forms",
    "terminusgps_notifier.apps.TerminusgpsNotifierConfig",
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
