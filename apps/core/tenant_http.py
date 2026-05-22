"""Tenant-aware helpers aligned with Django REST Framework ``APITestCase``.

django-tenants ``FastTenantTestCase`` exposes no ``client_class``, so inheriting alongside
:class:`rest_framework.test.APITestCase` yields tenant schema routing + ``APIClient`` semantics.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.utils import get_public_schema_name, get_tenant_domain_model, schema_context
from rest_framework.test import APITestCase, APIClient


class OmniTenantAPITestCase(FastTenantTestCase, APITestCase):
    """Tenant ``fast_test`` schema + DRF :class:`~rest_framework.test.APITestCase` (JSON API client)."""

    client_class = APIClient

    user = None

    @classmethod
    def setup_tenant(cls, tenant) -> None:  # type: ignore[override]
        from tenants.models import BusinessType

        with schema_context(get_public_schema_name()):
            bt, _ = BusinessType.objects.get_or_create(code="unittest_bt", defaults={"name": "Unit test vertical"})
            tenant.business_type_id = bt.pk
        tenant.name = "Tenant DRF unittest"

    def setUp(self) -> None:  # type: ignore[override]
        super().setUp()

        domain_obj = getattr(type(self), "domain", None)
        if domain_obj is None:
            domain_obj = get_tenant_domain_model().objects.filter(tenant=self.tenant).first()
        if domain_obj is None:
            self.fail(
                "Tenant has no Domain row; cannot route APIClient for django-tenants (check FastTenantTestCase reuse)",
            )

        host = domain_obj.domain
        self.client.defaults.setdefault("SERVER_NAME", host)
        self.client.credentials(HTTP_HOST=host)

        UserModel = get_user_model()
        self.user = UserModel.objects.create_user(
            username="tenant_api_staff",
            password="test-pass-omit",
            is_staff=True,
        )
        self.client.force_authenticate(user=self.user)


OmniTenantDRFTestCase = OmniTenantAPITestCase  # compat: legacy import name elsewhere in the repo
