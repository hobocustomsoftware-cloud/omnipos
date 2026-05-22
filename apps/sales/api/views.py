"""Checkout API (atomic order + tenders + inventory commit)."""

from __future__ import annotations

from datetime import datetime, timedelta, time
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone as dj_timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import (
    IsBranchEmployee,
    _branch_hint_request,
    _resolve_branch_uuid,
)
from accounting.services import DebtLedgerPostingService
from catalog.models import Branch, Order, OrderItem, OrderStatus, Product
from core.models import IntegrationScope
from inventory.services import OrderInventoryService
from sales.api.serializers import BulkSyncOrderSerializer, CheckoutRequestSerializer
from sales.invoice_generation import InvoiceGenerationService
from sales.models import InvoiceFormat, InvoiceSetting, OrderPayment, PaymentMethod
from sales.services import PricingEngineService


def _quantize_money(amount: Decimal) -> Decimal | None:
    return PricingEngineService._quantize_money(amount)  # type: ignore[attr-defined]


def _branch_local_day_bounds(branch: Branch) -> tuple[str, str, datetime, datetime]:
    tz_label = (branch.timezone or "").strip() or "UTC"
    try:
        tz_obj = ZoneInfo(tz_label)
    except Exception:
        tz_obj = ZoneInfo("UTC")
    now_local = dj_timezone.now().astimezone(tz_obj)
    day = now_local.date()
    start_local = datetime.combine(day, time.min, tzinfo=tz_obj)
    end_local = start_local + timedelta(days=1)
    return day.isoformat(), tz_label, start_local, end_local


def _dashboard_bucket_total(norm: dict[str, Decimal], *aliases: str) -> Decimal:
    total = Decimal("0")
    for alias in aliases:
        total += norm.get(alias.upper(), Decimal("0"))
    q = _quantize_money(total)
    return q if q is not None else Decimal("0")


