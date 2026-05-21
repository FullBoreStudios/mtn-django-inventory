import csv
import io
import os
import tempfile
from datetime import date, datetime

from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    AuditEvent, Category, Client, CustomFieldDef,
    CustomFieldValue, Item, Location,
)
from .conf import inventory_setting

_ENABLE_CLIENT = inventory_setting('ENABLE_CLIENT')


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'item_count']
    list_filter = ['parent']
    search_fields = ['name']
    ordering = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_item_count=Count('items'))

    def item_count(self, obj):
        return obj._item_count
    item_count.short_description = 'Items'
    item_count.admin_order_field = '_item_count'


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'item_count']
    search_fields = ['name', 'address']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_item_count=Count('items'))

    def item_count(self, obj):
        return obj._item_count
    item_count.short_description = 'Items'
    item_count.admin_order_field = '_item_count'


# ---------------------------------------------------------------------------
# Client — only registered when the built-in model is not swapped out
# ---------------------------------------------------------------------------

class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_name', 'contact_email', 'contact_phone', 'item_count']
    search_fields = ['name', 'contact_name', 'contact_email']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_item_count=Count('inventory_items'))

    def item_count(self, obj):
        return obj._item_count
    item_count.short_description = 'Items'
    item_count.admin_order_field = '_item_count'


if not Client._meta.swapped:
    admin.site.register(Client, ClientAdmin)


# ---------------------------------------------------------------------------
# Custom Field Definitions
# ---------------------------------------------------------------------------

@admin.register(CustomFieldDef)
class CustomFieldDefAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'field_type', 'required', 'order']
    list_filter = ['field_type', 'required', 'category']
    search_fields = ['name']
    ordering = ['order', 'name']


# ---------------------------------------------------------------------------
# Custom Field Values inline (on Item)
# ---------------------------------------------------------------------------

class CustomFieldValueInline(admin.TabularInline):
    model = CustomFieldValue
    extra = 0
    fields = ['field_def', 'value']
    autocomplete_fields = ['field_def']


# ---------------------------------------------------------------------------
# Audit Events inline (read-only on Item)
# ---------------------------------------------------------------------------

class AuditEventInline(admin.TabularInline):
    model = AuditEvent
    extra = 0
    readonly_fields = ['timestamp', 'user', 'field_name', 'old_value', 'new_value', 'note']
    fields = ['timestamp', 'user', 'field_name', 'old_value', 'new_value', 'note']
    can_delete = False
    max_num = 0

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-timestamp')

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

class CSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Required columns: name. Optional: asset_tag, item_type, status, category, '
                  'manufacturer, model_number, serial_number, quantity, unit, purchase_date, '
                  'warranty_expiry, purchase_price, location, client, notes',
    )


CSV_EXPORT_FIELDS = [
    'id', 'name', 'asset_tag', 'item_type', 'status', 'category',
    'manufacturer', 'model_number', 'serial_number',
    'quantity', 'unit', 'purchase_date', 'warranty_expiry', 'purchase_price',
    'location', 'client', 'assigned_to', 'notes', 'created_at', 'updated_at',
]

CSV_IMPORT_FIELD_NAMES = [
    'name', 'asset_tag', 'item_type', 'status',
    'manufacturer', 'model_number', 'serial_number',
    'quantity', 'unit', 'purchase_date', 'warranty_expiry', 'purchase_price', 'notes',
]

TRACKED_FIELDS = ['status', 'location', 'client', 'assigned_to']


