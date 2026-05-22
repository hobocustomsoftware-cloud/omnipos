"""Ledger admin."""

from django.contrib import admin

from accounting.models import DebtLedgerEntry


@admin.register(DebtLedgerEntry)
class DebtLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("party_type", "customer", "supplier", "order", "debit_amount", "credit_amount", "created_at")
    list_filter = ("party_type",)
    autocomplete_fields = ("customer", "supplier", "order", "purchase_order")
    readonly_fields = ("created_at", "updated_at", "order_payment")
    search_fields = ("description",)
