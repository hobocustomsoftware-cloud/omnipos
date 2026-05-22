"""Tenant-schema catalog replicated per django-tenants PostgreSQL schema.

Each tenant receives isolated ``catalog_*`` tables. ``Product.metadata`` is the
PostgreSQL JSONB-backed extension surface for vertically specific attributes
(expiry/traceability, warranty/serials, unit conversion dictionaries) without
forking relational columns per industry.
"""

from __future__ import annotations

from typing import Any

from django.core.validators import MinValueValidator
from django.db import models

from core.models import AbstractBaseModel


class OrderStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONFIRMED = "confirmed", "Confirmed"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class UnitOfMeasure(AbstractBaseModel):
    """Super-admin curated units surfaced per tenant via ``BusinessType`` tags (M2M)."""

    code = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Stable unit token (EA, PCS, BOT, KG, …) used alongside Product inventory math.",
    )
    label = models.CharField(max_length=128, blank=True, help_text="Human label for POS/UI (optional).")
    applicable_business_types = models.ManyToManyField(
        "tenants.BusinessType",
        blank=True,
        related_name="tagged_units_of_measure",
        help_text=(
            "Leave empty for GLOBAL units visible to **all** tenants. "
            "Otherwise only tenants whose primary BusinessType is among these tags "
            "will see this unit."
        ),
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return f"{self.code}" + (f" ({self.label})" if self.label else "")


class Branch(AbstractBaseModel):
    """Physical or logical fulfilment endpoint for omnichannel POS."""

    code = models.CharField(
        max_length=64,
        help_text="Short identifier unique inside the active tenant.",
    )
    name = models.CharField(max_length=255)
    address = models.JSONField(blank=True, default=dict)
    timezone = models.CharField(max_length=64, default="UTC")
    is_active = models.BooleanField(default=True, db_index=True)
    settings = models.JSONField(
        blank=True,
        default=dict,
        help_text="Branch-local UX/POS payloads (kitchen routing, receipts, printers, etc.).",
    )

    class Meta:
        ordering = ("code",)
        constraints = (
            models.UniqueConstraint(fields=("code",), name="catalog_branch_code_unique_per_tenant"),
        )

    def __str__(self) -> str:
        return f"{self.code}: {self.name}"


class Product(AbstractBaseModel):
    """Universal SKU with JSONB metadata for heterogeneous verticals.

    ``base_price`` is the default **retail** (per-unit) list price; ``wholesale_price``
    applies when sell quantity meets ``wholesale_minimum_qty`` (business rules live
    in services/API). Canonical stock/sell math must continue to honour
    ``base_uom_code``.
    Secondary facts (regulated handling, aftermarket warranties, ad-hoc conversions)
    live inside ``metadata`` using an informal, versioned contract:

    * ``schema_version`` (``int``, recommended): Bump when rewriting structures.
    * ``regulated`` (``dict``, optional): Medical/traceability knobs such as
      ``requires_expiry``, ``batch_tracked``, ``default_shelf_life_days``.
    * ``electronics`` (``dict``, optional): Aftermarket metadata such as
      ``warranty_months``, ``serial_tracked``, ``imei_tracked``.
    * ``units`` (``dict``, optional): Structured conversion payloads, e.g.::

          {
              "base": "EA",
              "conversions": [
                  {"uom": "PACK", "to_base": 6},
                  {"uom": "CASE", "to_base": 72},
              ]
          }

    Services/workflows should coerce unknown keys gracefully and serialize via the
    ORM JSONField backed by PostgreSQL JSONB indexes when query patterns emerge.
    """

    SCHEMA_VERSION_KEY = "schema_version"
    METADATA_REGULATED = "regulated"
    METADATA_ELECTRONICS = "electronics"
    METADATA_UNITS = "units"

    sku = models.CharField(max_length=128)
    barcode = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Scanned barcode (GTIN/custom); omit when unused. Unique per tenant.",
    )
    name = models.CharField(max_length=255)
    base_uom_code = models.CharField(
        max_length=32,
        help_text="Canonical stocking/selling unit (EA, KG, etc.).",
    )
    base_uom_precision = models.DecimalField(
        blank=True,
        null=True,
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(0)],
    )
    track_inventory = models.BooleanField(default=True)
    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Default retail unit price before branch overrides (see ProductBranchSettings).",
        validators=[MinValueValidator(0)],
    )
    wholesale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        help_text="Wholesale unit price when quantity rules are satisfied (see wholesale_minimum_qty).",
    )
    wholesale_minimum_qty = models.PositiveIntegerField(
        default=1,
        help_text="Minimum units on a line/order to qualify for wholesale_price logic.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSONB-backed extension layer (regulated, electronics, unit conversions …).",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("sku",)
        constraints = (
            models.UniqueConstraint(fields=("sku",), name="catalog_product_sku_unique_per_tenant"),
        )

    def __str__(self) -> str:
        return f"{self.sku} ({self.name})"

    def metadata_schema_version(self) -> int | None:
        raw = (self.metadata or {}).get(self.SCHEMA_VERSION_KEY)
        return int(raw) if isinstance(raw, int) else None

    def regulated_facets(self) -> dict[str, Any]:
        data = (self.metadata or {}).get(self.METADATA_REGULATED)
        return data if isinstance(data, dict) else {}

    def electronics_facets(self) -> dict[str, Any]:
        data = (self.metadata or {}).get(self.METADATA_ELECTRONICS)
        return data if isinstance(data, dict) else {}

    def unit_declarations(self) -> dict[str, Any]:
        data = (self.metadata or {}).get(self.METADATA_UNITS)
        return data if isinstance(data, dict) else {}


class ProductUnitConversion(AbstractBaseModel):
    """Alternate barcode/SKU resolving to a base product (packs, partner codes, aliases)."""

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="unit_conversions",
    )
    barcode = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Alternate GTIN / scan code (unique within tenant schema when set).",
    )
    alternate_sku = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text="Alternate SKU or pack code (unique when non-blank — see constraint).",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Product unit conversion"
        verbose_name_plural = "Product unit conversions"
        constraints = (
            models.UniqueConstraint(
                fields=("alternate_sku",),
                condition=~models.Q(alternate_sku=""),
                name="catalog_productunitconversion_alternate_sku_unique_when_set",
            ),
        )

    def __str__(self) -> str:
        alias = self.barcode or self.alternate_sku or str(self.pk)
        return f"{alias}→{self.product.sku}"


