"""SaaS models in the public schema (subscription plans, payment logs)."""

from django.apps import AppConfig


class SaasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "saas"
    verbose_name = "SaaS"

