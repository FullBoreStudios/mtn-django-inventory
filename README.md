# mtn-django-inventory

Reusable Django app for inventory management. Admin-first, plug-n-play, works with any Django project.

Built for tracking IT hardware (Ubiquiti, cameras, cable, etc.) but general enough for any industry.

---

## Features

- **Items** — serialized (serial# tracked) or bulk (quantity + unit)
- **Categories** — hierarchical (parent/child)
- **Locations** — physical locations
- **Clients** — swappable client model (mirrors `AUTH_USER_MODEL` pattern)
- **User assignment** — assign items to staff via `AUTH_USER_MODEL`
- **Custom fields** — per-category EAV fields (text, number, date, boolean, URL)
- **Status tracking** — In Stock / In Use / Maintenance / Retired / Disposed
- **Audit log** — tracks status/location/client/assignment changes
- **Asset tags** — auto-generated on save (`ASSET-00001`, configurable prefix/padding)
- **Label printing** — print-ready thermal labels with QR code; label dimensions managed via `LabelFormat` admin model (default: 3.5in × 1.1in)
- **CSV export** — admin action exports filtered items
- **CSV import** — upload CSV with preview/confirm step

---

## Installation

```bash
pip install mtn-django-inventory
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'inventory',
]
```

Run migrations:

```bash
python manage.py migrate
```

---

## Settings

Add an `INVENTORY` dict to your Django settings (all optional):

```python
INVENTORY = {
    'BASE_TEMPLATE': 'base.html',  # template to extend in any package views
    'ENABLE_CLIENT': True,         # set False to hide the Client field on all Item admin views
    'ASSET_TAG_AUTO': True,        # auto-generate asset tag on save when blank
    'ASSET_TAG_PREFIX': 'ASSET',   # prefix for generated tags, e.g. 'ASSET' → 'ASSET-00001'
    'ASSET_TAG_PADDING': 5,        # zero-pad width for the numeric portion
}
```

---

## Swapping the Client Model

By default the package uses its own built-in `Client` model. To point to an existing model in your project (e.g. a CRM customer model), set `INVENTORY_CLIENT_MODEL` **before running your first migration**:

```python
# settings.py
INVENTORY_CLIENT_MODEL = 'crm.Customer'  # default: 'inventory.Client'
```

The target model must exist and be migrated before installing this package. This follows the same pattern as Django's `AUTH_USER_MODEL`.

If you change this after the initial migration you'll need to write a data migration to update the FK references.

---

## Label Printing

Label dimensions are managed via the **Label Formats** section in Django admin. A default `3.5in × 1.1in` format (standard Dymo/thermal label) is created automatically on first migrate.

Labels include the asset tag (large), item name, manufacturer, serial number, and a QR code encoding the asset tag and serial number. They auto-print on page load.

### Admin (zero config)

- Click the **🏷 Label** link on any row in the Items changelist
- Select items and use the **Print labels for selected items** action for bulk printing

### Public URLs (optional)

Include in your project's `urls.py` to expose label views outside the admin:

```python
path('inventory/', include('inventory.urls', namespace='inventory')),
```

Then access:
- `/inventory/labels/<pk>/` — single item label
- `/inventory/labels/?ids=1,2,3` — bulk labels
- Add `?format=<pk>` to either URL to use a specific `LabelFormat`

---

## CSV Import Format

Required column: `name`

Optional columns:

| Column | Notes |
|---|---|
| `asset_tag` | Must be unique |
| `item_type` | `serialized` or `bulk` |
| `status` | `in_stock`, `in_use`, `maintenance`, `retired`, `disposed` |
| `category` | Matched by name (case-insensitive) |
| `manufacturer` | |
| `model_number` | |
| `serial_number` | |
| `quantity` | Numeric |
| `unit` | `each`, `ft`, `m`, `box`, `roll`, `lot` |
| `purchase_date` | `YYYY-MM-DD` |
| `warranty_expiry` | `YYYY-MM-DD` |
| `purchase_price` | Numeric |
| `location` | Matched by name (case-insensitive) |
| `client` | Matched by name (case-insensitive) |
| `notes` | |

Unmatched `category`, `location`, and `client` values are silently skipped (item is still created).

---

## Applying to fulcrumsupport

1. Install: `pip install mtn-django-inventory` (or add path dependency in pyproject.toml during dev)
2. Add `'inventory'` to `INSTALLED_APPS`
3. Run `python manage.py migrate`
4. Log into admin — Category, Location, Client, and Item sections appear

Suggested initial categories for IT hardware:

```
Hardware
  Network
    Ubiquiti
    Switches
    Routers
  Security
    Cameras
    NVR
  Cabling
    Cat6
    Fiber
    Coax
  Compute
    Servers
    Workstations
```
