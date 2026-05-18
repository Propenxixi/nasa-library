# Generated migration to add missing verification_status field
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('literacy', '0006_literacysession'),
    ]

    operations = [
        migrations.AddField(
            model_name='literacypost',
            name='verification_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected')],
                default='pending',
                max_length=20,
            ),
        ),
    ]
