"""Debt ledger primitives (tenant-scoped; pairs with contacts balance snapshots)."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import AbstractBaseModel


class PartyType(models.TextChoices):
    CUSTOMER = "customer", _("Customer (AR)")
    SUPPLIER = "supplier", _("Supplier (AP)")


class DebtLedgerEntry(AbstractBaseModel):
    """Normalized double-column movement for buyer AR / seller AP narratives."""

    party_type = models.CharField(max_length=16, choices=PartyType.choices, db_index=True)
    customer = models.ForeignKey(
        "contacts.Customer",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="debt_ledger_entries",
    )
    supplier = models.ForeignKey(
        "contacts.Supplier",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payable_ledger_entries",
    )
    order = models.ForeignKey(
        "catalog.Order",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="debt_ledger_entries",
        help_text="POS sales order linkage (customer AR).",
    )
    purchase_order = models.ForeignKey(
        "contacts.PurchaseOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="debt_ledger_entries",
        help_text="Purchase-side linkage (supplier AP) when postings exist.",
    )
    order_payment = models.OneToOneField(
        "sales.OrderPayment",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="debt_ledger_entry",
        help_text="At most one ledger row per tender line (replay deletes cascade).",
    )
    debit_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Increases owed balance for the focal party convention used in OmniPOS postings.",
    )
    credit_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Reliefs / payments applied on account.",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = (
            models.Index(fields=("party_type", "created_at")),
            models.Index(fields=("customer", "created_at")),
            models.Index(fields=("supplier", "created_at")),
            models.Index(fields=("order", "created_at")),
        )

    def __str__(self) -> str:
        return f"{self.party_type} D{self.debit_amount} C{self.credit_amount}"
