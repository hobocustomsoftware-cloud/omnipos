"""Public-schema SaaS models (PostgreSQL ``public`` via django-tenants SHARED_APPS).

This module owns **subscription commercial terms** (``SubscriptionPlan``) and
**provider-agnostic payment observability** (``PaymentLog``).

Tenant routing and tenant rows live under ``tenants.models`` alongside
``Domain`` mappings.
"""

from django.conf import settings
from django.db import models

from core.models import AbstractBaseModel


class SubscriptionPlan(AbstractBaseModel):
    """Commercial tier surfaced at signup/billing time with enforced limits."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    max_products = models.PositiveIntegerField(
        help_text="Hard cap per tenant catalog. Use 0 to mean unlimited.",
    )
    max_branches = models.PositiveIntegerField(
        help_text="Hard cap on active branches/locations per tenant. 0 means unlimited.",
    )
    max_staff = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Optional cap on staff identities. Blank means unlimited.",
    )
    billing_interval = models.CharField(
        max_length=16,
        blank=True,
        help_text="Suggested interval label (month, year); upstream billing owns truth.",
    )
    is_public = models.BooleanField(
        default=True,
        help_text="Whether this tier is visible on self-serve signup/purchase journeys.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive tiers cannot be assigned to freshly provisioned tenants.",
    )

    class Meta:
        ordering = ("slug",)

    def __str__(self) -> str:
        return self.name


class PaymentLog(AbstractBaseModel):
    """Normalized provider feed for SaaS invoicing reconciliation (PCI-light payload only)."""

    tenant = models.ForeignKey(
        settings.TENANT_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="payment_logs",
    )
    provider = models.CharField(
        max_length=64,
        help_text="Processor identifier such as stripe, paddle, manual.",
    )
    event_type = models.CharField(
        max_length=128,
        help_text="Normalized event token (for example invoice_paid).",
    )
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Dedup anchor for webhooks/commands (provider-scoped uniqueness).",
    )
    external_object_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="External invoice/session/charge identifier.",
    )
    status = models.CharField(max_length=32, default="received")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
    )
    currency = models.CharField(max_length=3, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    recorded_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Provider-observed timestamp when available.",
    )

    class Meta:
        indexes = (
            models.Index(fields=("tenant", "created_at")),
            models.Index(fields=("provider", "external_object_id")),
        )

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_type}:{self.external_object_id or ''}"
