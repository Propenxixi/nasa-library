# Generated migration for updating WaitingList model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book_loan', '0002_alter_loan_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='waitinglist',
            name='status',
            field=models.CharField(
                choices=[
                    ('menunggu', 'Menunggu'),
                    ('siap_dipinjam', 'Siap Dipinjam'),
                    ('menunggu_konfirmasi_dari_admin', 'Menunggu Konfirmasi dari Admin'),
                    ('siap_diambil_di_perpustakaan', 'Siap Diambil di Perpustakaan'),
                    ('dibatalkan', 'Dibatalkan'),
                ],
                default='menunggu',
                max_length=30
            ),
        ),
        migrations.AddField(
            model_name='waitinglist',
            name='claimed_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='waitinglist',
            name='approved_by_admin_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
