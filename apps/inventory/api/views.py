"""Receiving / procurement REST helpers."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBranchEmployee, _branch_hint_request, _resolve_branch_uuid
from catalog.models import Branch, Product
from contacts.models import PurchaseOrder, PurchaseOrderLine, PurchaseSettlement, Supplier
from inventory.api.serializers import (
    PurchaseOrderCreateSerializer,
    SupplierSerializer,
)
from inventory.receiving_service import StockReceivingService
from sales.services import PricingEngineService


def _quantize_money(v: Decimal) -> Decimal | None:
    return PricingEngineService._quantize_money(v)  # type: ignore[attr-defined]


class SupplierListCreateAPIView(APIView):
    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def get(self, request):  # type: ignore[no-untyped-def]
        params = getattr(request, "query_params", request.GET)
        qs = Supplier.objects.filter(is_active=True).order_by("name")

        raw_phone = params.get("phone")
        if isinstance(raw_phone, str) and raw_phone.strip():
            qs = qs.filter(phone__icontains=raw_phone.strip())

        return Response({"results": SupplierSerializer(qs, many=True).data})

    def post(self, request):  # type: ignore[no-untyped-def]
        ser = SupplierSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        row = ser.save(current_payable=Decimal("0.00"))
        return Response(SupplierSerializer(row).data, status=status.HTTP_201_CREATED)


class PurchaseOrderCreateAPIView(APIView):
    """Inbound PO: persist lines + stock; ``credit`` settlement bumps ``Supplier.current_payable``."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def post(self, request):  # type: ignore[no-untyped-def]
        inbound = PurchaseOrderCreateSerializer(data=request.data)
        inbound.is_valid(raise_exception=True)
        data = inbound.validated_data

        elevated = getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False)
        branch_hint = _resolve_branch_uuid(_branch_hint_request(request))
        if not elevated:
            if branch_hint is None or branch_hint != data["branch_id"]:
                return Response(
                    {"detail": "branch_id body must match the scoped X-Branch-Id / branch_id parameter."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        settlement = PurchaseSettlement(data["settlement_mode"])
        try:
            with transaction.atomic():
                branch = Branch.objects.select_for_update().filter(pk=data["branch_id"], is_active=True).first()
                if branch is None:
                    raise DRFValidationError({"branch_id": ["Branch inactive or unknown."]})

                supplier = (
                    Supplier.objects.select_for_update()
                    .filter(pk=data["supplier_id"], is_active=True)
                    .first()
                )
                if supplier is None:
                    raise DRFValidationError({"supplier_id": ["Supplier inactive or unknown."]})

                product_ids = {ln["product_id"] for ln in data["lines"]}
                products = Product.objects.select_for_update().filter(pk__in=product_ids).in_bulk(product_ids)

                missing = sorted({str(x) for x in product_ids} - {str(k) for k in products})
                if missing:
                    raise DRFValidationError({"lines": [f"Unknown product ids: {', '.join(missing)}"]})

                line_payload: list[dict] = []
                grand_acc = Decimal("0")
                for ln in data["lines"]:
                    pid = ln["product_id"]
                    prod = products[pid]
                    if not prod.is_active:
                        raise DRFValidationError(
                            {"lines": [f"Product inactive SKU={prod.sku!r}."]},
                        )

                    qty = ln["quantity"]
                    unit = _quantize_money(ln["unit_cost"])
                    assert unit is not None

                    lt = PricingEngineService._quantize_money(qty * unit)  # type: ignore[attr-defined]
                    assert lt is not None
                    grand_acc += lt
                    line_payload.append({"product_id": pid, "product": prod, "quantity": qty, "unit_cost": unit})

                grand_total = _quantize_money(grand_acc)
                assert grand_total is not None

                po = PurchaseOrder.objects.create(
                    supplier_id=supplier.pk,
                    branch_id=branch.pk,
                    settlement_mode=settlement,
                    reference_number=(data["reference_number"] or "").strip(),
                    notes=data.get("notes") or "",
                )

                lines_out: list[dict] = []
                for lp in line_payload:
                    ln_row = PurchaseOrderLine.objects.create(
                        purchase_order=po,
                        product_id=lp["product_id"],
                        quantity=lp["quantity"],
                        unit_cost=lp["unit_cost"],
                    )
                    StockReceivingService.increment_branch_stock(
                        branch_pk=branch.pk,
                        product_pk=lp["product"].pk,
                        delta=lp["quantity"],
                    )
                    amt_line = PricingEngineService._quantize_money(lp["quantity"] * lp["unit_cost"])  # type: ignore
                    assert amt_line is not None
                    lines_out.append(
                        {
                            "line_id": str(ln_row.pk),
                            "product_id": str(lp["product_id"]),
                            "quantity": str(lp["quantity"]),
                            "unit_cost": str(lp["unit_cost"]),
                            "line_total": str(amt_line),
                            "stock_adjusted": lp["product"].track_inventory,
                        },
                    )

                if settlement == PurchaseSettlement.CREDIT:
                    new_payable = PricingEngineService._quantize_money(supplier.current_payable + grand_total)  # type: ignore
                    assert new_payable is not None
                    supplier.current_payable = new_payable
                    supplier.save(update_fields=("current_payable", "updated_at"))

        except DRFValidationError:
            raise

        supplier.refresh_from_db(fields=["current_payable", "updated_at"])

        return Response(
            {
                "purchase_order_id": str(po.pk),
                "supplier_id": str(supplier.pk),
                "branch_id": str(branch.pk),
                "settlement_mode": settlement.value,
                "grand_total": str(grand_total),
                "supplier_current_payable": str(supplier.current_payable),
                "lines": lines_out,
            },
            status=status.HTTP_201_CREATED,
        )
