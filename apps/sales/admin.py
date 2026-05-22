"""Tenant sales admin registrations."""

from django.contrib import admin

from sales.models import InvoiceSetting, PaymentMethod


@admin.register(InvoiceSetting)
class InvoiceSettingAdmin(admin.ModelAdmin):
    list_display = ("company_name", "default_format", "is_active", "contact_phone", "updated_at")
    list_filter = ("default_format", "is_active")
    search_fields = ("company_name", "tax_identifier", "contact_phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    search_fields = ("code", "name")
    list_filter = ("is_active",)
    filter_horizontal = ("applicable_business_types",)
