"""HTTP routes under ``api/payments/``."""

from django.urls import path

from payments.api.views import AvailableGatewaysAPIView, KYCSubmissionAPIView

urlpatterns = [
    path(
        "kyc/submissions/",
        KYCSubmissionAPIView.as_view(),
        name="payments-kyc-submit",
    ),
    path(
        "gateways/available/",
        AvailableGatewaysAPIView.as_view(),
        name="payments-gateways-available",
    ),
]
