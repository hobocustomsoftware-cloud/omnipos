"""Payment gateway payloads must omit secrets and scrub sensitive credential keys."""

from __future__ import annotations

from django.urls import reverse
from rest_framework import status as http_status

from core.models import IntegrationScope
from core.tenant_http import OmniTenantAPITestCase
from payments.models import TenantPaymentGateway
from sales.models import PaymentMethod


class AvailableGatewaysLeakAPITests(OmniTenantAPITestCase):
    def test_gateways_hide_secret_field_and_masks_extra_credentials(self) -> None:
        pm = PaymentMethod.objects.create(code="KPAY", name="KPay QR")
        TenantPaymentGateway.objects.create(
            payment_method=pm,
            scope=IntegrationScope.POS,
            merchant_id="mid_test",
            secret_key="this-must-never-leak-plaintext",
            public_key="pk_test_public",
            api_extra_credentials={
                "safe_publishable": True,
                "client_secret_here": "leak-if-exposed",
                "nested_bundle": {"api_password": "no", "oauth_access_token_plain": "t0k3n", "readable": "yes"},
                "oauth_private_key_b64": "-----BEGIN BOGUS-----",
            },
            is_enabled=True,
        )

        url = reverse("payments-gateways-available")
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, http_status.HTTP_200_OK)
        methods = resp.data["payment_methods"]
        self.assertEqual(len(methods), 1)
        gw = methods[0]
        self.assertNotIn("secret_key", gw)
        extras = gw.get("api_extra_credentials") or {}

        forbidden_key_fragments = ("private_key", "secret", "password", "token")
        stack = [(str(k).lower(), v) for k, v in extras.items()]
        collected = []
        while stack:
            key, val = stack.pop()
            collected.append(key)
            if isinstance(val, dict):
                stack.extend((str(sk).lower(), sv) for sk, sv in val.items())

        for lk in collected:
            self.assertFalse(
                any(frag in lk for frag in forbidden_key_fragments),
                msg=f"credential subtree still exposes sensitive key slug: {lk!r}",
            )

        self.assertTrue(extras.get("safe_publishable"))
        nested = extras.get("nested_bundle")
        self.assertIsInstance(nested, dict)
        self.assertEqual(nested.get("readable"), "yes")
