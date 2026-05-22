"""Contacts routes (customers, supplier masters live here but inventory APIs expose suppliers)."""

from django.urls import path

from contacts.api.views import CustomerListCreateAPIView

urlpatterns = [
    path(
        "customers/",
        CustomerListCreateAPIView.as_view(),
        name="contacts-customers",
    ),
]
