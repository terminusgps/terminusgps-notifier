import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
ASGI_APPLICATION = "src.asgi.application"
AWS_PINPOINT_MAX_PRICE_SMS = os.getenv("AWS_PINPOINT_MAX_PRICE_SMS")
AWS_PINPOINT_MAX_PRICE_VOICE = os.getenv("AWS_PINPOINT_MAX_PRICE_VOICE")
AWS_PINPOINT_POOL_ARN = os.getenv("AWS_PINPOINT_POOL_ARN")
CSRF_COOKIE_SECURE = False
DEBUG = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
ROOT_URLCONF = "src.urls"
SECRET_KEY = "k_il7ce@&k-=n9zo+7_^^b4kb+k$7##aa&z#=3(s7jkc_w5j9l"
SESSION_COOKIE_SECURE = False
STATIC_URL = "static/"
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True
WIALON_TOKEN = os.getenv("WIALON_TOKEN")
WSGI_APPLICATION = "src.wsgi.application"
DOCS_ROOT = BASE_DIR / "docs" / "build" / "html"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "django.forms",
    "docs",
    "terminusgps_notifier.apps.TerminusgpsNotifierConfig",
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "DEBUG"},
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
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
