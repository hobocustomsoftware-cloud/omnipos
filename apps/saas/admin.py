"""Public-schema admin registrations."""

from django.contrib import admin

from .models import PaymentLog, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "max_products", "max_branches", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    list_display = ("tenant", "provider", "event_type", "amount", "currency", "status", "created_at")
    search_fields = ("idempotency_key", "external_object_id", "event_type")

