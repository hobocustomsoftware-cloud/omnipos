"""Django settings for OmniPOS (django-tenants, PostgreSQL)."""

import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

_APPS_ROOT = BASE_DIR / "apps"
if str(_APPS_ROOT) not in sys.path:
    sys.path.insert(0, str(_APPS_ROOT))

import os

from django.templatetags.static import static
from django.utils.translation import gettext_lazy as _


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-dev-key-change-before-production")

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in {"1", "true", "yes"}

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")


SHARED_APPS = [
    "django_tenants",
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "tenants",
    "saas",
    "payments",
]

TENANT_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "unfold",
    "django.contrib.admin",
    "core",
    "accounts",
    "contacts",
    "accounting",
    "catalog",
    "inventory",
    "sales",
    "payments",
]

INSTALLED_APPS = list(dict.fromkeys(SHARED_APPS + TENANT_APPS))

MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": os.environ.get("PGDATABASE", "omnipos"),
        "USER": os.environ.get("PGUSER", "postgres"),
        "PASSWORD": os.environ.get("PGPASSWORD", "351994"),
        "HOST": os.environ.get("PGHOST", "localhost"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }
}

DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Yangon"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PUBLIC_SCHEMA_NAME = "public"

TENANT_MODEL = "tenants.Client"

TENANT_DOMAIN_MODEL = "tenants.Domain"

SHOW_PUBLIC_IF_NO_TENANT_FOUND = True


# -----------------------------------------------------------------------------
# UNFOLD["STYLES"]: Unfold only accepts stylesheet URLs (<link>). Tailwind-style
# utilities are implemented as plain CSS in static/admin/css/omnipos_unfold.css:
#   • bg-gradient-to-br from-[#450a0a] via-black to-black fixed (body canvas)
#   • Sidebar bg-black/40 backdrop-blur-2xl border-white/10
#   • Nav: space-y-4 + px-4; links py-3 rounded-lg
#   • text-white + text-red-400 accents (no text-gray-*)
#   • App pills: bg-red-600/20 text-red-500 border-red-500/30 uppercase tracking-widest
#   • Hover red-500/10 + text-white • Active gradient + border-l-4 + shadow glow
#   • Tables: thead black/80 • rows white/[0.02] hover/[0.05]
# -----------------------------------------------------------------------------
UNFOLD = {
    "SITE_TITLE": _("OmniPOS Admin"),
    "SITE_HEADER": _("OmniPOS"),
    "SITE_SUBHEADER": _("Operations Console"),
    "THEME": "dark",
    "SHOW_UI_WARNINGS": False,
    "COLORS": {
        # Accent ladder — deep brand red (#991b1b) through scarlet highlights.
        "primary": {
            "50": "#fef2f2",
            "100": "#fee2e2",
            "200": "#fecaca",
            "300": "#fca5a5",
            "400": "#f87171",
            "500": "#991b1b",
            "600": "#b91c1c",
            "700": "#dc2626",
            "800": "#7f1d1d",
            "900": "#450a0a",
            "950": "#000000",
        },
        # Surfaces: black / near-black / white — avoids slate/zinc grays in dark chrome.
        "base": {
            "50": "#ffffff",
            "100": "#fafafa",
            "200": "#e8e8e8",
            "300": "#cfcfcf",
            "400": "#a8a8a8",
            "500": "#737373",
            "600": "#525252",
            "700": "#3a3a3a",
            "800": "#242424",
            "900": "#121212",
            "950": "#000000",
        },
        # Typography: pure white / near-white only (sidebar + chrome inherit via CSS overrides).
        "font": {
            "subtle-light": "#ffffff",
            "subtle-dark": "#ffffff",
            "default-light": "#ffffff",
            "default-dark": "#ffffff",
            "important-light": "#ffffff",
            "important-dark": "#ffffff",
        },
    },
    "STYLES": [
        lambda request: static(
            "admin/css/omnipos_unfold.css",
        ),
    ],
}


REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

TEST_RUNNER = "config.test_runner.OmniPOSTenantTestRunner"
