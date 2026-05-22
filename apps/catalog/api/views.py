"""API views for catalog configuration (Flutter)."""

from __future__ import annotations

from datetime import datetime

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import (
    IsBranchEmployee,
    _branch_hint_request,
    _resolve_branch_uuid,
)
from catalog.api.serializers import ProductScanDetailSerializer, UnitOfMeasureSerializer
from catalog.models import Branch, Product
from catalog.services import CatalogConfigService, CatalogScanService
from sales.services import PricingEngineService


def _parse_last_sync_timestamp_param(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt



class CatalogConfigAPIView(APIView):
    """Single payload: merged UI preset + ``BusinessType.ui_schema`` + scoped units."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def get(self, request):  # type: ignore[no-untyped-def]
        tenant = getattr(request, "tenant", None) or getattr(connection, "tenant", None)

        ui_config = CatalogConfigService.get_ui_config_for_tenant(tenant)
        queryset = CatalogConfigService.get_applicable_units(tenant=tenant)
        applicable_units = UnitOfMeasureSerializer(queryset, many=True).data

        return Response(
            {
                "ui_config": ui_config,
                "applicable_units": applicable_units,
            },
        )


class ProductScanAPIView(APIView):
    """Resolve barcode / SKU (+ optional alternate conversion codes), return branch-priced preview."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def get(self, request):  # type: ignore[no-untyped-def]
        params = getattr(request, "query_params", request.GET)
        raw_code = params.get("barcode") or params.get("sku")
        if raw_code is None or str(raw_code).strip() == "":
            return Response(
                {"detail": "Provide a barcode or sku query parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            qty = PricingEngineService._coerce_quantity(params.get("quantity", 1))  # type: ignore[attr-defined]
        except DjangoValidationError as exc:
            msgs = getattr(exc, "messages", None) or [str(exc)]
            detail = msgs[0] if len(msgs) == 1 else list(msgs)
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        product = CatalogScanService.resolve_product_from_scan(str(raw_code))
        if product is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        branch: Branch | None = None
        hint = _branch_hint_request(request)
        if hint:
            branch_uuid = _resolve_branch_uuid(hint)
            if branch_uuid is not None:
                branch = Branch.objects.filter(pk=branch_uuid, is_active=True).first()
                if branch is None and not (
                    getattr(request.user, "is_superuser", False) or getattr(request.user, "is_staff", False)
                ):
                    return Response(
                        {"detail": "Branch was not found or inactive."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

        calculated_unit_price = PricingEngineService.resolve_unit_price(
            product=product,
            quantity=qty,
            branch=branch,
        )
        total_price = PricingEngineService.compute_order_total(
            lines=[{"quantity": qty, "unit_price": calculated_unit_price}],
        )

        return Response(
            {
                "product": ProductScanDetailSerializer(product).data,
                "quantity": qty,
                "calculated_unit_price": calculated_unit_price,
                "total_price": total_price,
            },
        )


class CatalogIncrementalSyncAPIView(APIView):
    """Product catalogue delta sync for offline-first mobiles (pull since ``last_synced_at``)."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def get(self, request):  # type: ignore[no-untyped-def]
        params = getattr(request, "query_params", request.GET)
        raw_anchor = params.get("last_synced_at")

        qs = Product.objects.all().order_by("updated_at", "pk")
        anchor_applied: str | None = None

        if raw_anchor is not None and str(raw_anchor).strip() != "":
            try:
                cutoff = _parse_last_sync_timestamp_param(str(raw_anchor))
            except (ValueError, TypeError):
                return Response(
                    {"detail": "Invalid last_synced_at; use ISO-8601 (e.g. 2026-05-01T08:30:00+06:30 or ...Z)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = qs.filter(updated_at__gt=cutoff)
            anchor_applied = str(raw_anchor).strip()

        return Response(
            {
                "products": ProductScanDetailSerializer(qs, many=True).data,
                "last_synced_at_requested": anchor_applied,
                "sync_generated_at": timezone.now().isoformat(),
            },
        )
