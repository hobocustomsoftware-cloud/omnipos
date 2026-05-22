"""KYC artifacts (public-schema history) & tenant PSP gateway credentials."""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import AbstractBaseModel, IntegrationScope


class MerchantKYCApplication(AbstractBaseModel):
    """Merchant KYC packets (SaaS billing vs POS acquirer onboarding)."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        SUBMITTED = "submitted", _("Submitted")
        UNDER_REVIEW = "under_review", _("Under review")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")
        CHANGES_REQUESTED = "changes_requested", _("Changes requested")

    client = models.ForeignKey(
        "tenants.Client",
        on_delete=models.CASCADE,
        related_name="kyc_applications",
    )
    scope = models.CharField(
        max_length=16,
        choices=IntegrationScope.choices,
        db_index=True,
        help_text=_("Whether this packet backs SaaS invoicing or POS acquirer onboarding."),
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    legal_name = models.CharField(max_length=255, blank=True)
    trading_name = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(max_length=128, blank=True)
    tax_identifier = models.CharField(max_length=128, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=64, blank=True)
    registered_address = models.JSONField(blank=True, default=dict)

    documents_requested = models.JSONField(blank=True, default=list)
    manual_submission = models.JSONField(blank=True, default=dict)
    instant_qr_metadata = models.JSONField(blank=True, default=dict)

    reviewer_notes = models.TextField(blank=True)

    document_nrc = models.FileField(
        upload_to="payments/kyc/%Y/%m/",
        blank=True,
        help_text=_("National registration card payload (PRIVATE)."),
    )
    document_license = models.FileField(
        upload_to="payments/kyc/%Y/%m/",
        blank=True,
        help_text=_("Business / trade licence (PRIVATE)."),
    )

    class Meta:
        ordering = ("-created_at",)
        indexes = (
            models.Index(fields=("client", "scope", "status")),
        )
        verbose_name = _("Merchant KYC application")
        verbose_name_plural = _("Merchant KYC applications")

    def __str__(self) -> str:
        return f"{self.client.schema_name}:{self.scope}:{self.status}"


class TenantPaymentGateway(AbstractBaseModel):
    """Encrypted PSP credential bundle per storefront payment method slug."""

    payment_method = models.ForeignKey(
        "sales.PaymentMethod",
        on_delete=models.PROTECT,
        related_name="tenant_payment_gateways",
    )
    scope = models.CharField(
        max_length=16,
        choices=IntegrationScope.choices,
        default=IntegrationScope.POS,
        db_index=True,
    )
    merchant_id = models.CharField(max_length=255, blank=True)
    secret_key = models.TextField(blank=True, help_text="Encrypted at rest (Fernet).")
    public_key = models.TextField(blank=True)
    api_extra_credentials = models.JSONField(blank=True, default=dict)
    is_enabled = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = _("Tenant payment gateway")
        verbose_name_plural = _("Tenant payment gateways")
        constraints = (
            models.UniqueConstraint(
                fields=("payment_method", "scope"),
                name="payments_tpg_unique_payment_method_scope",
            ),
        )

    def save(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        from payments.encryption import encrypt_secret

        val = self.secret_key or ""
        if isinstance(val, str) and val.strip():
            self.secret_key = encrypt_secret(val)
        else:
            self.secret_key = ""
        super().save(*args, **kwargs)

    def get_decrypted_secret_key(self) -> str:
        from payments.encryption import decrypt_secret

        return decrypt_secret(self.secret_key)

    def __str__(self) -> str:
        return f"{self.payment_method.code}:{self.scope}:{'on' if self.is_enabled else 'off'}"
