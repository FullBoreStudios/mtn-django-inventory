import base64
import io

import qrcode
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from .models import Item, LabelFormat


def _qr_data_url(content):
    img = qrcode.make(content)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return f'data:image/png;base64,{b64}'


@staff_member_required
def label_print(request, pk):
    item = get_object_or_404(Item, pk=pk)
    fmt_pk = request.GET.get('format')
    label = (
        LabelFormat.objects.filter(pk=fmt_pk).first()
        if fmt_pk
        else LabelFormat.get_default()
    )
    return render(request, 'inventory/label_print.html', {
        'items_data': [{'item': item, 'qr_url': _qr_data_url(item.qr_content())}],
        'label': label,
        'bulk': False,
    })


@staff_member_required
def label_print_bulk(request):
    raw_ids = request.GET.get('ids', '')
    pks = [p.strip() for p in raw_ids.split(',') if p.strip().isdigit()]
    items = Item.objects.filter(pk__in=pks).select_related('category', 'location')
    fmt_pk = request.GET.get('format')
    label = (
        LabelFormat.objects.filter(pk=fmt_pk).first()
        if fmt_pk
        else LabelFormat.get_default()
    )
    items_data = [
        {'item': item, 'qr_url': _qr_data_url(item.qr_content())}
        for item in items
    ]
    return render(request, 'inventory/label_print.html', {
        'items_data': items_data,
        'label': label,
        'bulk': True,
    })
