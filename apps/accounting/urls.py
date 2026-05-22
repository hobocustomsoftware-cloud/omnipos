"""Accounting routes."""

from django.urls import path

from accounting.api.views import CustomerDebtSettlementAPIView

urlpatterns = [
    path(
        "settlements/customer/",
        CustomerDebtSettlementAPIView.as_view(),
        name="accounting-customer-debt-settlement",
    ),
]
