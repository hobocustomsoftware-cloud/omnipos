"""Serializers for accounting HTTP surfaces."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers


class CustomerDebtSettlementSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    settlement_amount = serializers.DecimalField(max_digits=16, decimal_places=2)

    def validate_settlement_amount(self, value: Decimal) -> Decimal:  # type: ignore[override]
        if value <= Decimal("0"):
            raise serializers.ValidationError("Must be greater than zero.")
        return value
