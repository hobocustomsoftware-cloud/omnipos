"""Tenant inventory / supplier receiving routes."""

from django.urls import path

from inventory.api.views import PurchaseOrderCreateAPIView, SupplierListCreateAPIView

urlpatterns = [
    path(
        "suppliers/",
        SupplierListCreateAPIView.as_view(),
        name="inventory-suppliers",
    ),
    path(
        "purchase-orders/",
        PurchaseOrderCreateAPIView.as_view(),
        name="inventory-purchase-orders",
    ),
]
