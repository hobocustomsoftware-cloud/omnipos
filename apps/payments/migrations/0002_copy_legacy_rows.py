# Manual data bridge: tenants/sales credential tables → payments.* before legacy drops.

from django.db import connection, migrations


def forwards_copy_legacy_rows(apps, schema_editor):  # type: ignore[no-untyped-def]
    from django_tenants.utils import get_public_schema_name

    schema_name = str(getattr(connection, "schema_name", "") or "")
    public = get_public_schema_name()

    MerchantKYC = apps.get_model("payments", "MerchantKYCApplication")
    OldKYC = apps.get_model("tenants", "MerchantKYCApplication")
    NewGW = apps.get_model("payments", "TenantPaymentGateway")
    OldGW = apps.get_model("sales", "TenantPaymentGateway")

    if schema_name == public:
        for row in OldKYC.objects.iterator():
            if MerchantKYC.objects.filter(pk=row.pk).exists():
                continue
            docs = row.documents_requested
            if docs is None:
                docs_req = []
            elif isinstance(docs, list):
                docs_req = docs
            else:
                docs_req = []

            MerchantKYC.objects.create(
                pk=row.pk,
                created_at=row.created_at,
                updated_at=row.updated_at,
                client_id=row.client_id,
                scope=row.scope,
                status=row.status,
                legal_name=row.legal_name,
                trading_name=row.trading_name,
                registration_number=row.registration_number,
                tax_identifier=row.tax_identifier,
                contact_email=row.contact_email,
                contact_phone=row.contact_phone,
                registered_address=row.registered_address or {},
                documents_requested=docs_req,
                manual_submission=row.manual_submission or {},
                instant_qr_metadata=row.instant_qr_metadata or {},
                reviewer_notes=row.reviewer_notes or "",
            )
        return

    for row in OldGW.objects.iterator():
        if NewGW.objects.filter(pk=row.pk).exists():
            continue
        NewGW.objects.create(
            pk=row.pk,
            created_at=row.created_at,
            updated_at=row.updated_at,
            payment_method_id=row.payment_method_id,
            scope=row.scope,
            merchant_id=row.merchant_id or "",
            secret_key=row.secret_key or "",
            public_key=row.public_key or "",
            api_extra_credentials=row.api_extra_credentials or {},
            is_enabled=row.is_enabled,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
        ("sales", "0002_fintech_engine"),
        ("tenants", "0005_fintech_engine"),
    ]

    operations = [
        migrations.RunPython(forwards_copy_legacy_rows, migrations.RunPython.noop),
    ]
