from django.db import models
from django.contrib.auth.models import User


class BookRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Menunggu'),
        ('approved', 'Disetujui'),
        ('rejected', 'Ditolak'),
    ]

    requester = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='book_requests'
    )
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=300)
    publisher = models.CharField(max_length=300, blank=True)
    category = models.CharField(max_length=200, blank=True)
    reason = models.TextField(help_text="Alasan pengajuan buku ini (maks. 500 karakter)")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_book_requests'
    )
    catatan_petugas = models.TextField(
        blank=True,
        help_text="Catatan petugas saat menyetujui atau menolak usulan"
    )

    notification_seen = models.BooleanField(
        default=False,
        help_text="True setelah pengaju menutup pop-up notifikasi status"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Usulan Buku"
        verbose_name_plural = "Usulan Buku"

    def __str__(self):
        return f"{self.title} – {self.requester.get_full_name()} ({self.get_status_display()})"