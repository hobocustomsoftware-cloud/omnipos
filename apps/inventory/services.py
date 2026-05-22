"""Order confirmations / cancellations reconcile ``ProductStock`` rows."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from catalog.models import Order, OrderItem, OrderStatus

from .models import ProductStock

_CONSUMING_STATUSES = frozenset({OrderStatus.CONFIRMED, OrderStatus.COMPLETED})


def _normalize_order_pk(order_id: str | UUID) -> UUID:
    if isinstance(order_id, UUID):
        return order_id
    try:
        return UUID(str(order_id))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValidationError("order_id must be a UUID.", code="invalid_order_id") from exc


class OrderInventoryService:
    """Apply ``ProductStock`` debits/credits when orders confirm or cancel."""

    @staticmethod
    def process_order_stock(order_id: str | UUID) -> None:
        """Adjust branch stock rows for CONFIRMED/COMPLETED or reverse on CANCELLED.

        Rows are aggregated per SKU, locked with ``select_for_update``, and created
        on demand at quantity ``0`` before debiting. Deduction skips products where
        ``track_inventory=False``.

        Requires ``catalog.Order.inventory_committed`` to distinguish idempotent passes
        and to restore only after a recorded deduction.
        """

        pk = _normalize_order_pk(order_id)

        try:
            with transaction.atomic():
                order = Order.objects.select_related("branch").select_for_update().get(pk=pk)

                locked_items = list(
                    OrderItem.objects.filter(order_id=order.pk)
                    .select_related("product")
                    .select_for_update()
                )

                deltas = OrderInventoryService._tracked_quantity_by_product_rows(locked_items)

                if order.status == OrderStatus.CANCELLED:
                    if not order.inventory_committed:
                        return
                    OrderInventoryService._apply_quantity_deltas(
                        branch_pk=order.branch.pk,
                        deltas=deltas,
                        subtract_stock=False,
                    )
                    order.inventory_committed = False
                    order.save(update_fields=("inventory_committed", "updated_at"))
                    return

                if order.status not in _CONSUMING_STATUSES:
                    return

                if order.inventory_committed:
                    return

                OrderInventoryService._apply_quantity_deltas(
                    branch_pk=order.branch.pk,
                    deltas=deltas,
                    subtract_stock=True,
                )

                order.inventory_committed = True
                order.save(update_fields=("inventory_committed", "updated_at"))
        except Order.DoesNotExist as exc:
            raise ValidationError("Order matching id was not found.", code="order_not_found") from exc

    @staticmethod
    def _tracked_quantity_by_product_rows(items: Iterable[OrderItem]) -> dict[UUID, Decimal]:
        sums: defaultdict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
        for row in items:
            if not row.product.track_inventory:
                continue
            sums[row.product_id] += row.quantity

        return {pid: qty for pid, qty in sums.items() if qty != Decimal("0")}

    @staticmethod
    def _locked_stock(branch_pk: UUID, product_pk: UUID) -> ProductStock:
        """Return locked stock row, inserting zero-on-hand baseline if absent."""

        existing = (
            ProductStock.objects.select_for_update()
            .filter(branch_id=branch_pk, product_id=product_pk)
            .first()
        )
        if existing is not None:
            return existing

        try:
            ProductStock.objects.create(
                branch_id=branch_pk,
                product_id=product_pk,
                quantity=Decimal("0"),
            )
        except IntegrityError:
            pass
        return ProductStock.objects.select_for_update().get(
            branch_id=branch_pk,
            product_id=product_pk,
        )

    @staticmethod
    def _apply_quantity_deltas(
        branch_pk: UUID,
        deltas: dict[UUID, Decimal],
        *,
        subtract_stock: bool,
    ) -> None:
        """``subtract_stock`` True ⇒ sale deductions; False ⇒ cancellations add back."""

        ordered_keys = sorted(deltas.keys(), key=lambda x: str(x))
        for product_pk in ordered_keys:
            qty_move = deltas[product_pk]

            stock = OrderInventoryService._locked_stock(branch_pk, product_pk)
            current_qty = Decimal(str(stock.quantity))
            desired = (
                current_qty - qty_move
                if subtract_stock
                else current_qty + qty_move
            )
            if subtract_stock and desired < Decimal("0"):
                raise ValidationError(
                    "Insufficient quantity on hand for one or more products on this branch.",
                    code="insufficient_stock",
                )
            stock.quantity = desired
            stock.save(update_fields=("quantity", "updated_at"))