def _export_items_csv(queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_export.csv"'
    writer = csv.writer(response)
    writer.writerow(CSV_EXPORT_FIELDS)
    for item in queryset.select_related('category', 'location', 'client', 'assigned_to'):
        writer.writerow([
            item.id,
            item.name,
            item.asset_tag or '',
            item.item_type,
            item.status,
            str(item.category) if item.category else '',
            item.manufacturer,
            item.model_number,
            item.serial_number,
            item.quantity,
            item.unit,
            item.purchase_date or '',
            item.warranty_expiry or '',
            item.purchase_price or '',
            str(item.location) if item.location else '',
            str(item.client) if item.client else '',
            str(item.assigned_to) if item.assigned_to else '',
            item.notes,
            item.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            item.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        ])
    return response


def _parse_csv_rows(file_obj):
    """Parse uploaded CSV file object, return (fieldnames, rows) or raise ValueError."""
    try:
        text = file_obj.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        file_obj.seek(0)
        text = file_obj.read().decode('latin-1')
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError('CSV file is empty.')
    if 'name' not in (reader.fieldnames or []):
        raise ValueError("CSV must contain a 'name' column.")
    return reader.fieldnames, rows


def _write_rows_to_tempfile(fieldnames, rows):
    """Write rows to a temp file, return path. Caller must delete the file."""
    fd, path = tempfile.mkstemp(suffix='.csv', prefix='inv_import_', text=True)
    try:
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception:
        os.unlink(path)
        raise
    return path


def _read_rows_from_tempfile(path):
    """Read and return rows from a temp file written by _write_rows_to_tempfile."""
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _row_to_item_kwargs(row):
    """Convert a CSV row dict to Item field kwargs, excluding FK fields."""
    kwargs = {}
    for field in CSV_IMPORT_FIELD_NAMES:
        val = row.get(field, '').strip()
        if val:
            kwargs[field] = val
    for field in ('quantity', 'purchase_price'):
        if field in kwargs:
            try:
                kwargs[field] = float(kwargs[field])
            except ValueError:
                del kwargs[field]
    for field in ('purchase_date', 'warranty_expiry'):
        if field in kwargs:
            try:
                kwargs[field] = datetime.strptime(kwargs[field], '%Y-%m-%d').date()
            except ValueError:
                del kwargs[field]
    return kwargs


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

_item_list_display = [
    'name', 'asset_tag', 'status_badge', 'item_type', 'category',
    'manufacturer', 'serial_number', 'location',
    *(['client'] if _ENABLE_CLIENT else []),
    'assigned_to', 'warranty_status',
]

_item_list_filter = [
    'status', 'item_type', 'category', 'location',
    *(['client'] if _ENABLE_CLIENT else []),
]

_item_autocomplete = [
    'category', 'location', 'assigned_to',
    *(['client'] if _ENABLE_CLIENT else []),
]

_assignment_fields = (
    'location',
    *(['client'] if _ENABLE_CLIENT else []),
    'assigned_to',
)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = _item_list_display
    list_filter = _item_list_filter
    search_fields = [
        'name', 'asset_tag', 'serial_number', 'model_number',
        'manufacturer', 'notes',
    ]
    autocomplete_fields = _item_autocomplete
    readonly_fields = ['created_by', 'updated_by', 'created_at', 'updated_at']
    inlines = [CustomFieldValueInline, AuditEventInline]
    actions = ['export_csv']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Identity', {
            'fields': ('name', 'asset_tag', 'item_type', 'status', 'category'),
        }),
        ('Hardware Details', {
            'fields': ('manufacturer', 'model_number', 'serial_number'),
        }),
        ('Quantity', {
            'fields': ('quantity', 'unit'),
            'description': 'For serialized items quantity is 1. '
                           'For bulk items (cable, consumables) set quantity and unit.',
        }),
        ('Dates & Financials', {
            'fields': ('purchase_date', 'warranty_expiry', 'purchase_price'),
            'classes': ('collapse',),
        }),
        ('Assignment', {
            'fields': _assignment_fields,
        }),
        ('Notes', {
            'fields': ('notes',),
        }),
        ('Record', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    STATUS_COLORS = {
        'in_stock': '#28a745',
        'in_use': '#007bff',
        'maintenance': '#fd7e14',
        'retired': '#6c757d',
        'disposed': '#343a40',
    }

    def status_badge(self, obj):
        color = self.STATUS_COLORS.get(obj.status, '#999')
        label = obj.get_status_display()
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:3px;'
            'font-size:11px;font-weight:600">{}</span>',
            color, label,
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def warranty_status(self, obj):
        if not obj.warranty_expiry:
            return '—'
        today = date.today()
        delta = (obj.warranty_expiry - today).days
        if delta < 0:
            return format_html('<span style="color:#dc3545">Expired {}</span>', obj.warranty_expiry)
        if delta <= 90:
            return format_html('<span style="color:#fd7e14">Expires {}</span>', obj.warranty_expiry)
        return format_html('<span style="color:#28a745">{}</span>', obj.warranty_expiry)
    warranty_status.short_description = 'Warranty'

    # ------------------------------------------------------------------
    # Audit tracking on save
    # ------------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        else:
            old = Item.objects.get(pk=obj.pk)
            for field in TRACKED_FIELDS:
                old_val = str(getattr(old, field) or '')
                new_val = str(getattr(obj, field) or '')
                if old_val != new_val:
                    AuditEvent.objects.create(
                        item=old,
                        user=request.user,
                        field_name=field,
                        old_value=old_val,
                        new_value=new_val,
                    )
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    # ------------------------------------------------------------------
    # CSV Export action
    # ------------------------------------------------------------------

    @admin.action(description='Export selected items to CSV')
    def export_csv(self, request, queryset):
        return _export_items_csv(queryset)

    # ------------------------------------------------------------------
    # CSV Import — custom admin URL + view
    # ------------------------------------------------------------------

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                'import-csv/',
                self.admin_site.admin_view(self.import_csv_view),
                name='inventory_item_import_csv',
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_csv_url'] = reverse('admin:inventory_item_import_csv')
        return super().changelist_view(request, extra_context=extra_context)

    def import_csv_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            'title': 'Import Items from CSV',
            'opts': self.model._meta,
        }

        if request.method == 'POST' and 'confirm' in request.POST:
            tmp_path = request.session.pop('csv_import_tmp', None)
            if not tmp_path or not os.path.exists(tmp_path):
                self.message_user(
                    request,
                    'Import session expired — please re-upload the file.',
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(reverse('admin:inventory_item_import_csv'))

            try:
                rows = _read_rows_from_tempfile(tmp_path)
            finally:
                os.unlink(tmp_path)

            created, errors = 0, []
            for i, row in enumerate(rows, 1):
                try:
                    kwargs = _row_to_item_kwargs(row)
                    for model_cls, field, lookup in [
                        (Category, 'category', 'name__iexact'),
                        (Location, 'location', 'name__iexact'),
                        (Client, 'client', 'name__iexact'),
                    ]:
                        raw = row.get(field, '').strip()
                        if raw:
                            match = model_cls.objects.filter(**{lookup: raw}).first()
                            kwargs[field] = match  # None if not found — field stays blank
                    item = Item(**kwargs)
                    item.created_by = request.user
                    item.updated_by = request.user
                    item.full_clean()
                    item.save()
                    created += 1
                except Exception as e:
                    errors.append(f'Row {i} ({row.get("name", "?")}): {e}')

            for err in errors:
                self.message_user(request, err, level=messages.WARNING)
            self.message_user(request, f'{created} item(s) imported successfully.')
            return HttpResponseRedirect(reverse('admin:inventory_item_changelist'))

        if request.method == 'POST':
            form = CSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    fieldnames, rows = _parse_csv_rows(request.FILES['csv_file'])
                    tmp_path = _write_rows_to_tempfile(fieldnames, rows)
                    request.session['csv_import_tmp'] = tmp_path
                    context['preview_rows'] = rows[:20]
                    context['total_rows'] = len(rows)
                    context['form'] = form
                    return render(request, 'inventory/admin_csv_import.html', context)
                except ValueError as e:
                    self.message_user(request, str(e), level=messages.ERROR)
        else:
            form = CSVImportForm()

        context['form'] = form
        return render(request, 'inventory/admin_csv_import.html', context)


# ---------------------------------------------------------------------------
# AuditEvent — read-only standalone admin
# ---------------------------------------------------------------------------

@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ['item', 'field_name', 'old_value', 'new_value', 'user', 'timestamp']
    list_filter = ['field_name', 'user']
    search_fields = ['item__name', 'old_value', 'new_value']
    readonly_fields = ['item', 'user', 'timestamp', 'field_name', 'old_value', 'new_value', 'note']
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
