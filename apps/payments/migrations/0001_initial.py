# django-tenants routing: MerchantKYC table on public schema only;
# TenantPaymentGateway on tenant schemas only (FK sales.PaymentMethod).
# SeparateDatabaseAndState updates project state first; sibling RunPython below
# runs DDL with a MigrationState whose apps registry already includes models.

import django.db.models.deletion
import uuid
from django.db import connection, migrations, models


def forwards_create_merchant_kyc_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    from django_tenants.utils import get_public_schema_name

    if connection.schema_name != get_public_schema_name():
        return
    model = apps.get_model("payments", "MerchantKYCApplication")
    schema_editor.create_model(model)


def backwards_drop_merchant_kyc_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    from django_tenants.utils import get_public_schema_name

    if connection.schema_name != get_public_schema_name():
        return
    model = apps.get_model("payments", "MerchantKYCApplication")
    schema_editor.delete_model(model)


def forwards_create_tenant_gateway_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    from django_tenants.utils import get_public_schema_name

    if connection.schema_name == get_public_schema_name():
        return
    model = apps.get_model("payments", "TenantPaymentGateway")
    schema_editor.create_model(model)


def backwards_drop_tenant_gateway_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    from django_tenants.utils import get_public_schema_name

    if connection.schema_name == get_public_schema_name():
        return
    model = apps.get_model("payments", "TenantPaymentGateway")
    schema_editor.delete_model(model)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("sales", "0002_fintech_engine"),
        ("tenants", "0005_fintech_engine"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="MerchantKYCApplication",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "scope",
                            models.CharField(
                                choices=[("saas", "SaaS billing"), ("pos", "POS / storefront")],
                                db_index=True,
                                help_text="Whether this packet backs SaaS invoicing or POS acquirer onboarding.",
                                max_length=16,
                            ),
                        ),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("draft", "Draft"),
                                    ("submitted", "Submitted"),
                                    ("under_review", "Under review"),
                                    ("approved", "Approved"),
                                    ("rejected", "Rejected"),
                                    ("changes_requested", "Changes requested"),
                                ],
                                db_index=True,
                                default="draft",
                                max_length=24,
                            ),
                        ),
                        ("legal_name", models.CharField(blank=True, max_length=255)),
                        ("trading_name", models.CharField(blank=True, max_length=255)),
                        ("registration_number", models.CharField(blank=True, max_length=128)),
                        ("tax_identifier", models.CharField(blank=True, max_length=128)),
                        ("contact_email", models.EmailField(blank=True, max_length=254)),
                        ("contact_phone", models.CharField(blank=True, max_length=64)),
                        ("registered_address", models.JSONField(blank=True, default=dict)),
                        ("documents_requested", models.JSONField(blank=True, default=list)),
                        ("manual_submission", models.JSONField(blank=True, default=dict)),
                        ("instant_qr_metadata", models.JSONField(blank=True, default=dict)),
                        ("reviewer_notes", models.TextField(blank=True)),
                        (
                            "document_nrc",
                            models.FileField(
                                blank=True,
                                help_text="National registration card payload (PRIVATE).",
                                upload_to="payments/kyc/%Y/%m/",
                            ),
                        ),
                        (
                            "document_license",
                            models.FileField(
                                blank=True,
                                help_text="Business / trade licence (PRIVATE).",
                                upload_to="payments/kyc/%Y/%m/",
                            ),
                        ),
                        (
                            "client",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="kyc_applications",
                                to="tenants.client",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Merchant KYC application",
                        "verbose_name_plural": "Merchant KYC applications",
                        "ordering": ("-created_at",),
                        "indexes": [
                            models.Index(
                                fields=["client", "scope", "status"],
                                name="payments_me_client__6bd20a_idx",
                            ),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(forwards_create_merchant_kyc_table, backwards_drop_merchant_kyc_table),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="TenantPaymentGateway",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "scope",
                            models.CharField(
                                choices=[("saas", "SaaS billing"), ("pos", "POS / storefront")],
                                db_index=True,
                                default="pos",
                                max_length=16,
                            ),
                        ),
                        ("merchant_id", models.CharField(blank=True, max_length=255)),
                        (
                            "secret_key",
                            models.TextField(blank=True, help_text="Encrypted at rest (Fernet)."),
                        ),
                        ("public_key", models.TextField(blank=True)),
                        ("api_extra_credentials", models.JSONField(blank=True, default=dict)),
                        ("is_enabled", models.BooleanField(db_index=True, default=True)),
                        (
                            "payment_method",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="tenant_payment_gateways",
                                to="sales.paymentmethod",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Tenant payment gateway",
                        "verbose_name_plural": "Tenant payment gateways",
                        "constraints": [
                            models.UniqueConstraint(
                                fields=("payment_method", "scope"),
                                name="payments_tpg_unique_payment_method_scope",
                            ),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(forwards_create_tenant_gateway_table, backwards_drop_tenant_gateway_table),
    ]
