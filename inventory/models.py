from django.db import models
from django.conf import settings


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class Category(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='children'
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        if self.parent:
            return f'{self.parent} > {self.name}'
        return self.name


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

class Location(models.Model):
    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Client
# Swappable via INVENTORY_CLIENT_MODEL setting (mirrors AUTH_USER_MODEL pattern).
# Default: 'inventory.Client' (this model).
# ---------------------------------------------------------------------------

class Client(models.Model):
    name = models.CharField(max_length=150)
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        # Enables Django's swappable mechanism — sites set INVENTORY_CLIENT_MODEL
        # to point to their own client/customer model.
        swappable = 'INVENTORY_CLIENT_MODEL'

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class Item(models.Model):

    class Status(models.TextChoices):
        IN_STOCK = 'in_stock', 'In Stock'
        IN_USE = 'in_use', 'In Use'
        MAINTENANCE = 'maintenance', 'Maintenance'
        RETIRED = 'retired', 'Retired'
        DISPOSED = 'disposed', 'Disposed'

    class ItemType(models.TextChoices):
        SERIALIZED = 'serialized', 'Serialized (tracked individually)'
        BULK = 'bulk', 'Bulk (quantity-based)'

    class Unit(models.TextChoices):
        EACH = 'each', 'Each'
        FEET = 'ft', 'Feet'
        METERS = 'm', 'Meters'
        BOX = 'box', 'Box'
        ROLL = 'roll', 'Roll'
        LOT = 'lot', 'Lot'

    # Identity
    name = models.CharField(max_length=200)
    asset_tag = models.CharField(max_length=100, unique=True, blank=True, null=True)
    item_type = models.CharField(max_length=20, choices=ItemType.choices, default=ItemType.SERIALIZED)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_STOCK)
    category = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='items'
    )

    # Hardware details
    manufacturer = models.CharField(max_length=100, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=200, blank=True)

    # Quantity (primarily for bulk items; serialized items default to 1)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.EACH)

    # Dates & financials
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Assignment
    location = models.ForeignKey(
        Location, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='items'
    )
    client = models.ForeignKey(
        'inventory.Client',
        null=True, blank=True,
        on_delete=models.SET_NULL, related_name='inventory_items',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_inventory_items'
    )

    notes = models.TextField(blank=True)

    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_inventory_items'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='updated_inventory_items'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Custom Fields (EAV)
# ---------------------------------------------------------------------------

class CustomFieldDef(models.Model):

    class FieldType(models.TextChoices):
        TEXT = 'text', 'Text'
        NUMBER = 'number', 'Number'
        DATE = 'date', 'Date'
        BOOLEAN = 'boolean', 'Yes / No'
        URL = 'url', 'URL'

    category = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='custom_field_defs',
        help_text='Leave blank to apply to all items regardless of category.'
    )
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FieldType.choices, default=FieldType.TEXT)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Custom Field Definition'
        verbose_name_plural = 'Custom Field Definitions'

    def __str__(self):
        scope = str(self.category) if self.category else 'All Categories'
        return f'{self.name} [{scope}]'


class CustomFieldValue(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='custom_field_values')
    field_def = models.ForeignKey(CustomFieldDef, on_delete=models.CASCADE, related_name='values')
    value = models.TextField(blank=True)

    class Meta:
        unique_together = [('item', 'field_def')]
        verbose_name = 'Custom Field Value'
        verbose_name_plural = 'Custom Field Values'

    def __str__(self):
        return f'{self.field_def.name}: {self.value}'


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditEvent(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='audit_events')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='inventory_audit_events'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Event'
        verbose_name_plural = 'Audit Events'

    def __str__(self):
        return f'{self.item} — {self.field_name} at {self.timestamp:%Y-%m-%d %H:%M}'
