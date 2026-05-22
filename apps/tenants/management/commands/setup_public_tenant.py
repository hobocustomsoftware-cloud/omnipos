"""Idempotent bootstrap: Standard Free plan + public-schema tenant + localhost domain."""

from django.core.management.base import BaseCommand, CommandError

from saas.models import SubscriptionPlan
from tenants.models import BusinessType, Client, Domain


def _default_retail_business_type() -> BusinessType:
    retail, _ = BusinessType.objects.get_or_create(
        code="retail",
        defaults={"name": "Retail", "is_active": True},
    )
    return retail


class Command(BaseCommand):
    help = "Create Standard Free subscription plan, public tenant Client, and localhost Domain (safe to re-run)."

    def handle(self, *args, **options):
        plan, plan_created = SubscriptionPlan.objects.get_or_create(
            slug="standard-free",
            defaults={
                "name": "Standard Free",
                "max_products": 50,
                "max_branches": 1,
                "max_staff": None,
                "billing_interval": "",
                "is_public": True,
                "is_active": True,
            },
        )

        retail_bt = _default_retail_business_type()

        client, client_created = Client.objects.get_or_create(
            schema_name="public",
            defaults={
                "name": "OmniPOS Public",
                "business_type": retail_bt,
                "subscription_plan": plan,
                "is_active": True,
            },
        )

        conflict = Domain.objects.filter(domain="localhost").exclude(tenant_id=client.pk).first()
        if conflict:
            raise CommandError(
                f'Domain "localhost" is already mapped to tenant '
                f'"{conflict.tenant.schema_name}" (pk={conflict.tenant_id}).'
            )

        domain, domain_created = Domain.objects.get_or_create(
            domain="localhost",
            defaults={
                "tenant": client,
                "is_primary": True,
            },
        )

        if domain.tenant_id != client.pk:
            raise CommandError('Domain "localhost" exists but points at a different tenant.')

        if not domain.is_primary:
            domain.is_primary = True
            domain.save(update_fields=("is_primary",))

        sync = []
        if client.subscription_plan_id != plan.pk:
            client.subscription_plan = plan
            sync.append("subscription_plan")
        if client.name != "OmniPOS Public":
            client.name = "OmniPOS Public"
            sync.append("name")
        if client.business_type_id != retail_bt.pk:
            client.business_type = retail_bt
            sync.append("business_type")
        if sync:
            client.save(update_fields=sync)

        self.stdout.write(
            self.style.SUCCESS(
                "setup_public_tenant finished:\n"
                f"  SubscriptionPlan slug={plan.slug!r} ({'created' if plan_created else 'already present'})\n"
                f"  Client schema={client.schema_name!r} ({'created' if client_created else 'already present'})\n"
                f"  Domain localhost ({'created' if domain_created else 'already present'}, primary={domain.is_primary})\n"
            )
        )
