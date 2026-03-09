from django.db import models
from django.contrib.auth.models import User


class BookRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Waiting Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    requester = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='book_requests'
    )
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=300)
    category = models.CharField(max_length=200, blank=True)
    reason = models.TextField(help_text="Reason for requesting this book")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_book_requests'
    )
    rejection_reason = models.TextField(blank=True)

    # Track whether the user has been notified of the status change
    # so we show the pop-up only once
    notification_seen = models.BooleanField(
        default=False,
        help_text="True once the requester has dismissed the status pop-up"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Book Request"
        verbose_name_plural = "Book Requests"

    def __str__(self):
        return f"{self.title} – {self.requester.get_full_name()} ({self.get_status_display()})"