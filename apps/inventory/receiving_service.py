"""Non-sales stock intake (supplier receipts without ``catalog.Order``)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from catalog.models import Product
from django.core.exceptions import ValidationError

from inventory.services import OrderInventoryService


class StockReceivingService:
    """Bump ``ProductStock`` when inbound lines post (respects ``track_inventory``)."""

    @staticmethod
    def increment_branch_stock(*, branch_pk: UUID, product_pk: UUID, delta: Decimal) -> None:
        if delta <= Decimal("0"):
            raise ValidationError("Receipt quantity must exceed zero.")

        prod = Product.objects.only("track_inventory").filter(pk=product_pk).first()
        if prod is None:
            raise ValidationError("Unknown product UUID for receiving.")
        if not prod.track_inventory:
            return

        stock = OrderInventoryService._locked_stock(branch_pk, product_pk)
        current = Decimal(str(stock.quantity))
        stock.quantity = current + delta
        stock.save(update_fields=("quantity", "updated_at"))
