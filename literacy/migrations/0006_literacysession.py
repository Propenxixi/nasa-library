# Generated migration for LiteracySession model
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('literacy', '0005_alter_literacyleaderboard_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LiteracySession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Contoh: Forum Literasi #1', max_length=200)),
                ('topic', models.CharField(choices=[('kepemimpinan_motivasi', 'Kepemimpinan & Motivasi'), ('sains_teknologi', 'Sains & Teknologi'), ('sejarah_kebudayaan', 'Sejarah & Kebudayaan'), ('fiksi_sastra', 'Fiksi & Sastra'), ('kesehatan_gaya_hidup', 'Kesehatan & Gaya Hidup'), ('ekonomi_bisnis', 'Ekonomi & Bisnis'), ('lainnya', 'Lainnya')], default='lainnya', max_length=50)),
                ('date', models.DateField(help_text='Tanggal pelaksanaan sesi')),
                ('is_open', models.BooleanField(default=True, help_text='Jika True, siswa masih bisa submit posting ke sesi ini.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Literacy Session',
                'verbose_name_plural': 'Literacy Sessions',
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.AddField(
            model_name='literacypost',
            name='session',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='posts', to='literacy.literacysession'),
        ),
    ]
