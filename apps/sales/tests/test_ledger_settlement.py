"""CREDIT sales raise AR; settlements post credit ledger rows and reduce ``current_debt``."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from django.urls import reverse
from rest_framework import status as http_status

from accounting.models import DebtLedgerEntry
from catalog.models import Branch, Order, Product
from contacts.models import Customer
from core.tenant_http import OmniTenantAPITestCase
from inventory.models import ProductStock
from sales.models import PaymentMethod


class LedgerSettlementAPITests(OmniTenantAPITestCase):
    def test_credit_sale_raises_debt_then_settlement_credit_lowers_balance(self) -> None:
        branch = Branch.objects.create(code="B-LED", name="Ledger branch")
        product = Product.objects.create(
            sku="SKU-DEBT",
            name="Debt item",
            base_uom_code="EA",
            base_price=Decimal("50.00"),
            track_inventory=True,
        )
        ProductStock.objects.create(branch=branch, product=product, quantity=Decimal("500"))
        credit_pm = PaymentMethod.objects.create(code="CREDIT", name="Accounts receivable")

        cust = Customer.objects.create(name="AR buyer", current_debt=Decimal("0.00"))

        offline_uuid = uuid4()
        sync_body = [
            {
                "id": str(offline_uuid),
                "branch_id": str(branch.pk),
                "status": "confirmed",
                "notes": "",
                "customer_id": str(cust.pk),
                "lines": [
                    {
                        "product_id": str(product.pk),
                        "quantity": "1",
                        "unit_price": "50.00",
                    },
                ],
                "payments": [
                    {
                        "payment_method_id": str(credit_pm.pk),
                        "amount": "50.00",
                        "transaction_ref": "",
                    },
                ],
            },
        ]

        bs_url = reverse("sales-bulk-sync")
        r1 = self.client.post(bs_url, sync_body, format="json")
        self.assertEqual(r1.status_code, http_status.HTTP_200_OK)

        cust.refresh_from_db()
        self.assertEqual(cust.current_debt, Decimal("50.00"))

        ledger_rows_pre = DebtLedgerEntry.objects.filter(customer_id=cust.pk).order_by("created_at")
        self.assertEqual(ledger_rows_pre.count(), 1)
        debit_row = ledger_rows_pre.first()
        assert debit_row is not None
        self.assertGreater(debit_row.debit_amount, Decimal("0"))
        self.assertEqual(debit_row.credit_amount, Decimal("0.00"))

        settle_url = reverse("accounting-customer-debt-settlement")
        r_settle = self.client.post(
            settle_url,
            {"customer_id": str(cust.pk), "settlement_amount": "30.00"},
            format="json",
        )
        self.assertEqual(r_settle.status_code, http_status.HTTP_200_OK)
        self.assertEqual(r_settle.data["credit_amount"], "30.00")

        cust.refresh_from_db()
        self.assertEqual(cust.current_debt, Decimal("20.00"))

        all_rows = list(DebtLedgerEntry.objects.filter(customer_id=cust.pk).order_by("created_at"))
        self.assertEqual(len(all_rows), 2)

        settle_row = all_rows[-1]
        self.assertEqual(settle_row.order_id, None)
        self.assertEqual(settle_row.order_payment_id, None)
        self.assertEqual(settle_row.debit_amount, Decimal("0.00"))
        self.assertEqual(settle_row.credit_amount, Decimal("30.00"))

        order = Order.objects.get(pk=offline_uuid)
        self.assertIsNotNone(order.pk)
