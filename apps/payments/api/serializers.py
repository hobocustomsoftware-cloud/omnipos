"""DRF serializers for payments/KYC endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from core.models import IntegrationScope
from payments.models import MerchantKYCApplication, TenantPaymentGateway

_SENSITIVE_KEY_FRAGMENTS = ("private_key", "secret", "password", "token")


def scrub_sensitive_credentials(payload: Any) -> Any:
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, val in payload.items():
            lk = str(key).lower()
            if any(fragment in lk for fragment in _SENSITIVE_KEY_FRAGMENTS):
                continue
            out[str(key)] = scrub_sensitive_credentials(val)
        return out
    if isinstance(payload, list):
        return [scrub_sensitive_credentials(item) for item in payload]
    return payload


class ClientSafePaymentGatewaySerializer(serializers.ModelSerializer):
    payment_method_id = serializers.UUIDField(source="payment_method.pk", read_only=True)
    code = serializers.CharField(source="payment_method.code", read_only=True)
    name = serializers.CharField(source="payment_method.name", read_only=True)

    class Meta:
        model = TenantPaymentGateway
        fields = (
            "payment_method_id",
            "code",
            "name",
            "scope",
            "merchant_id",
            "public_key",
            "api_extra_credentials",
        )
        read_only_fields = fields

    def to_representation(self, instance):  # type: ignore[override]
        data = super().to_representation(instance)
        raw_extra = data.get("api_extra_credentials")
        data["api_extra_credentials"] = scrub_sensitive_credentials(
            raw_extra if isinstance(raw_extra, dict) else {},
        )
        return data


class MerchantKYCApplicationSerializer(serializers.ModelSerializer):
    """Read-only client snapshot (no private documents or reviewer notes)."""

    class Meta:
        model = MerchantKYCApplication
        fields = (
            "id",
            "scope",
            "status",
            "legal_name",
            "trading_name",
            "registration_number",
            "tax_identifier",
            "contact_email",
            "contact_phone",
            "registered_address",
            "documents_requested",
            "manual_submission",
            "instant_qr_metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def to_representation(self, instance):  # type: ignore[override]
        data = super().to_representation(instance)
        for key in ("manual_submission", "instant_qr_metadata"):
            raw = data.get(key)
            data[key] = scrub_sensitive_credentials(raw if isinstance(raw, dict) else {})
        return data


class KYCSubmissionSerializer(serializers.Serializer):
    scope = serializers.ChoiceField(choices=IntegrationScope.choices)
    legal_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    trading_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    registration_number = serializers.CharField(max_length=128, required=False, allow_blank=True)
    tax_identifier = serializers.CharField(max_length=128, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=64, required=False, allow_blank=True)
    registered_address = serializers.JSONField(required=False, default=dict)
    manual_submission = serializers.JSONField(required=False, default=dict)
    document_nrc = serializers.FileField(required=False, allow_empty_file=False)
    document_license = serializers.FileField(required=False, allow_empty_file=False)
