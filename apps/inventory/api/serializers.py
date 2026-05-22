"""Serial shapes for OmniPOS inbound inventory endpoints."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from contacts.models import Supplier
from sales.services import PricingEngineService


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = (
            "id",
            "name",
            "phone",
            "email",
            "notes",
            "tax_identifier",
            "current_payable",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "current_payable", "created_at")


class PurchaseReceiptLineSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4)
    unit_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"))

    def validate_quantity(self, value: Decimal) -> Decimal:  # type: ignore[override]
        q = PricingEngineService._coerce_quantity(value).quantize(Decimal("0.0001"))  # type: ignore[attr-defined]
        if q <= Decimal("0"):
            raise serializers.ValidationError("quantity must exceed zero.")
        return q


class PurchaseOrderCreateSerializer(serializers.Serializer):
    supplier_id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    settlement_mode = serializers.ChoiceField(choices=("cash", "credit"))
    reference_number = serializers.CharField(required=False, default="", max_length=128, allow_blank=True)
    notes = serializers.CharField(required=False, default="", allow_blank=True)
    lines = PurchaseReceiptLineSerializer(many=True, min_length=1)
