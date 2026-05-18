# Generated migration to add missing verification fields
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('literacy', '0007_add_verification_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='literacypost',
            name='verified_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='verified_posts',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='literacypost',
            name='rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='literacypost',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
