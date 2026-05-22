"""Customer / supplier master data with running balance anchors for ledger sync."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import AbstractBaseModel


class PurchaseSettlement(models.TextChoices):
    """How the storefront funded this supplier receipt."""

    CASH = "cash", _("Cash / paid at receipt")
    CREDIT = "credit", _("On supplier AP (increases current_payable)")


class Customer(AbstractBaseModel):
    """Storefront buyer; ``current_debt`` tracks AR owed on CREDIT tenders."""

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=64, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    external_ref = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text="Optional POS / ERP customer key.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    current_debt = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Rolling balance owed by customer (AUDIT snapshot; derive from DebtLedgerEntry for truth)."),
    )

    class Meta:
        ordering = ("name",)
        indexes = (models.Index(fields=("name",), name="contacts_cust_name_idx"),)

    def __str__(self) -> str:
        return self.name


class Supplier(AbstractBaseModel):
    """Vendor payable anchor for purchase-side debt ledgers."""

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=64, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    tax_identifier = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    current_payable = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Rolling amount owed to supplier (snapshot; reconcile via ledger postings)."),
    )

    class Meta:
        ordering = ("name",)
        indexes = (models.Index(fields=("name",), name="contacts_sup_name_idx"),)

    def __str__(self) -> str:
        return self.name


class PurchaseOrder(AbstractBaseModel):
    """Supplier receipt header; lines live in ``PurchaseOrderLine``."""

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    branch = models.ForeignKey(
        "catalog.Branch",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        null=True,
        blank=True,
        help_text=_("Receiving branch whose stock ledger is incremented."),
    )
    settlement_mode = models.CharField(
        max_length=16,
        choices=PurchaseSettlement.choices,
        default=PurchaseSettlement.CASH,
        db_index=True,
    )
    reference_number = models.CharField(max_length=128, blank=True, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.reference_number or self.pk} ({self.supplier})"


class PurchaseOrderLine(AbstractBaseModel):
    """SKU line on an inbound receipt (priced snapshot at receive time)."""

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
    )
    unit_cost = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )

    class Meta:
        ordering = ("created_at",)
        indexes = (models.Index(fields=("purchase_order", "product")),)

    def __str__(self) -> str:
        return f"{self.purchase_order_id}:{self.product_id}"
