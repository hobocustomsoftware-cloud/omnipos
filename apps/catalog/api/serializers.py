"""Serializers for catalog REST endpoints (Flutter / mobile)."""

from rest_framework import serializers

from catalog.models import Product, UnitOfMeasure
from tenants.models import BusinessType


class BusinessTypeTagSerializer(serializers.ModelSerializer):
    """Minimal business-type projection for tagging units (id, code, name)."""

    class Meta:
        model = BusinessType
        fields = ("id", "code", "name")
        read_only_fields = fields


class UnitOfMeasureSerializer(serializers.ModelSerializer):
    applicable_business_types = BusinessTypeTagSerializer(many=True, read_only=True)

    class Meta:
        model = UnitOfMeasure
        fields = (
            "id",
            "code",
            "label",
            "applicable_business_types",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProductScanDetailSerializer(serializers.ModelSerializer):
    """Product payload returned with POS/mobile scan preview pricing."""

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "barcode",
            "name",
            "base_uom_code",
            "base_uom_precision",
            "track_inventory",
            "base_price",
            "wholesale_price",
            "wholesale_minimum_qty",
            "metadata",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
