"""Application services for postings into :class:`~accounting.models.DebtLedgerEntry`."""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from accounting.models import DebtLedgerEntry, PartyType
from catalog.models import Order
from contacts.models import Customer
from sales.models import OrderPayment
from sales.services import PricingEngineService


class DebtLedgerPostingService:
    """Hook sales tenders (CREDIT) into ledger + rolling customer balances."""

    @staticmethod
    def record_customer_debt_settlement(*, customer_id, settlement_amount) -> DebtLedgerEntry:
        """Allocate an on-account payment against AR inside a single atomic transaction.

        Under ``transaction.atomic()`` the customer row is ``select_for_update``, the owed
        balance is reduced by the applied slice of the payment, then a ledger row records
        the relief with ``credit_amount`` equal to the **applied** amount (the same decrement
        as ``current_debt``):

        ``applied = min(quantized_requested_settlement, quantized_current_debt_before)``.

        This keeps postings consistent when the POS sends a settlement larger than the
        running balance — the surplus is intentionally not posted as phantom credit beyond
        what was owed.

        Ledger rows carrying only ``credit_amount`` represent debtor payments on account.
        """

        amt = PricingEngineService._quantize_money(settlement_amount)  # type: ignore[attr-defined]
        if amt is None or amt <= Decimal("0"):
            raise ValidationError({"settlement_amount": "Must be greater than zero."})

        with transaction.atomic():
            cust = Customer.objects.select_for_update().get(pk=customer_id)
            owed = PricingEngineService._quantize_money(cust.current_debt) or Decimal("0")  # type: ignore[attr-defined]
            if owed <= Decimal("0"):
                raise ValidationError({"customer_id": "Customer has zero outstanding debt."})

            applied = amt if amt <= owed else owed
            new_bal_q = PricingEngineService._quantize_money(owed - applied)
            assert new_bal_q is not None
            cust.current_debt = new_bal_q
            cust.save(update_fields=("current_debt", "updated_at"))

            return DebtLedgerEntry.objects.create(
                party_type=PartyType.CUSTOMER,
                customer_id=cust.pk,
                supplier_id=None,
                order=None,
                purchase_order=None,
                order_payment=None,
                debit_amount=Decimal("0"),
                credit_amount=applied,
                description="Customer debt settlement (on-account payment)",
            )

    @staticmethod
    def post_credit_sales_for_order(order: Order) -> None:
        """Raise customer ``current_debt`` for CREDIT tenders; idempotent via ``order_payment`` OneToOne."""

        if order.customer_id is None:
            return

        payments = OrderPayment.objects.filter(order=order).select_related("payment_method")
        for tender in payments:
            code = (tender.payment_method.code or "").strip().upper()
            if code != "CREDIT":
                continue
            amt = PricingEngineService._quantize_money(tender.amount)  # type: ignore[attr-defined]
            if amt is None or amt <= Decimal("0"):
                continue
            DebtLedgerPostingService._create_customer_credit_ledger_row(
                customer_id=order.customer_id,
                order=order,
                order_payment=tender,
                debit_amount=amt,
            )

    @staticmethod
    def _create_customer_credit_ledger_row(
        *,
        customer_id,
        order: Order,
        order_payment: OrderPayment,
        debit_amount: Decimal,
    ) -> None:
        if DebtLedgerEntry.objects.filter(order_payment_id=order_payment.pk).exists():
            return

        with transaction.atomic():
            cust = Customer.objects.select_for_update().get(pk=customer_id)
            cust.current_debt = (cust.current_debt or Decimal("0")) + debit_amount
            cust.save(update_fields=("current_debt", "updated_at"))
            DebtLedgerEntry.objects.create(
                party_type=PartyType.CUSTOMER,
                customer_id=customer_id,
                supplier_id=None,
                order=order,
                purchase_order=None,
                order_payment=order_payment,
                debit_amount=debit_amount,
                credit_amount=Decimal("0"),
                description=f'CREDIT tender snapshot for order {order.pk}',
            )


def customer_debt_ledger_cleanup_hook(entry: DebtLedgerEntry) -> None:
    """Keep ``Customer.current_debt`` in sync when ledger rows are cascaded/deleted."""

    if entry.party_type != PartyType.CUSTOMER:
        return
    if entry.customer_id is None:
        return

    debit_delta = PricingEngineService._quantize_money(entry.debit_amount)  # type: ignore[attr-defined]
    if debit_delta is None:
        debit_delta = Decimal("0")
    credit_delta = PricingEngineService._quantize_money(entry.credit_amount)  # type: ignore[attr-defined]
    if credit_delta is None:
        credit_delta = Decimal("0")

    if debit_delta > Decimal("0"):
        updated = (
            Customer.objects.filter(pk=entry.customer_id, current_debt__gte=debit_delta).update(
                current_debt=F("current_debt") - debit_delta,
            )
        )
        if updated == 0:
            Customer.objects.filter(pk=entry.customer_id).update(current_debt=Decimal("0"))

    if credit_delta > Decimal("0"):
        Customer.objects.filter(pk=entry.customer_id).update(current_debt=F("current_debt") + credit_delta)
