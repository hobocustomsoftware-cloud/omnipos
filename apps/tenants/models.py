"""Public-schema tenancy models (PostgreSQL ``public``).

django-tenants persists ``Client`` (tenant row / schema anchor) together with
``Domain`` hostname bindings. Operational POS data belongs in TENANT_APPS — see
``catalog.models``.

``BusinessType`` rows are SaaS-managed from Django Admin and referenced by tenants
(unit scoping + UI presets) without hard-coded vertical enums.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django_tenants.models import DomainMixin, TenantMixin

from core.models import AbstractBaseModel


class BusinessType(AbstractBaseModel):
    """Super-admin manageable vertical preset (Welding, Retail, Pharmacy, …)."""

    code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Stable lowercase key (welding, retail, pharmacy, …).",
    )
    name = models.CharField(max_length=255)
    ui_schema = models.JSONField(
        blank=True,
        default=dict,
        help_text=(
            "Portable UI/layout payload consumed by OmniPOS Flutter (merged over built-in "
            "presets — e.g. layout_preset, product_form_sections). Empty {} defers entirely "
            "to coded fallbacks keyed by ``code``."
        ),
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("code",)
        verbose_name = _("Business type")
        verbose_name_plural = _("Business types")

    def __str__(self) -> str:
        return f"{self.code} ({self.name})"


class Client(TenantMixin):
    """SaaS tenant + PostgreSQL schema name (django-tenants TenantMixin).

    Lifecycle fields tie into subscription enforcement in application services —
    migrations remain schema-only per project workflow.
    """

    name = models.CharField(max_length=255)
    business_type = models.ForeignKey(
        BusinessType,
        on_delete=models.PROTECT,
        related_name="tenant_clients",
        help_text="Vertical driving catalogue units, presets, and partner UX divergences.",
    )
    subscription_plan = models.ForeignKey(
        "saas.SubscriptionPlan",
        on_delete=models.SET_NULL,
        related_name="tenants",
        blank=True,
        null=True,
    )
    custom_domain = models.CharField(
        max_length=253,
        unique=True,
        blank=True,
        null=True,
        help_text="Canonical branded hostname (mirror the ``Domain.is_primary=True`` row).",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Operational kill-switch before HTTP access middleware runs.",
    )
    paid_until = models.DateTimeField(blank=True, null=True)
    external_billing_customer_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="External CRM/customer identifier (Stripe customer id, etc.).",
    )

    auto_create_schema = True

    class Meta:
        ordering = ("schema_name",)
        verbose_name = "Tenant Client"
        verbose_name_plural = "Tenant Clients"

    def __str__(self) -> str:
        return self.name or self.schema_name


class Domain(DomainMixin):
    """Host → tenant mapping enforced by TenantMainMiddleware."""

    class Meta:
        verbose_name = "Tenant Domain"
        verbose_name_plural = "Tenant Domains"
