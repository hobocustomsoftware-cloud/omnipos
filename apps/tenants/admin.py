"""Administrative helpers for SaaS provisioning."""

from django.contrib import admin

from tenants.models import BusinessType, Client, Domain


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 0


@admin.register(BusinessType)
class BusinessTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("schema_name", "name", "business_type", "subscription_plan", "is_active", "paid_until")
    list_filter = ("is_active", "business_type")
    search_fields = ("schema_name", "name", "custom_domain")
    autocomplete_fields = ("business_type", "subscription_plan")
    inlines = (DomainInline,)