class ProductBranchSettings(AbstractBaseModel):
    """Branch-scoped catalogue flags and optional pricing overrides."""

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="product_overrides")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="branch_settings")
    is_sellable = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this SKU can be surfaced in POS/UI for this branch.",
    )
    branch_selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Override list price per branch; falls back to ``Product.base_price`` when null.",
    )

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("branch", "product"),
                name="catalog_productbranchsettings_unique_branch_product",
            ),
        )

    def __str__(self) -> str:
        return f"{self.branch.code}->{self.product.sku}"

    @property
    def effective_selling_price(self):
        """Resolved sell price respecting branch overrides."""

        if self.branch_selling_price is None:
            return self.product.base_price
        return self.branch_selling_price


class Order(AbstractBaseModel):
    """Sales order header anchored to the fulfilling branch.

    Lines capture priced snapshots via ``OrderItem``; totals can be aggregated in
    services or deferred to reporting.

    The primary key is a UUID (see ``core.models.AbstractBaseModel``): mobile clients may
    pass ``id`` when inserting offline-first payloads so handset-generated identifiers
    are preserved without collisions (``default=uuid.uuid4`` applies only when omitted).

    ``created_by`` records which authenticated staff member posted the sale (set only by
    the server from ``request.user`` in checkout / bulk-sync).
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(
        max_length=16,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    inventory_committed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="When True, branch stock was reduced for this order; cleared after cancel restores.",
    )
    customer = models.ForeignKey(
        "contacts.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="orders",
        help_text="Buyer for AR tracking (required when tenders include CREDIT).",
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = (
            models.Index(fields=("branch", "status")),
        )

    def __str__(self) -> str:
        return f"Order {self.pk} ({self.branch.code})"


class OrderItem(AbstractBaseModel):
    """Priced line on an order (unit_price snapshot at time of sale)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(0)],
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Snapshot unit price charged (retail vs wholesale resolved upstream).",
    )

    class Meta:
        ordering = ("created_at",)
        indexes = (
            models.Index(fields=("order",)),
            models.Index(fields=("product",)),
        )

    def __str__(self) -> str:
        return f"{self.order_id}: {self.product.sku} x {self.quantity}"

    @property
    def line_total(self):
        """Convenience; not persisted."""

        return self.quantity * self.unit_price