class CheckoutAPIView(APIView):
    """Create a confirmed catalog order with server-priced lines and tenders, then debit stock."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def post(self, request):  # type: ignore[no-untyped-def]
        inbound = CheckoutRequestSerializer(data=request.data)
        inbound.is_valid(raise_exception=True)
        data = inbound.validated_data

        branch_id = data["branch_id"]
        tenant = getattr(request, "tenant", None) or getattr(connection, "tenant", None)

        if not getattr(request.user, "is_staff", False) and not getattr(request.user, "is_superuser", False):
            hinted = _resolve_branch_uuid(_branch_hint_request(request))
            if hinted is None or hinted != branch_id:
                return Response(
                    {"detail": "branch_id body must match the scoped X-Branch-Id / branch_id parameter."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        payment_rows: list[dict]
        resolved_payload: list[dict]
        order_total: Decimal

        try:
            with transaction.atomic():
                branch = Branch.objects.select_for_update().filter(pk=branch_id, is_active=True).first()
                if branch is None:
                    raise DRFValidationError({"detail": "Branch was not found or inactive."})

                product_ids = [line["product_id"] for line in data["items"]]
                unique_ids = list({pid: pid for pid in product_ids}.values())

                products_locked = Product.objects.select_for_update().filter(pk__in=unique_ids).in_bulk(unique_ids)

                missing = sorted({str(pid) for pid in unique_ids} - {str(pk) for pk in products_locked})
                if missing:
                    raise DRFValidationError(
                        {"detail": f"Unknown or inactive catalogue products: {', '.join(missing)}"},
                    )

                resolved_payload = []
                for line in data["items"]:
                    pid = line["product_id"]
                    product = products_locked[pid]
                    if not product.is_active:
                        raise DRFValidationError(
                            {"detail": f'Product inactive: {product.sku!r}.', "sku": product.sku},
                        )

                    qty = line["quantity"]
                    unit = PricingEngineService.resolve_unit_price(product=product, quantity=qty, branch=branch)

                    resolved_payload.append(
                        {"product_id": pid, "product": product, "quantity": qty, "unit_price": unit},
                    )

                declared_unique_ids = {pay["payment_method_id"] for pay in data["payments"]}
                qs_methods = (
                    PaymentMethod.objects.filter(pk__in=declared_unique_ids, is_active=True).prefetch_related(
                        "applicable_business_types",
                    )
                )
                methods_by_pk = {m.pk: m for m in qs_methods}

                if methods_by_pk.keys() != declared_unique_ids:
                    raise DRFValidationError({"detail": "One or more payment_method_id values were not found."})

                bt_id = getattr(tenant, "business_type_id", None) if tenant is not None else None

                payment_rows = []
                for pay in data["payments"]:
                    method = methods_by_pk[pay["payment_method_id"]]
                    tags = method.applicable_business_types.all()
                    if tags.exists():
                        if bt_id is None or not tags.filter(pk=bt_id).exists():
                            raise DRFValidationError(
                                {"detail": f'Payment tender {method.code!r} is restricted by business_type tags.'},
                            )

                    amt = _quantize_money(pay["amount"])
                    assert amt is not None
                    if amt <= Decimal("0"):
                        raise DRFValidationError(
                            {"detail": f'Payment amounts must exceed zero (tender={method.code!r}).'},
                        )
                    tnd = pay.get("tendered_amount", Decimal("0.00"))
                    chg = pay.get("change_amount", Decimal("0.00"))
                    t_q = _quantize_money(tnd)
                    c_q = _quantize_money(chg)
                    payment_rows.append(
                        {
                            "method": method,
                            "amount": amt,
                            "ref": (pay["transaction_ref"] or "").strip(),
                            "tendered_amount": t_q if t_q is not None else Decimal("0.00"),
                            "change_amount": c_q if c_q is not None else Decimal("0.00"),
                        },
                    )

                order_total = PricingEngineService.compute_order_total(
                    lines=[{"quantity": x["quantity"], "unit_price": x["unit_price"]} for x in resolved_payload],
                )

                pay_total_acc = Decimal("0")
                for row in payment_rows:
                    pay_total_acc += row["amount"]
                pay_total = _quantize_money(pay_total_acc)
                assert pay_total is not None

                if pay_total != order_total:
                    raise DRFValidationError(
                        {
                            "detail": "Sum of tenders must equal the priced order total (server-calculated).",
                            "order_total": str(order_total),
                            "payment_total": str(pay_total),
                        },
                    )

                order = Order.objects.create(
                    branch=branch,
                    status=OrderStatus.CONFIRMED,
                    notes=data.get("notes") or "",
                    customer_id=data.get("customer_id"),
                )

                OrderItem.objects.bulk_create(
                    [
                        OrderItem(
                            order=order,
                            product_id=item["product_id"],
                            quantity=item["quantity"],
                            unit_price=item["unit_price"],
                        )
                        for item in resolved_payload
                    ],
                    batch_size=50,
                )

                OrderPayment.objects.bulk_create(
                    [
                        OrderPayment(
                            order=order,
                            payment_method=r["method"],
                            amount=r["amount"],
                            transaction_ref=r["ref"],
                            tendered_amount=r["tendered_amount"],
                            change_amount=r["change_amount"],
                        )
                        for r in payment_rows
                    ],
                    batch_size=50,
                )

                DebtLedgerPostingService.post_credit_sales_for_order(order)

                try:
                    OrderInventoryService.process_order_stock(order.pk)
                except DjangoValidationError as exc:
                    raise DRFValidationError({"detail": list(exc.messages)}) from exc

                resp_order_id = order.pk
                resp_branch_id = branch.pk

        except DRFValidationError:
            raise
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": list(exc.messages)}) from exc

        cust_pk = data.get("customer_id")
        return Response(
            {
                "order_id": str(resp_order_id),
                "branch_id": str(resp_branch_id),
                "customer_id": str(cust_pk) if cust_pk is not None else None,
                "status": OrderStatus.CONFIRMED,
                "order_total": str(order_total),
                "payments": [
                    {
                        "payment_method_id": str(r["method"].pk),
                        "code": r["method"].code,
                        "amount": str(r["amount"]),
                        "tendered_amount": str(r["tendered_amount"]),
                        "change_amount": str(r["change_amount"]),
                        "transaction_ref": r["ref"],
                    }
                    for r in payment_rows
                ],
                "lines": [
                    {
                        "product_id": str(x["product_id"]),
                        "sku": x["product"].sku,
                        "quantity": str(x["quantity"]),
                        "unit_price": str(x["unit_price"]),
                        "line_total": str(
                            _quantize_money(x["quantity"] * x["unit_price"]) or Decimal("0"),
                        ),
                    }
                    for x in resolved_payload
                ],
                "inventory_committed": True,
            },
            status=status.HTTP_201_CREATED,
        )


def _flatten_bulk_orders_payload(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("orders"), list):
        return data["orders"]
    raise ValueError("bulk_sync_invalid_envelope")


def _persist_bulk_sync_order_row(
    *,
    request,
    row: dict,
    tenant_bt_id,
    elevated: bool,
    hinted_branch_uuid: UUID | None,
) -> dict[str, Any]:
    """Create or reconcile one offline-first order row under an outer atomic() block."""

    branch_id = row["branch_id"]
    oid = row["id"]
    payments_payload = list(row["payments"])

    if not elevated:
        if hinted_branch_uuid is None or hinted_branch_uuid != branch_id:
            raise DRFValidationError(
                {"detail": "branch_id must match the scoped X-Branch-Id / branch_id for this device."},
            )

    branch = Branch.objects.select_for_update().filter(pk=branch_id, is_active=True).first()
    if branch is None:
        raise DRFValidationError({"detail": "Branch was not found or inactive."})

    lines = row["lines"]
    uniq = list({ln["product_id"]: ln["product_id"] for ln in lines}.values())

    products_locked = Product.objects.select_for_update().filter(pk__in=uniq).in_bulk(uniq)
    missing_ids = sorted({str(pid) for pid in uniq} - {str(pk) for pk in products_locked})
    if missing_ids:
        raise DRFValidationError({"detail": f"Unknown catalogue products: {', '.join(missing_ids)}"})

    resolved_lines = []
    for ln in lines:
        pid = ln["product_id"]
        prod = products_locked[pid]
        if not prod.is_active:
            raise DRFValidationError({"detail": f'Product inactive: {prod.sku!r}.', "sku": prod.sku})
        up_q = PricingEngineService._quantize_money(ln["unit_price"])  # type: ignore[attr-defined]
        assert up_q is not None
        resolved_lines.append({"product_id": pid, "product": prod, "quantity": ln["quantity"], "unit_price": up_q})

    order_total = PricingEngineService.compute_order_total(
        lines=[{"quantity": x["quantity"], "unit_price": x["unit_price"]} for x in resolved_lines],
    )

    payment_rows: list[dict[str, Any]] = []
    if payments_payload:
        declared_unique_ids = {pay["payment_method_id"] for pay in payments_payload}
        qs_methods = (
            PaymentMethod.objects.filter(pk__in=declared_unique_ids, is_active=True).prefetch_related(
                "applicable_business_types",
            )
        )
        methods_by_pk = {m.pk: m for m in qs_methods}
        if methods_by_pk.keys() != declared_unique_ids:
            raise DRFValidationError({"detail": "One or more payment_method_id values were not found."})

        for pay in payments_payload:
            method = methods_by_pk[pay["payment_method_id"]]
            tags = method.applicable_business_types.all()
            if tags.exists():
                if tenant_bt_id is None or not tags.filter(pk=tenant_bt_id).exists():
                    raise DRFValidationError(
                        {"detail": f'Payment tender {method.code!r} is restricted by business_type tags.'},
                    )

            amt = _quantize_money(pay["amount"])
            assert amt is not None
            if amt <= Decimal("0"):
                raise DRFValidationError({"detail": f'Payment amounts must exceed zero (tender={method.code!r}).'})
            tnd = pay.get("tendered_amount", Decimal("0.00"))
            chg = pay.get("change_amount", Decimal("0.00"))
            t_q = _quantize_money(tnd)
            c_q = _quantize_money(chg)
            payment_rows.append(
                {
                    "method": method,
                    "amount": amt,
                    "ref": (pay["transaction_ref"] or "").strip(),
                    "tendered_amount": t_q if t_q is not None else Decimal("0.00"),
                    "change_amount": c_q if c_q is not None else Decimal("0.00"),
                },
            )

        pay_total_acc = Decimal("0")
        for r in payment_rows:
            pay_total_acc += r["amount"]
        pay_total = _quantize_money(pay_total_acc)
        assert pay_total is not None
        if pay_total != order_total:
            raise DRFValidationError(
                {
                    "detail": "Sum of tenders must equal the priced order total (offline line snapshot).",
                    "order_total": str(order_total),
                    "payment_total": str(pay_total),
                    "offline_order_id": str(oid),
                },
            )

    existing = Order.objects.select_for_update().filter(pk=oid).first()
    notes_value = row.get("notes") or ""
    cid = row.get("customer_id")

    if existing is not None:
        if existing.inventory_committed:
            return {
                "id": str(oid),
                "action": "skipped_idempotent",
                "status": existing.status,
                "inventory_committed": True,
            }
        if existing.branch_id != branch_id:
            raise DRFValidationError(
                {"detail": "Cannot move an offline replay order to another branch.", "offline_order_id": str(oid)},
            )
        OrderItem.objects.filter(order_id=existing.pk).delete()
        OrderPayment.objects.filter(order_id=existing.pk).delete()

        existing.notes = notes_value
        existing.status = row["status"]
        if cid is not None:
            existing.customer_id = cid
        uf: tuple[str, ...] = ("notes", "status", "updated_at")
        if cid is not None:
            uf = ("notes", "status", "customer_id", "updated_at")
        existing.save(update_fields=uf)
        order = existing
        action_label = "updated"
    else:
        order = Order.objects.create(
            id=oid,
            branch=branch,
            status=row["status"],
            notes=notes_value,
            inventory_committed=False,
            customer_id=cid,
        )
        action_label = "created"

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product_id=item["product_id"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            for item in resolved_lines
        ],
        batch_size=50,
    )

    if payment_rows:
        OrderPayment.objects.bulk_create(
            [
                OrderPayment(
                    order=order,
                    payment_method=r["method"],
                    amount=r["amount"],
                    transaction_ref=r["ref"],
                    tendered_amount=r["tendered_amount"],
                    change_amount=r["change_amount"],
                )
                for r in payment_rows
            ],
            batch_size=50,
        )

    DebtLedgerPostingService.post_credit_sales_for_order(order)

    try:
        OrderInventoryService.process_order_stock(order.pk)
    except DjangoValidationError as exc:
        raise DRFValidationError({"detail": list(exc.messages), "offline_order_id": str(oid)}) from exc

    order.refresh_from_db(fields=["inventory_committed", "status"])

    return {
        "id": str(oid),
        "action": action_label,
        "status": order.status,
        "inventory_committed": order.inventory_committed,
    }


class SalesBulkSyncAPIView(APIView):
    """Replay offline-created orders by client UUID (idempotent), then commit inventory."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def post(self, request):  # type: ignore[no-untyped-def]
        raw = getattr(request, "data", {})
        try:
            raw_orders = _flatten_bulk_orders_payload(raw)
        except ValueError:
            return Response(
                {"detail": "Expected JSON array of orders or an object {\"orders\": [...]}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = BulkSyncOrderSerializer(data=raw_orders, many=True)
        ser.is_valid(raise_exception=True)

        validated = ser.validated_data
        if len(validated) == 0:
            return Response({"detail": "At least one order is required."}, status=status.HTTP_400_BAD_REQUEST)

        elevated = getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False)
        hinted_uuid = None
        if not elevated:
            hinted_raw = _branch_hint_request(request)
            hinted_uuid = _resolve_branch_uuid(hinted_raw)

        tenant = getattr(request, "tenant", None) or getattr(connection, "tenant", None)
        tenant_bt_id = getattr(tenant, "business_type_id", None) if tenant is not None else None

        results: list[dict[str, Any]]
        try:
            with transaction.atomic():
                results = []
                for row in validated:
                    results.append(
                        _persist_bulk_sync_order_row(
                            request=request,
                            row=row,
                            tenant_bt_id=tenant_bt_id,
                            elevated=elevated,
                            hinted_branch_uuid=hinted_uuid,
                        ),
                    )
        except DRFValidationError:
            raise
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": list(exc.messages)}) from exc

        return Response({"results": results}, status=status.HTTP_200_OK)


class OrderInvoiceDownloadAPIView(APIView):
    """JSON invoice / thermal receipt for a persisted :class:`~catalog.models.Order`.

    Branch employees may only retrieve documents for orders on their scoped branch.
    """

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def get(self, request, order_id):  # type: ignore[no-untyped-def]
        elevated = getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False)
        hinted = _resolve_branch_uuid(_branch_hint_request(request))

        order = get_object_or_404(
            Order.objects.select_related("branch", "customer"),
            pk=order_id,
        )

        if not elevated:
            if hinted is None or hinted != order.branch_id:
                return Response(
                    {"detail": "You may only print invoices for your scoped branch."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        params = getattr(request, "query_params", request.GET)
        fmt_raw = params.get("format")
        if fmt_raw is None or str(fmt_raw).strip() == "":
            pref_fmt = (
                InvoiceSetting.objects.filter(is_active=True)
                .order_by("-updated_at")
                .values_list("default_format", flat=True)
                .first()
            )
            fmt = str(pref_fmt or InvoiceFormat.A4).strip().upper()
        else:
            fmt = str(fmt_raw).strip().upper()

        if fmt not in ("A4", "THERMAL"):
            return Response({"detail": "format must be A4 or THERMAL."}, status=status.HTTP_400_BAD_REQUEST)

        if fmt == "THERMAL":
            try:
                tw = int(str(params.get("thermal_width", "58")).strip())
            except (AttributeError, TypeError, ValueError):
                tw = 58
            tw = min(80, max(58, tw))
            wc = InvoiceGenerationService.thermal_width_from_mm(tw)
            plain = InvoiceGenerationService.render_thermal_text(order=order, width_chars=wc)
            return Response(
                {
                    "format": "THERMAL",
                    "thermal_width_mm": tw,
                    "characters_per_line": wc,
                    "plain_text": plain,
                    "order_id": str(order.pk),
                },
            )

        active_settings = InvoiceSetting.objects.filter(is_active=True).order_by("-updated_at").first()
        body = InvoiceGenerationService.build_a4_invoice_payload(
            order=order,
            settings=active_settings,
            request=request,
        )
        return Response(body)


class MerchantPaymentDashboardAPIView(APIView):
    """POS storefront settlements today (Cash / KPay / WavePay …) from ``OrderPayment``.

    SaaS billing rails use separate credentials ``IntegrationScope.SAAS``;
    this dashboard intentionally reflects POS checkout liquidity only.
    """

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def get(self, request):  # type: ignore[no-untyped-def]
        hint = _resolve_branch_uuid(_branch_hint_request(request))
        raw_branch = request.query_params.get("branch_id")

        branch_uuid: UUID | None
        if raw_branch is not None and str(raw_branch).strip() != "":
            try:
                branch_uuid = UUID(str(raw_branch).strip())
            except (AttributeError, TypeError, ValueError):
                return Response({"detail": "Invalid branch_id UUID."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            branch_uuid = hint

        if branch_uuid is None:
            return Response(
                {"detail": "Provide branch_id query parameter or X-Branch-Id / branch_id scope."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        elevated = getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False)
        if not elevated:
            if hint is None or hint != branch_uuid:
                return Response(
                    {"detail": "You may only query the dashboard for your scoped branch."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        branch = Branch.objects.filter(pk=branch_uuid, is_active=True).first()
        if branch is None:
            return Response({"detail": "Branch was not found or inactive."}, status=status.HTTP_404_NOT_FOUND)

        date_local, tz_label, start_local, end_local = _branch_local_day_bounds(branch)

        payment_qs = OrderPayment.objects.filter(
            order__branch_id=branch.pk,
            order__created_at__gte=start_local,
            order__created_at__lt=end_local,
        )

        agg_rows = (
            payment_qs.values("payment_method__code", "payment_method__name")
            .annotate(total=Sum("amount"))
            .order_by("payment_method__code")
        )

        norm_upper: dict[str, Decimal] = {}
        payment_methods: list[dict[str, str]] = []
        for row in agg_rows:
            raw_code = (row["payment_method__code"] or "").strip()
            label = row["payment_method__name"] or raw_code or "UNKNOWN"
            chunk = row["total"] if row["total"] is not None else Decimal("0")
            q_chunk = _quantize_money(chunk)
            amt = q_chunk if q_chunk is not None else Decimal("0")

            upper = raw_code.upper() if raw_code else "UNKNOWN"
            norm_upper[upper] = norm_upper.get(upper, Decimal("0")) + amt

            payment_methods.append(
                {
                    "code": raw_code,
                    "name": label,
                    "total": str(amt),
                },
            )

        grand_raw = payment_qs.aggregate(grand_total=Sum("amount"))["grand_total"]
        grand_dec = grand_raw if grand_raw is not None else Decimal("0")
        grand_q = _quantize_money(grand_dec)
        grand_total = grand_q if grand_q is not None else Decimal("0")

        summary = {
            "cash_total": str(_dashboard_bucket_total(norm_upper, "CASH")),
            "kpay_total": str(_dashboard_bucket_total(norm_upper, "KPAY", "K_PAY")),
            "wavepay_total": str(_dashboard_bucket_total(norm_upper, "WAVEPAY", "WAVE_PAY")),
            "credit_total": str(_dashboard_bucket_total(norm_upper, "CREDIT", "AR", "TAB")),
        }

        return Response(
            {
                "branch": {
                    "id": str(branch.pk),
                    "code": branch.code,
                    "name": branch.name,
                },
                "date_local": date_local,
                "timezone": tz_label,
                "settlement_scope": IntegrationScope.POS,
                "payment_methods": payment_methods,
                "summary": summary,
                "grand_total": str(grand_total),
            },
        )
