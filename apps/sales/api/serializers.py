"""Request/response shapes for POS checkout endpoints."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from catalog.models import OrderStatus
from contacts.customer_defaults import ensure_walk_in_customer
from contacts.models import Customer
from sales.services import PricingEngineService


class CheckoutLineSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4)

    def validate_quantity(self, value: Decimal):  # type: ignore[override]
        qty = PricingEngineService._coerce_quantity(value).quantize(Decimal("0.0001"))  # type: ignore[attr-defined]
        if qty <= Decimal("0"):
            raise serializers.ValidationError("quantity must exceed zero.")
        return qty


class CheckoutPaymentSerializer(serializers.Serializer):
    """Settlement line — identify tender by ``payment_method_id`` **or** ``payment_method_code`` (not both)."""

    payment_method_id = serializers.UUIDField(required=False, allow_null=True)
    payment_method_code = serializers.CharField(required=False, allow_blank=True, max_length=64)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"))
    tendered_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default=Decimal("0.00"),
        min_value=Decimal("0"),
    )
    change_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        default=Decimal("0.00"),
        min_value=Decimal("0"),
    )
    transaction_ref = serializers.CharField(required=False, default="", max_length=255, allow_blank=True)

    def validate(self, attrs):  # type: ignore[override]
        from sales.models import PaymentMethod

        pid = attrs.get("payment_method_id")
        raw_code = attrs.get("payment_method_code")
        code_str = (raw_code or "").strip()

        pid_ok = pid is not None

        if pid_ok and code_str:
            raise serializers.ValidationError(
                {"payment_method_code": "Provide only one of payment_method_id or payment_method_code."},
            )
        if not pid_ok and not code_str:
            raise serializers.ValidationError(
                {"payment_method_id": "Either payment_method_id or payment_method_code is required."},
            )

        if pid_ok:
            method = PaymentMethod.objects.filter(pk=pid, is_active=True).first()
            if method is None:
                raise serializers.ValidationError({"payment_method_id": "Payment method not found or inactive."})
        else:
            method = PaymentMethod.objects.filter(code__iexact=code_str, is_active=True).first()
            if method is None:
                raise serializers.ValidationError(
                    {"payment_method_code": f"Unknown tender code {code_str!r}."},
                )

        attrs["payment_method_id"] = method.pk
        attrs.pop("payment_method_code", None)

        amt = PricingEngineService._quantize_money(attrs["amount"])
        if amt is None or amt < Decimal("0"):
            raise serializers.ValidationError({"amount": "amount must be zero or greater (quantized)."})
        attrs["amount"] = amt

        t_raw = attrs.get("tendered_amount", Decimal("0.00"))
        c_raw = attrs.get("change_amount", Decimal("0.00"))
        t_q = PricingEngineService._quantize_money(t_raw)
        c_q = PricingEngineService._quantize_money(c_raw)
        attrs["tendered_amount"] = t_q if t_q is not None else Decimal("0.00")
        attrs["change_amount"] = c_q if c_q is not None else Decimal("0.00")

        if attrs["tendered_amount"] > Decimal("0") or attrs["change_amount"] > Decimal("0"):
            cash_net = PricingEngineService._quantize_money(attrs["tendered_amount"] - attrs["change_amount"])
            assert cash_net is not None
            if cash_net != amt:
                raise serializers.ValidationError(
                    {
                        "tendered_amount": (
                            "tendered_amount minus change_amount must equal amount for this tender line."
                        ),
                    },
                )

        return attrs


class CheckoutRequestSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    notes = serializers.CharField(required=False, default="", allow_blank=True)
    items = CheckoutLineSerializer(many=True, min_length=1)
    payments = CheckoutPaymentSerializer(many=True, min_length=1)
    customer_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):  # type: ignore[override]
        from sales.models import PaymentMethod

        payments = attrs.get("payments") or []
        mids = [p["payment_method_id"] for p in payments]
        cmap = {pk: (c or "").strip().upper() for pk, c in PaymentMethod.objects.filter(pk__in=mids).values_list("pk", "code")}
        for p in payments:
            if cmap.get(p["payment_method_id"], "") == "CREDIT" and attrs.get("customer_id") is None:
                raise serializers.ValidationError(
                    {"customer_id": "CREDIT tender requires customer_id referencing a Customer row."},
                )
        cid = attrs.get("customer_id")
        if cid is not None:
            if not Customer.objects.filter(pk=cid).exists():
                raise serializers.ValidationError({"customer_id": "Unknown customer UUID."})
        else:
            attrs["customer_id"] = ensure_walk_in_customer().pk
        return attrs


class BulkSyncOrderLineSerializer(serializers.Serializer):
    """Priced line snapshot from offline POS (trusted unit_price at sale time)."""

    product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=14, decimal_places=4)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_quantity(self, value: Decimal):  # type: ignore[override]
        qty = PricingEngineService._coerce_quantity(value).quantize(Decimal("0.0001"))  # type: ignore[attr-defined]
        if qty <= Decimal("0"):
            raise serializers.ValidationError("quantity must exceed zero.")
        return qty

    def validate_unit_price(self, value: Decimal):  # type: ignore[override]
        amt = PricingEngineService._quantize_money(value)  # type: ignore[attr-defined]
        if amt is None or amt < Decimal("0"):
            raise serializers.ValidationError("unit_price must be zero or greater.")
        return amt


class BulkSyncOrderSerializer(serializers.Serializer):
    """Single offline-first order envelope for bulk replay (Flutter → backend)."""

    id = serializers.UUIDField()
    branch_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=OrderStatus.choices, default=OrderStatus.CONFIRMED)
    notes = serializers.CharField(required=False, default="", allow_blank=True)
    customer_id = serializers.UUIDField(required=False, allow_null=True)
    lines = BulkSyncOrderLineSerializer(many=True, min_length=1)
    payments = serializers.ListField(
        child=CheckoutPaymentSerializer(),
        required=False,
        default=list,
    )

    def validate(self, attrs):  # type: ignore[override]
        from sales.models import PaymentMethod

        payments = list(attrs.get("payments") or [])
        if payments:
            mids = [p["payment_method_id"] for p in payments]
            cmap = {pk: (c or "").strip().upper() for pk, c in PaymentMethod.objects.filter(pk__in=mids).values_list("pk", "code")}
            for p in payments:
                if cmap.get(p["payment_method_id"], "") == "CREDIT" and attrs.get("customer_id") is None:
                    raise serializers.ValidationError(
                        {"customer_id": "CREDIT tender requires customer_id referencing a Customer row."},
                    )

        cid = attrs.get("customer_id")
        if cid is not None:
            if not Customer.objects.filter(pk=cid).exists():
                raise serializers.ValidationError({"customer_id": "Unknown customer UUID."})
        else:
            attrs["customer_id"] = ensure_walk_in_customer().pk
        return attrs
