"""Administrative tooling for catalogs."""

from django.contrib import admin

from accounts.permissions import user_can_manage_branch_pricing

from inventory.models import ProductStock

from .models import (
    Branch,
    Order,
    OrderItem,
    Product,
    ProductBranchSettings,
    ProductUnitConversion,
    UnitOfMeasure,
)
from .services import assert_user_may_modify_branch_price


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "timezone", "is_active", "updated_at")
    search_fields = ("code", "name")


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "label")
    filter_horizontal = ("applicable_business_types",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "barcode",
        "name",
        "base_uom_code",
        "base_price",
        "wholesale_price",
        "wholesale_minimum_qty",
        "is_active",
        "updated_at",
    )
    search_fields = ("sku", "barcode", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProductUnitConversion)
class ProductUnitConversionAdmin(admin.ModelAdmin):
    list_display = ("product", "barcode", "alternate_sku", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("barcode", "alternate_sku", "product__sku", "product__name")
    autocomplete_fields = ("product",)
    readonly_fields = ("created_at", "updated_at")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ("product",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "customer", "status", "inventory_committed", "created_at", "updated_at")
    list_filter = ("status", "branch")
    search_fields = ("notes",)
    autocomplete_fields = ("branch", "customer")
    readonly_fields = ("inventory_committed", "created_at", "updated_at")
    inlines = (OrderItemInline,)


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ("branch", "product", "quantity", "updated_at")
    search_fields = ("product__sku", "branch__code")
    autocomplete_fields = ("branch", "product")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProductBranchSettings)
class ProductBranchSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "branch",
        "product",
        "is_sellable",
        "branch_selling_price",
        "updated_at",
    )
    autocomplete_fields = ("branch", "product")
    search_fields = ("product__sku", "branch__code")

    def get_readonly_fields(self, request, obj=None):  # type: ignore[override]
        fields = tuple(super().get_readonly_fields(request, obj))
        if not user_can_manage_branch_pricing(request.user):
            return (*fields, "branch_selling_price")
        return fields

    def save_model(self, request, obj, form, change):  # type: ignore[override]
        if "branch_selling_price" in form.changed_data:
            assert_user_may_modify_branch_price(request.user)
        super().save_model(request, obj, form, change)
