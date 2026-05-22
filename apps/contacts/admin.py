"""Contacts admin."""

from django.contrib import admin

from contacts.models import Customer, PurchaseOrder, Supplier


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "current_debt", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "phone", "email", "external_ref")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "current_payable", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "phone", "email", "tax_identifier")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("supplier", "reference_number", "created_at", "updated_at")
    search_fields = ("reference_number", "notes")
    autocomplete_fields = ("supplier",)
    readonly_fields = ("created_at", "updated_at")
