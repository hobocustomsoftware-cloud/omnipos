# OmniPOS

**Universal SaaS Point-of-Sale** — Django multi-tenant backend with Flutter mobile frontend.

Built for multiple business verticals (Retail, Workshop, Pharmacy, Welding, …) from a single codebase. Each tenant runs in an isolated PostgreSQL schema via `django-tenants`.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Apps & Architecture](#apps--architecture)
- [API Endpoints](#api-endpoints)
- [Multi-Tenancy](#multi-tenancy)
- [Business Types](#business-types)
- [Frontend (Flutter)](#frontend-flutter)
- [Running Tests](#running-tests)
- [Contributing](#contributing)

---

## Overview

OmniPOS solves the problem of running a single POS platform across fundamentally different business types. A welding shop, a pharmacy, and a retail store all need inventory, sales, and payments — but their workflows, units of measure, and UI layouts differ.

The solution: a **Universal core** (products, orders, inventory, accounting) extended by `JSONField` metadata and `BusinessType`-driven UI schemas. The Flutter frontend conditionally renders based on the tenant's business type — no separate apps needed.

Key capabilities:

- Multi-tenant PostgreSQL schema isolation (one schema per tenant)
- Dynamic UI configuration per `BusinessType` delivered to Flutter via REST
- Barcode / SKU scan with retail vs wholesale pricing resolution
- Branch-scoped inventory with atomic stock commits
- Offline-first mobile sync via incremental product catalogue endpoint
- KYC merchant onboarding and SaaS subscription plan enforcement

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 5.1 |
| Multi-tenancy | django-tenants 3.7+ |
| REST API | Django REST Framework 3.15+ |
| Database | PostgreSQL (psycopg 3) |
| Admin UI | django-unfold |
| Mobile frontend | Flutter (Dart SDK ^3.10) |
| Authentication | Session + (JWT recommended — see setup) |

---

## Project Structure

```
omnipos/
├── config/
│   ├── settings.py          # Django settings (env-driven)
│   ├── urls.py              # Root URL config
│   ├── test_runner.py       # Tenant-aware test runner
│   └── wsgi.py / asgi.py
│
├── apps/
│   ├── core/                # Shared abstract models (UUID + timestamps)
│   ├── tenants/             # Public schema: Client, Domain, BusinessType
│   ├── saas/                # Public schema: SubscriptionPlan, PaymentLog
│   ├── accounts/            # Tenant: User roles, StaffProfile, branch RBAC
│   ├── catalog/             # Tenant: Product, Branch, Order, UnitOfMeasure
│   ├── inventory/           # Tenant: ProductStock, receiving service
│   ├── sales/               # Tenant: Checkout, OrderPayment, invoice
│   ├── accounting/          # Tenant: DebtLedger (AR/AP)
│   ├── contacts/            # Tenant: Customer, Supplier, PurchaseOrder
│   └── payments/            # Shared: KYC, PSP gateway credentials
│
├── omnipos_frontend/        # Flutter mobile app
│   └── lib/
│       ├── core/            # Theme, network, routing
│       └── features/
│           ├── auth/        # Staff sign-in
│           ├── pos/         # Counter / catalog
│           ├── inventory/
│           └── accounting/
│
├── requirements.txt
└── manage.py
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 14+
- Flutter SDK 3.10+

### 1. Clone the repository

```bash
git clone https://github.com/hobocustomsoftware-cloud/omnipos.git
cd omnipos
```

### 2. Set up Python environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root (never commit this file):

```env
DJANGO_SECRET_KEY=your-strong-random-secret-key
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=yourdomain.com,localhost

PGDATABASE=omnipos
PGUSER=postgres
PGPASSWORD=your-db-password
PGHOST=localhost
PGPORT=5432
```

### 4. Create the database and run migrations

```bash
# Create the public schema tables (tenants, saas, payments)
python manage.py migrate_schemas --shared

# Create your first tenant
python manage.py shell
```

```python
from tenants.models import Client, Domain, BusinessType

bt = BusinessType.objects.create(code="retail", name="Retail")
tenant = Client.objects.create(
    schema_name="tenant_demo",
    name="Demo Store",
    business_type=bt,
)
Domain.objects.create(tenant=tenant, domain="demo.localhost", is_primary=True)
```

```bash
# Run tenant migrations
python manage.py migrate_schemas
```

### 5. Create a superuser

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

Access the admin at `http://localhost/admin/` (use the `public` schema domain).

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(required)* | Django secret key — generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_DEBUG` | `false` | Set to `true` for local dev only |
| `DJANGO_ALLOWED_HOSTS` | `*` | Comma-separated allowed hostnames |
| `PGDATABASE` | `omnipos` | PostgreSQL database name |
| `PGUSER` | `postgres` | PostgreSQL user |
| `PGPASSWORD` | *(required)* | PostgreSQL password |
| `PGHOST` | `localhost` | PostgreSQL host |
| `PGPORT` | `5432` | PostgreSQL port |

> ⚠️ Never set fallback values for `PGPASSWORD` or `DJANGO_SECRET_KEY` in `settings.py`. Use `.env` files or a secrets manager in production.

---

## Apps & Architecture

### Public schema (shared across all tenants)

| App | Purpose |
|---|---|
| `tenants` | `Client` (tenant row + schema), `Domain` (hostname routing), `BusinessType` |
| `saas` | `SubscriptionPlan` (tier limits), `PaymentLog` (SaaS billing observability) |
| `payments` | `MerchantKYCApplication`, PSP gateway credentials |
| `core` | `AbstractBaseModel` (UUID primary key + timestamps) |

### Tenant schema (isolated per tenant)

| App | Purpose |
|---|---|
| `accounts` | `Role` (RBAC), `StaffProfile`, branch assignments |
| `catalog` | `Product` (universal SKU), `Branch`, `Order`, `OrderItem`, `UnitOfMeasure` |
| `inventory` | `ProductStock` (branch × SKU quantities), receiving service |
| `sales` | `CheckoutAPIView`, `OrderPayment`, invoice generation |
| `accounting` | `DebtLedgerEntry` (AR customers / AP suppliers) |
| `contacts` | `Customer`, `Supplier`, `PurchaseOrder` |

### Product metadata structure

`Product.metadata` is a PostgreSQL JSONB field. The informal contract:

```json
{
  "schema_version": 1,
  "regulated": {
    "requires_expiry": true,
    "batch_tracked": true,
    "default_shelf_life_days": 365
  },
  "electronics": {
    "warranty_months": 12,
    "serial_tracked": true
  },
  "units": {
    "base": "EA",
    "conversions": [
      { "uom": "PACK", "to_base": 6 },
      { "uom": "CASE", "to_base": 72 }
    ]
  }
}
```

---

## API Endpoints

All endpoints are prefixed with `/api/`. Branch context is passed via the `X-Branch-Id` header or `?branch_id=<uuid>` query parameter.

### Accounts

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `api/accounts/user/profile/` | Authenticated staff profile + role |
| `GET` | `api/accounts/user/branches/` | Branches assigned to the current user |

### Catalog

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `api/catalog/config/` | UI config + applicable units for the tenant's `BusinessType` |
| `GET` | `api/catalog/products/scan/?barcode=<code>` | Resolve scan code → product + pricing |
| `GET` | `api/catalog/products/incremental/?last_synced_at=<iso8601>` | Delta sync for offline-first mobile |

### Sales

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `api/sales/checkout/` | Create confirmed order + tenders + stock commit |
| `POST` | `api/sales/orders/bulk-sync/` | Offline-first order upload from mobile |
| `GET` | `api/sales/orders/<uuid>/invoice/` | Download PDF invoice |
| `GET` | `api/sales/merchant/dashboard/payments/` | Daily payment dashboard by method |

### Inventory / Contacts / Accounting / Payments

Additional endpoints are registered under `api/inventory/`, `api/contacts/`, `api/accounting/`, and `api/payments/`.

---

## Multi-Tenancy

OmniPOS uses `django-tenants` with **PostgreSQL schema isolation**. Each `Client` record maps to a dedicated schema.

- The **public** schema holds `tenants`, `saas`, and `payments` tables.
- Every other app (`catalog`, `accounts`, `inventory`, etc.) lives inside the tenant's own schema.
- `TenantMainMiddleware` must remain **first** in `MIDDLEWARE` to route requests to the correct schema.
- Tenant context is accessible via `connection.tenant` or `request.tenant` anywhere in the request lifecycle.

To run a management command against a specific tenant:

```bash
python manage.py tenant_command <command> --schema=<schema_name>
```

---

## Business Types

`BusinessType` rows are managed from Django Admin by super-admins. Each tenant is linked to one business type, which controls:

- which `UnitOfMeasure` entries are visible (via M2M tags)
- the Flutter UI layout preset (`ui_schema` JSONField)
- conditional rendering on the mobile POS (retail grid vs workshop job cards, etc.)

Built-in layout presets: `retail_inventory`, `workshop_service`, `appointment_first`. Unknown slugs fall back to a generic adaptive preset.

---

## Frontend (Flutter)

The Flutter app lives in `omnipos_frontend/`.

```bash
cd omnipos_frontend
flutter pub get
flutter run --dart-define=API_BASE_URL=http://localhost:8000/
```

For release builds:

```bash
flutter build apk --dart-define=API_BASE_URL=https://api.yourdomain.com/
```

The app calls `GET api/catalog/config/` at login to receive the tenant's UI schema and dynamically renders the POS interface based on `business_type`.

---

## Running Tests

OmniPOS uses a custom `OmniPOSTenantTestRunner` that handles schema lifecycle for tests.

```bash
# Run all tests
python manage.py test

# Run a specific app
python manage.py test apps.catalog
python manage.py test apps.inventory
```

Test files are located in each app's `tests/` directory or `tests.py`.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Follow the Master Orchestration Prompt workflow: PLAN → BUILD → TEST → VERIFY → AUDIT → UX → DOCS.
3. Ensure all new features include unit tests (especially inventory and pricing logic).
4. Add a `.gitattributes` entry (`*.py text eol=lf`) to prevent CRLF line ending issues.
5. Open a pull request with a clear description of the change.

---

## License

Private — © Hobo Custom Software. All rights reserved.
