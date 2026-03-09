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
        try:
            borrowed = self.loan_set.filter(status='dipinjam').count()
        except AttributeError:
            borrowed = 0
        return max(self.total_copies - borrowed, 0)

    @property
    def is_available(self):
        return self.status == 'tersedia' and self.available_copies > 0


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