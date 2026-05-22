"""REST API for payments / KYC (Flutter)."""

from __future__ import annotations

from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBranchEmployee
from payments.api.serializers import (
    KYCSubmissionSerializer,
    MerchantKYCApplicationSerializer,
)
from payments.models import MerchantKYCApplication
from payments.services import PaymentProvisioningService


class KYCSubmissionAPIView(APIView):
    """POS owner submits KYC documents + manual fields (multipart or JSON)."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def post(self, request):  # type: ignore[no-untyped-def]
        tenant = getattr(request, "tenant", None) or getattr(connection, "tenant", None)
        if tenant is None:
            return Response({"detail": "Tenant context missing."}, status=status.HTTP_400_BAD_REQUEST)

        inbound = KYCSubmissionSerializer(data=request.data)
        inbound.is_valid(raise_exception=True)
        payload = inbound.validated_data

        doc_nrc = payload.get("document_nrc")
        doc_lic = payload.get("document_license")

        create_kwargs = {
            "client": tenant,
            "scope": payload["scope"],
            "status": MerchantKYCApplication.Status.SUBMITTED,
            "legal_name": payload.get("legal_name") or "",
            "trading_name": payload.get("trading_name") or "",
            "registration_number": payload.get("registration_number") or "",
            "tax_identifier": payload.get("tax_identifier") or "",
            "contact_email": payload.get("contact_email") or "",
            "contact_phone": payload.get("contact_phone") or "",
            "registered_address": payload.get("registered_address") or {},
            "manual_submission": payload.get("manual_submission") or {},
        }
        if doc_nrc:
            create_kwargs["document_nrc"] = doc_nrc
        if doc_lic:
            create_kwargs["document_license"] = doc_lic

        # KYC rows live on the public schema (FK to tenants.Client).
        with schema_context(get_public_schema_name()):
            app = MerchantKYCApplication.objects.create(**create_kwargs)

        body = MerchantKYCApplicationSerializer(instance=app).data
        body["documents_uploaded"] = {
            "nrc": bool(app.document_nrc),
            "license": bool(app.document_license),
        }
        return Response(body, status=status.HTTP_201_CREATED)


class AvailableGatewaysAPIView(APIView):
    """Published POS-scope gateway rows (masked JSON, never ``secret_key``)."""

    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def get(self, request):  # type: ignore[no-untyped-def]
        tenant = getattr(request, "tenant", None) or getattr(connection, "tenant", None)
        return Response(
            {
                "payment_methods": PaymentProvisioningService.build_client_safe_payment_manifest(tenant=tenant),
            },
        )
