"""Payments and checkout artefacts (tenant-isolated PostgreSQL schemas)."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from catalog.models import Order
from core.models import AbstractBaseModel


class PaymentMethod(AbstractBaseModel):
    """Centrally provisioned tenders (cash, QR, ledger, …).

    Rows live in each tenant schema; seed/sync via SaaS tooling or admin APIs.
    When ``applicable_business_types`` is empty this method applies to **all**
    verticals tied to tenants in this schema instance.
    """

    code = models.CharField(max_length=64, db_index=True, unique=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True, db_index=True)
    applicable_business_types = models.ManyToManyField(
        "tenants.BusinessType",
        blank=True,
        related_name="applicable_payment_methods",
        help_text=(
            "Empty = GLOBAL (any tenant vertical). Otherwise only stores whose Client "
            "``business_type`` matches one of these tags may use this tender during checkout."
        ),
    )

    class Meta:
        ordering = ("code",)
        verbose_name = "Payment method"
        verbose_name_plural = "Payment methods"

    def __str__(self) -> str:
        return f"{self.code} ({self.name})"


class OrderPayment(AbstractBaseModel):
    """One tender line capturing part of settlement for :class:`~catalog.models.Order`."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, related_name="order_rows")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    transaction_ref = models.CharField(
        max_length=255,
        blank=True,
        help_text="Processor / reference id (approval code, PSP trace, …).",
    )
    tendered_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text=_("POS counter: amount the buyer handed over for this tender (often cash)."),
    )
    change_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text=_("Cash change returned; reconcile with tendered − amount."),
    )

    class Meta:
        ordering = ("created_at",)
        indexes = (models.Index(fields=("order", "payment_method")),)

    def __str__(self) -> str:
        return f"{self.order_id}:{self.payment_method.code}:{self.amount}"


class InvoiceFormat(models.TextChoices):
    """Default render channel for OmniPOS invoicing previews."""

    A4 = "A4", _("A4 / PDF-style company invoice")
    THERMAL = "THERMAL", _("POS thermal receipt")


class InvoiceSetting(AbstractBaseModel):
    """Per-tenant storefront / company stationery for receipts and invoices (admin-maintained)."""

    company_name = models.CharField(max_length=255)
    company_logo = models.ImageField(
        upload_to="sales/invoices/logos/%Y/%m/",
        blank=True,
        null=True,
        help_text=_("Printed on A4 payloads and referenced as URL when available."),
    )
    tax_identifier = models.CharField(max_length=128, blank=True, help_text=_("VAT / SSID / Tin (display only)."))
    registered_address = models.TextField(blank=True, help_text=_("Legal / trading address (multi-line plain text)."))
    contact_phone = models.CharField(max_length=64, blank=True)
    invoice_footer_note = models.TextField(
        blank=True,
        help_text=_("Disclaimer, bank details, or thank-you footer on formal invoices."),
    )
    default_format = models.CharField(
        max_length=16,
        choices=InvoiceFormat.choices,
        default=InvoiceFormat.A4,
        db_index=True,
        help_text=_("Suggested channel when callers omit explicit format."),
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "Invoice setting"
        verbose_name_plural = "Invoice settings"

    def __str__(self) -> str:
        return self.company_name
