"""Bootstrap SubscriptionPlan + demo tenant/domain rows (public PostgreSQL schema).

django-tenants keeps SHARED_APPS tables in ``PUBLIC_SCHEMA_NAME`` (usually ``public``).
Giving a tenant ``schema_name`` equal to that value merges TENANT_APP migrations into the
same PostgreSQL schema as shared tables and often conflicts when apps such as ``auth``
appear in both SHARED_APPS and TENANT_APPS. Prefer ``--schema-name public_store`` for
healthy multi-schema setups while still naming the tenant ``Public Store``.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from saas.models import SubscriptionPlan
from tenants.models import BusinessType, Client, Domain


def _default_retail_business_type() -> BusinessType:
    """Ensure bootstrap works on empty DB if migrations/seeding have not yet run."""
    retail, _ = BusinessType.objects.get_or_create(
        code="retail",
        defaults={"name": "Retail", "is_active": True},
    )
    return retail


class Command(BaseCommand):
    help = (
        "Create Free/Standard plan, default tenant row, and localhost domain idempotently "
        "(safe to re-run)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema-name",
            default="public",
            help=(
                "PostgreSQL schema name for the tenant row (default: public). "
                "Strongly prefer a non-public schema name in real deployments."
            ),
        )
        parser.add_argument(
            "--tenant-name",
            default="Public Store",
            help='Human-readable tenant name (default: "Public Store").',
        )
        parser.add_argument(
            "--domain",
            default="localhost",
            help='Hostname routed by TenantMainMiddleware (default: localhost).',
        )
        parser.add_argument(
            "--skip-public-schema-warning",
            action="store_true",
            help="Silence the warning when schema-name equals PUBLIC_SCHEMA_NAME.",
        )

    def handle(self, *args, **options):
        schema_name: str = options["schema_name"]
        tenant_name: str = options["tenant_name"]
        domain_host: str = options["domain"]
        skip_warning: bool = options["skip_public_schema_warning"]

        public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", "public")
        if schema_name == public_schema and not skip_warning:
            self.stderr.write(
                self.style.WARNING(
                    f'Tenant schema_name="{schema_name}" equals PUBLIC_SCHEMA_NAME. '
                    "TENANT_APP migrations may collide with SHARED_APPS in the same schema. "
                    'Consider `--schema-name public_store` unless you truly intend this.\n'
                    "Suppress with --skip-public-schema-warning.\n"
                )
            )

        plan, plan_created = SubscriptionPlan.objects.get_or_create(
            slug="free-standard",
            defaults={
                "name": "Free/Standard",
                "max_products": 5000,
                "max_branches": 50,
                "max_staff": None,
                "billing_interval": "",
                "is_public": True,
                "is_active": True,
            },
        )

        retail_bt = _default_retail_business_type()

        client, client_created = Client.objects.get_or_create(
            schema_name=schema_name,
            defaults={
                "name": tenant_name,
                "business_type": retail_bt,
                "subscription_plan": plan,
                "is_active": True,
            },
        )

        existing_domain = Domain.objects.filter(domain=domain_host).first()
        if existing_domain and existing_domain.tenant_id != client.pk:
            raise CommandError(
                f'Domain "{domain_host}" already belongs to tenant '
                f'"{existing_domain.tenant.schema_name}" (pk={existing_domain.tenant_id}). '
                "Resolve manually before bootstrapping."
            )

        domain, domain_created = Domain.objects.get_or_create(
            domain=domain_host,
            defaults={
                "tenant": client,
                "is_primary": True,
            },
        )

        if domain.tenant_id != client.pk:
            raise CommandError(
                f'Domain "{domain_host}" exists but points at the wrong tenant.'
            )

        if not domain.is_primary:
            domain.is_primary = True
            domain.save(update_fields=("is_primary",))

        sync_fields = []
        if client.name != tenant_name:
            client.name = tenant_name
            sync_fields.append("name")
        if client.subscription_plan_id != plan.pk:
            client.subscription_plan = plan
            sync_fields.append("subscription_plan")
        if client.business_type_id != retail_bt.pk:
            client.business_type = retail_bt
            sync_fields.append("business_type")
        if sync_fields:
            client.save(update_fields=sync_fields)

        self.stdout.write(
            self.style.SUCCESS(
                "Bootstrap complete:\n"
                f"  SubscriptionPlan slug={plan.slug!r} "
                f"({'created' if plan_created else 'existing'})\n"
                f'  Client schema={client.schema_name!r} name={client.name!r} '
                f"({'created' if client_created else 'existing'})\n"
                f'  Domain {domain.domain!r} primary={domain.is_primary} '
                f"({'created' if domain_created else 'existing'})\n"
            )
        )
