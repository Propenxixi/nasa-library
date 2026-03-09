from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class UserPreference(models.Model):
    """User reading interest preferences"""
    
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='reading_preference'
    )
    categories = models.JSONField(default=list, help_text="List of interest categories")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"
    
    def __str__(self):
        return f"{self.user.username}'s preferences: {self.categories}"
    
    def get_categories_list(self):
        """Return categories as a list"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Getting categories for user: {self.user.username}, categories: {self.categories}, type: {type(self.categories)}")
        if isinstance(self.categories, list):
            return self.categories
        return []


class Loan(models.Model):
    """Track book borrowing/peminjaman"""
    
    STATUS_CHOICES = [
        ('dipinjam', 'Dipinjam'),
        ('dikembalikan', 'Dikembalikan'),
        ('terlambat', 'Terlambat'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='recommendation_loans'
    )
    book = models.ForeignKey(
        'book.Book', 
        on_delete=models.CASCADE, 
        related_name='recommendation_loans'
    )
    borrowed_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='dipinjam'
    )
    
    class Meta:
        ordering = ['-borrowed_at']
        verbose_name = "Loan"
        verbose_name_plural = "Loans"
    
    def __str__(self):
        return f"{self.user.username} - {self.book.title}"
    
    @property
    def is_returned(self):
        return self.status in ['dikembalikan', 'terlambat']
