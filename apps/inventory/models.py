"""Per-tenant SKU × branch on-hand quantities (kept separate from catalogue core)."""

from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from core.models import AbstractBaseModel


class ProductStock(AbstractBaseModel):
    """Branch-scoped quantity; keyed to catalog SKU + branch anchors.

    The physical PostgreSQL table name remains ``catalog_productstock`` for
    continuity with deployments that applied early ``catalog`` migrations.
    """

    branch = models.ForeignKey(
        "catalog.Branch",
        on_delete=models.CASCADE,
        related_name="product_stocks",
    )
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="branch_stocks",
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="On-hand amount in Product.base_uom_code units.",
    )

    class Meta:
        db_table = "catalog_productstock"
        constraints = (
            models.UniqueConstraint(
                fields=("branch", "product"),
                name="catalog_productstock_unique_branch_product",
            ),
        )

    def __str__(self) -> str:
        return f"{self.branch.code} / {self.product.sku} = {self.quantity}"
