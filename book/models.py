from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class Book(models.Model):
    STATUS_CHOICES = [
        ('tersedia', 'Tersedia'),
        ('rusak', 'Rusak'),
        ('hilang', 'Hilang'),
        ('tidak_aktif', 'Tidak Aktif'),
    ]

    # Data dari CSV / input manual
    title           = models.CharField(max_length=500)
    author          = models.CharField(max_length=500)
    isbn            = models.CharField(max_length=20, unique=True)
    pages           = models.PositiveIntegerField(null=True, blank=True)
    language        = models.CharField(max_length=100, blank=True, default='Indonesian')
    total_copies    = models.PositiveIntegerField(default=1)
    damaged_copies  = models.PositiveIntegerField(default=0)  # Track damaged copies
    lost_copies     = models.PositiveIntegerField(default=0)  # Track lost copies
    shelf_location  = models.CharField(max_length=100, blank=True)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='tersedia')

    # Data enriched dari API (bisa kosong, diisi saat user buka detail)
    cover_url       = models.URLField(max_length=1000, blank=True, null=True)
    publisher       = models.CharField(max_length=300, blank=True, null=True)
    publish_year    = models.CharField(max_length=100, blank=True, null=True)
    category        = models.CharField(max_length=300, blank=True, null=True)
    synopsis        = models.TextField(blank=True, null=True)

    # Metadata
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    updated_by      = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='books_updated'
    )

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} ({self.isbn})"

    @property
    def available_copies(self):
        """Calculate available copies: total - borrowed - damaged - lost"""
        try:
            borrowed = self.loans.filter(status='sedang_dipinjam').count()
        except AttributeError:
            borrowed = 0
        good_copies = self.total_copies - self.damaged_copies - self.lost_copies
        available = good_copies - borrowed
        return max(available, 0)

    @property
    def borrowed_copies(self):
        """Count copies currently borrowed (sedang_dipinjam status)"""
        try:
            return self.loans.filter(status='sedang_dipinjam').count()
        except AttributeError:
            return 0

    @property
    def display_status(self):
        """Calculate display status based on counter values"""
        if self.status == 'tidak_aktif':
            return 'tidak_aktif'
        if self.total_copies == 0:
            return 'tidak_tersedia'
        if self.damaged_copies == self.total_copies:
            return 'rusak'
        if self.lost_copies == self.total_copies:
            return 'hilang'
        if self.available_copies > 0:
            return 'tersedia'
        return 'tidak_tersedia'

    @property
    def is_available(self):
        return self.status == 'tersedia' and self.available_copies > 0

    def distribute_waiting_list(self):
        """
        Distribute book to waiting list members when book becomes available.
        Based on PBI backlog requirements.
        """
        from django.utils import timezone
        from datetime import timedelta
        from book_loan.models import WaitingList, Notification
        
        try:
            # Get first person in waiting list (not already marked as ready/cancelled)
            waiting = self.waiting_lists.filter(
                status='menunggu'
            ).order_by('position').first()
            
            if waiting:
                # Mark as ready to claim
                waiting.mark_ready()
                
                # Create notification for the user
                Notification.objects.create(
                    user=waiting.user,
                    notification_type='waitlist_ready',
                    title='Buku Siap Dipinjam',
                    message=f'Buku "{self.title}" yang Anda tunggu sekarang tersedia. Silakan ambil dalam 24 jam.',
                    book=self
                )
        except Exception as e:
            print(f"Error distributing waiting list for book {self.id}: {str(e)}")


class Review(models.Model):
    book       = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    rating     = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('book', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"Review {self.user} → {self.book.title}"