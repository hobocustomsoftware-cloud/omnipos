"""Accounts app bootstrap hooks."""

from django.apps import AppConfig

_SIGNALS_REGISTERED = False


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Accounts"

    def ready(self) -> None:
        """Wire signals after Django discovers models."""

        global _SIGNALS_REGISTERED
        if _SIGNALS_REGISTERED:
            return

        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_save

        from .models import StaffProfile
        from .permissions import get_or_create_default_cashier_role

        def ensure_profile(sender, instance, created: bool, **kwargs) -> None:
            if not created:
                return
            default_role = get_or_create_default_cashier_role()
            StaffProfile.objects.get_or_create(
                user=instance,
                defaults={"role": default_role},
            )

        post_save.connect(ensure_profile, sender=get_user_model(), weak=False)
        _SIGNALS_REGISTERED = True
