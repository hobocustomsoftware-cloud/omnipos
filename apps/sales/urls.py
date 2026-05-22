"""Sales / checkout REST routes."""

from django.urls import path

from sales.api.views import (
    CheckoutAPIView,
    MerchantPaymentDashboardAPIView,
    OrderInvoiceDownloadAPIView,
    SalesBulkSyncAPIView,
)

urlpatterns = [
    path(
        "orders/<uuid:order_id>/invoice/",
        OrderInvoiceDownloadAPIView.as_view(),
        name="sales-order-invoice",
    ),
    path("orders/bulk-sync/", SalesBulkSyncAPIView.as_view(), name="sales-bulk-sync"),
    path("checkout/", CheckoutAPIView.as_view(), name="sales-checkout"),
    path(
        "merchant/dashboard/payments/",
        MerchantPaymentDashboardAPIView.as_view(),
        name="sales-merchant-payment-dashboard",
    ),
]
