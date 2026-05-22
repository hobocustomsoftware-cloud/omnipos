"""System-scoped anchors for OmniPOS countertop flows."""

from __future__ import annotations

from contacts.models import Customer

SYSTEM_WALK_IN_EXTERNAL_REF = "omnipos.system.walk_in_customer"
SYSTEM_WALK_IN_DISPLAY_NAME = "Walk-in Customer (လက်လီဝယ်သူ)"


def ensure_walk_in_customer(*, reopen_if_inactive: bool = True) -> Customer:
    """Lazy-create the canonical anonymous B2C customer row per tenant schema."""

    row = Customer.objects.filter(external_ref=SYSTEM_WALK_IN_EXTERNAL_REF).first()
    if row is not None:
        if reopen_if_inactive and not row.is_active:
            row.is_active = True
            row.save(update_fields=("is_active", "updated_at"))
        return row

    return Customer.objects.create(
        name=SYSTEM_WALK_IN_DISPLAY_NAME,
        phone="",
        email="",
        notes="",
        external_ref=SYSTEM_WALK_IN_EXTERNAL_REF,
        is_active=True,
    )
