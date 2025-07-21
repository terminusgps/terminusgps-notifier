import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DEBUG", False)

ALLOWED_HOSTS = [".terminusgps.com"] if not DEBUG else ["localhost", "127.0.0.1"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
ROOT_URLCONF = "src.urls"
SECRET_KEY = os.getenv("SECRET_KEY")
TIME_ZONE = "America/Chicago"
USE_I18N = True
USE_TZ = True
WSGI_APPLICATION = "src.wsgi.application"

INSTALLED_APPS = ["terminusgps_notifier.apps.TerminusgpsNotifierApp"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "django.middleware.csrf.CsrfViewMiddleware",
    # "django.contrib.auth.middleware.AuthenticationMiddleware",
    # "django.contrib.messages.middleware.MessageMiddleware",
    # "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
