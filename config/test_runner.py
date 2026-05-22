"""Django test discovery defaults for OmniPOS (apps live under ./apps/)."""

from __future__ import annotations

from django.test.runner import DiscoverRunner


class OmniPOSTenantTestRunner(DiscoverRunner):
    """When no labels are given, run known tenant/integration suites instead of only ``"."``.

    Vanilla ``DiscoverRunner`` maps an empty argv to ``"."`` which points at the repo root
    — this project keeps tests beside application packages (``catalog.tests``, …).
    """

    DEFAULT_TEST_LABELS: tuple[str, ...] = (
        "catalog.tests",
        "payments.tests",
        "sales.tests",
    )

    def build_suite(self, test_labels=None, **kwargs):  # type: ignore[no-untyped-def]
        if test_labels == () or test_labels is None:
            merged = list(self.DEFAULT_TEST_LABELS)
        elif test_labels == (".",):
            merged = list(self.DEFAULT_TEST_LABELS)
        else:
            merged = list(test_labels)
        return super().build_suite(test_labels=tuple(merged), **kwargs)
