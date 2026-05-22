"""Accounting APIs (tenant-scoped ledger operations)."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounting.api.serializers import CustomerDebtSettlementSerializer
from accounting.services import DebtLedgerPostingService
from accounts.permissions import IsBranchEmployee
from contacts.models import Customer


class CustomerDebtSettlementAPIView(APIView):
    """POST on-account debtor payment reducing ``contacts.Customer.current_debt`` + ledger credit."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def post(self, request):  # type: ignore[no-untyped-def]
        inbound = CustomerDebtSettlementSerializer(data=request.data)
        inbound.is_valid(raise_exception=True)
        cid = inbound.validated_data["customer_id"]
        amt = inbound.validated_data["settlement_amount"]

        if not Customer.objects.filter(pk=cid).exists():
            return Response({"customer_id": ["No customer matches this id."]}, status=status.HTTP_404_NOT_FOUND)

        try:
            entry = DebtLedgerPostingService.record_customer_debt_settlement(
                customer_id=cid,
                settlement_amount=amt,
            )
        except DjangoValidationError as exc:
            errs = getattr(exc, "message_dict", None)
            if errs is not None:
                return Response(errs, status=status.HTTP_400_BAD_REQUEST)
            payload = getattr(exc, "messages", None)
            detail = list(payload) if payload is not None else [str(exc)]
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "ledger_entry_id": str(entry.pk),
                "requested_settlement_amount": str(amt),
                "applied_to_debt_amount": str(entry.credit_amount),
                "credit_amount": str(entry.credit_amount),
                "debit_amount": str(entry.debit_amount),
                "customer_id": str(cid),
            },
            status=status.HTTP_200_OK,
        )
