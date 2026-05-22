"""Catalog configuration + privileged mutation guards."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Count, Q

from accounts.permissions import user_can_manage_branch_pricing


def assert_user_may_modify_branch_price(user) -> None:
    if not user_can_manage_branch_pricing(user):
        raise PermissionDenied(
            "Only administrators or managers may edit branch-specific selling prices.",
        )


class CatalogConfigService:
    """Tenant-aware catalogue lookups (business-type filtered units, etc.)."""

    @staticmethod
    def get_applicable_units(tenant=None):  # type: ignore[no-untyped-def]
        """Return active :class:`~catalog.models.UnitOfMeasure` rows for ``tenant``.

        Units with **no** ``applicable_business_types`` behave as GLOBAL. Otherwise the
        unit applies when ``tenant.business_type`` is tagged (Many-to-many membership).
        Uses ``connection.tenant`` when ``tenant`` is omitted.
        """

        from catalog.models import UnitOfMeasure

        ctx = tenant if tenant is not None else getattr(connection, "tenant", None)
        bt_id = getattr(ctx, "business_type_id", None) if ctx is not None else None

        annotated = UnitOfMeasure.objects.filter(is_active=True).annotate(
            _business_tag_count=Count("applicable_business_types", distinct=True),
        )

        if not bt_id:
            return (
                annotated.filter(_business_tag_count=0)
                .order_by("code")
                .prefetch_related("applicable_business_types")
            )

        return (
            annotated.filter(
                Q(_business_tag_count=0) | Q(applicable_business_types__pk=bt_id),
            )
            .distinct()
            .order_by("code")
            .prefetch_related("applicable_business_types")
        )

    @staticmethod
    def get_ui_config_for_tenant(tenant=None):  # type: ignore[no-untyped-def]
        """Portable UI blueprint for Flutter: coded preset **merged** with ``BusinessType.ui_schema``."""

        ctx = tenant if tenant is not None else getattr(connection, "tenant", None)

        slug = ""
        bt = getattr(ctx, "business_type", None) if ctx is not None else None

        meta: dict[str, str | dict | None] = {
            "schema_name": None,
            "tenant_name": None,
            "business_type": None,
            "business_type_id": None,
            "business_type_name": None,
            "business_type_ui_schema": None,
        }
        if ctx is not None:
            if bt is not None:
                slug = str(getattr(bt, "code", "") or "").strip().lower()
            meta["schema_name"] = getattr(ctx, "schema_name", None)
            meta["tenant_name"] = getattr(ctx, "name", None)

            meta["business_type"] = slug or None
            if bt is not None:
                meta["business_type_id"] = str(getattr(bt, "pk", "") or "") or None
                meta["business_type_name"] = getattr(bt, "name", None) or None
                raw_schema = getattr(bt, "ui_schema", None)
                meta["business_type_ui_schema"] = raw_schema if isinstance(raw_schema, dict) else None

        preset = CatalogConfigService._ui_presets_for(slug)

        overrides: dict = {}
        if bt is not None:
            ui_schema_attr = getattr(bt, "ui_schema", None)
            if isinstance(ui_schema_attr, dict):
                overrides = ui_schema_attr

        merged: dict = {**preset, **overrides}
        merged["tenant"] = meta
        return merged

    @staticmethod
    def _ui_presets_for(business_slug: str) -> dict:
        generic_sections = CatalogConfigService._generic_product_sections()

        if business_slug == "workshop":
            return {
                "layout_preset": "workshop_service",
                "product_form_sections": generic_sections
                + [
                    {
                        "id": "aftermarket_labor",
                        "title": "Service / Workshop",
                        "field_keys": ["labor_estimate_hours", "service_notes_preview"],
                        "priority": "secondary",
                    },
                ],
                "pos_dashboard": {"tiles": ["open_jobs", "appointments"], "density": "comfortable"},
                "recommended_grids": ["variant_matrix", "time_blocks"],
            }
        if business_slug == "services":
            return {
                "layout_preset": "appointment_first",
                "product_form_sections": generic_sections
                + [
                    {
                        "id": "subscriptions",
                        "title": "Recurring Offers",
                        "field_keys": ["bundle_code", "term_length"],
                        "priority": "optional",
                    },
                ],
                "pos_dashboard": {"tiles": ["bookings"], "density": "comfortable"},
                "recommended_grids": ["packages"],
            }

        standardized = frozenset({"retail", "workshop", "services"})
        if not business_slug or business_slug == "retail":
            return CatalogConfigService._retail_preset(generic_sections)

        if business_slug not in standardized:
            return CatalogConfigService._vertical_adaptive_preset(business_slug, generic_sections)

        return CatalogConfigService._retail_preset(generic_sections)

    @staticmethod
    def _retail_preset(generic_sections):  # type: ignore[no-untyped-def]
        return {
            "layout_preset": "retail_inventory",
            "product_form_sections": generic_sections
            + [
                {
                    "id": "velocity",
                    "title": "Pricing & Moves",
                    "field_keys": [
                        "wholesale_price",
                        "wholesale_minimum_qty",
                        "track_inventory_toggle",
                    ],
                    "priority": "secondary",
                },
            ],
            "pos_dashboard": {"tiles": ["fast_movers", "alerts"], "density": "comfortable"},
            "recommended_grids": ["matrix_sku_variant", "price_ladder"],
        }

    @staticmethod
    def _vertical_adaptive_preset(slug: str, generic_sections):  # type: ignore[no-untyped-def]
        return {
            "layout_preset": f"{slug}_adaptive",
            "product_form_sections": generic_sections,
            "pos_dashboard": {"tiles": ["search", "favorites"], "density": "comfortable"},
            "recommended_grids": ["dense_list"],
            "vertical_hint": slug.upper(),
        }

    @staticmethod
    def _generic_product_sections():
        return [
            {
                "id": "identity",
                "title": "Core identity",
                "field_keys": [
                    "sku",
                    "barcode",
                    "name",
                    "base_price",
                    "base_uom_code",
                ],
                "priority": "primary",
            },
            {
                "id": "compliance_hints",
                "title": "Regulated overlays",
                "field_keys": [
                    "metadata.regulated.requires_expiry",
                    "metadata.electronics.warranty_months",
                ],
                "priority": "optional",
                "presentation": "chips",
            },
        ]


class CatalogScanService:
    """Resolve a POS/mobile scan identifier to :class:`~catalog.models.Product`.

    Matches (in order): ``Product.barcode``, ``Product.sku``,
    :class:`~catalog.models.ProductUnitConversion` ``barcode``, then ``alternate_sku``.
    """

    @staticmethod
    def resolve_product_from_scan(identifier: str):  # type: ignore[no-untyped-def]
        """Return ``Product`` or ``None`` when inactive / unknown."""

        from catalog.models import Product, ProductUnitConversion

        key = str(identifier).strip()
        if not key:
            return None

        product = (
            Product.objects.filter(is_active=True, barcode=key).first()
            or Product.objects.filter(is_active=True, sku=key).first()
        )
        if product is not None:
            return product

        conv = (
            ProductUnitConversion.objects.filter(is_active=True, barcode=key)
            .select_related("product")
            .first()
            or ProductUnitConversion.objects.filter(is_active=True, alternate_sku=key)
            .select_related("product")
            .first()
        )
        if conv is None:
            return None
        prod = conv.product
        return prod if prod.is_active else None
