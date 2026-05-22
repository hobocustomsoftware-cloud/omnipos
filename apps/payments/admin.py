"""Admin registrations for payments plumbing."""

from django.contrib import admin
from django.db import connection

from django_tenants.utils import get_public_schema_name

from payments.models import MerchantKYCApplication, TenantPaymentGateway


@admin.register(MerchantKYCApplication)
class MerchantKYCApplicationAdmin(admin.ModelAdmin):
    list_display = ("client", "scope", "status", "legal_name", "contact_phone", "created_at")
    list_filter = ("scope", "status")
    search_fields = (
        "legal_name",
        "trading_name",
        "registration_number",
        "contact_email",
        "client__schema_name",
    )
    autocomplete_fields = ("client",)
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        qs = super().get_queryset(request)
        if connection.schema_name != get_public_schema_name():
            return qs.none()
        return qs


@admin.register(TenantPaymentGateway)
class TenantPaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ("payment_method", "scope", "is_enabled", "merchant_id", "updated_at")
    list_filter = ("scope", "is_enabled")
    search_fields = ("merchant_id", "payment_method__code", "payment_method__name")
    autocomplete_fields = ("payment_method",)
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):  # type: ignore[no-untyped-def]
        qs = super().get_queryset(request)
        if connection.schema_name == get_public_schema_name():
            return qs.none()
        return qs
