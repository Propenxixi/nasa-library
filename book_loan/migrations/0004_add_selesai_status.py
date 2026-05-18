# Generated migration for adding 'selesai' status to WaitingList

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('book_loan', '0003_update_waiting_list'),
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
                    ('selesai', 'Selesai Diklaim'),
                    ('dibatalkan', 'Dibatalkan'),
                ],
                default='menunggu',
                max_length=30
            ),
        ),
    ]
