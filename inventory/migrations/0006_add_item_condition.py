from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0005_add_itemmodel_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='condition',
            field=models.CharField(choices=[('new', 'New'), ('used', 'Used')], default='new', max_length=10),
        ),
    ]
