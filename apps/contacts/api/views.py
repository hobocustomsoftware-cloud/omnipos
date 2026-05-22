"""Counter customer onboarding + AR snapshot reads."""

from __future__ import annotations

from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBranchEmployee
from contacts.api.serializers import CustomerSerializer, resolve_counter_customer_identity
from contacts.models import Customer


class CustomerListCreateAPIView(APIView):
    permission_classes = (IsAuthenticated, IsBranchEmployee)

    def get(self, request):  # type: ignore[no-untyped-def]
        params = getattr(request, "query_params", request.GET)
        qs = Customer.objects.filter(is_active=True).order_by("name")
        matched_phone_frag = ""

        raw_phone = params.get("phone")
        if isinstance(raw_phone, str) and raw_phone.strip():
            matched_phone_frag = raw_phone.strip()
            qs = qs.filter(phone__icontains=matched_phone_frag)

        raw_name = params.get("name")
        if isinstance(raw_name, str) and raw_name.strip():
            qs = qs.filter(Q(name__icontains=raw_name.strip()))

        rows = list(qs[:300])
        serializer = CustomerSerializer(rows, many=True)
        return Response(
            {
                "results": serializer.data,
                "meta": {
                    "truncated_after": 300,
                    "count_returned": len(serializer.data),
                    "matched_phone_fragment": matched_phone_frag or None,
                },
            },
        )

    def post(self, request):  # type: ignore[no-untyped-def]
        ser = CustomerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        vd = ser.validated_data

        resolved_name, phone_clean = resolve_counter_customer_identity(name=vd.get("name"), phone=vd.get("phone"))

        customer = Customer.objects.create(
            name=resolved_name,
            phone=phone_clean,
            email=vd.get("email") or "",
            notes=vd.get("notes") or "",
            external_ref=vd.get("external_ref") or "",
            is_active=vd.get("is_active", True),
        )
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)
