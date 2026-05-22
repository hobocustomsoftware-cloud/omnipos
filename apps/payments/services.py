"""Payment / KYC provisioning helpers (shared with REST surface)."""

from __future__ import annotations

from django.db import connection

from core.models import IntegrationScope
from payments.models import TenantPaymentGateway


def payment_method_allowed_for_tenant(payment_method, business_type_id) -> bool:
    scoped = payment_method.applicable_business_types.all()
    if not scoped.exists():
        return True
    if business_type_id is None:
        return False
    return scoped.filter(pk=business_type_id).exists()


class PaymentProvisioningService:
    """Flutter-safe gateway manifest (no ``secret_key``, scrubbed JSON extras)."""

    @staticmethod
    def build_client_safe_payment_manifest(*, tenant=None) -> list[dict]:
        from payments.api.serializers import ClientSafePaymentGatewaySerializer

        ctx = tenant if tenant is not None else getattr(connection, "tenant", None)
        bt_id = getattr(ctx, "business_type_id", None) if ctx is not None else None

        qs = (
            TenantPaymentGateway.objects.filter(
                is_enabled=True,
                payment_method__is_active=True,
                scope=IntegrationScope.POS,
            )
            .select_related("payment_method")
            .prefetch_related("payment_method__applicable_business_types")
            .order_by("payment_method__code")
        )

        rows: list[dict] = []
        for gw in qs:
            pm = gw.payment_method
            if not payment_method_allowed_for_tenant(pm, bt_id):
                continue
            rows.append(ClientSafePaymentGatewaySerializer(instance=gw).data)
        return rows
