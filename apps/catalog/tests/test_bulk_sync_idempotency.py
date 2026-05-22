"""Bulk-sync offline order replay must not double-apply inventory when committed."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.urls import reverse
from rest_framework import status as http_status

from catalog.models import Branch, Order, Product
from core.tenant_http import OmniTenantAPITestCase
from inventory.models import ProductStock
from inventory.services import OrderInventoryService
from sales.models import PaymentMethod

_REAL_PROCESS_ORDER_STOCK = OrderInventoryService.__dict__["process_order_stock"].__func__


def _process_order_stock_spy(order_id):  # type: ignore[no-untyped-def]
    """Call real deduction logic without recursing through the patched class attribute."""

    return _REAL_PROCESS_ORDER_STOCK(order_id)


class BulkSyncIdempotencyAPITests(OmniTenantAPITestCase):
    @patch("sales.api.views.OrderInventoryService.process_order_stock", wraps=_process_order_stock_spy)
    def test_duplicate_bulk_sync_uuid_commits_stock_once(self, mock_process_stock) -> None:
        branch = Branch.objects.create(code="B-SYNC", name="Sync Branch")
        cash = PaymentMethod.objects.create(code="CASH", name="Cash")
        product = Product.objects.create(
            sku="SKU-SYNC",
            name="Tracked widget",
            base_uom_code="EA",
            base_price=Decimal("10.00"),
            track_inventory=True,
        )
        ProductStock.objects.create(branch=branch, product=product, quantity=Decimal("500"))

        offline_uuid = uuid4()
        envelope = [
            {
                "id": str(offline_uuid),
                "branch_id": str(branch.pk),
                "status": "confirmed",
                "notes": "",
                "lines": [
                    {
                        "product_id": str(product.pk),
                        "quantity": "2",
                        "unit_price": "10.00",
                    },
                ],
                "payments": [
                    {
                        "payment_method_id": str(cash.pk),
                        "amount": "20.00",
                        "transaction_ref": "",
                    },
                ],
            },
        ]

        url = reverse("sales-bulk-sync")
        first = self.client.post(url, envelope, format="json")
        self.assertEqual(first.status_code, http_status.HTTP_200_OK)
        self.assertEqual(first.data["results"][0]["action"], "created")
        self.assertTrue(first.data["results"][0]["inventory_committed"])

        second = self.client.post(url, envelope, format="json")
        self.assertEqual(second.status_code, http_status.HTTP_200_OK)
        self.assertEqual(second.data["results"][0]["action"], "skipped_idempotent")

        self.assertEqual(Order.objects.filter(pk=offline_uuid).count(), 1)
        self.assertEqual(mock_process_stock.call_count, 1)
