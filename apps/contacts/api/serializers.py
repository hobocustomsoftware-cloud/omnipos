"""Contact serializers (B2C/B2B aware)."""

from __future__ import annotations

from contacts.customer_defaults import SYSTEM_WALK_IN_DISPLAY_NAME
from contacts.models import Customer
from rest_framework import serializers

# Counter capture when Flutter omits identity entirely (B2C drop-in label mirrors system anchor text).
DEFAULT_WALK_IN_DISPLAY_NAME = SYSTEM_WALK_IN_DISPLAY_NAME


class CustomerSerializer(serializers.ModelSerializer):
    """Nullable phone for retail drops; name optional until resolved in the view helper."""

    class Meta:
        model = Customer
        fields = (
            "id",
            "name",
            "phone",
            "email",
            "notes",
            "external_ref",
            "current_debt",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "current_debt", "created_at", "updated_at")
        extra_kwargs = {
            "phone": {"required": False, "allow_null": True, "allow_blank": True},
            "name": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "notes": {"required": False, "allow_blank": True},
            "external_ref": {"required": False, "allow_blank": True},
            "is_active": {"required": False},
        }


def resolve_counter_customer_identity(*, name: str | None, phone: str | None) -> tuple[str, str]:
    """Derive stored customer name and normalized phone for kiosk posts."""

    name_clean = (name or "").strip()
    phone_clean = "" if phone is None else str(phone).strip()

    if not name_clean and not phone_clean:
        return SYSTEM_WALK_IN_DISPLAY_NAME, ""

    if name_clean:
        return name_clean, phone_clean

    return phone_clean, phone_clean


CustomerQuickSerializer = CustomerSerializer
CustomerUpsertQuickSerializer = CustomerSerializer
