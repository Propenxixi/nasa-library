from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta


class BookReview(models.Model):
    """Student's book review submission"""
    
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='book_reviews')
    
    # Book Information
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    publisher = models.CharField(max_length=255)
    year_published = models.IntegerField(help_text="Year the book was published")
    summary = models.TextField(help_text="Book summary and review")
    
    # Verification
    status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='pending')
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='verified_reviews'
    )
    rejection_reason = models.TextField(blank=True, help_text="Reason for rejection")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
        verbose_name = "Book Review"
        verbose_name_plural = "Book Reviews"
    
    def __str__(self):
        return f"{self.title} - {self.student.get_full_name()}"
    
    def verify(self, teacher):
        """Mark review as verified"""
        self.status = 'verified'
        self.verified_by = teacher
        self.verified_at = timezone.now()
        self.save()
    
    def reject(self, teacher, reason):
        """Reject review with reason"""
        self.status = 'rejected'
        self.verified_by = teacher
        self.rejection_reason = reason
        self.verified_at = timezone.now()
        self.save()


class LiteracyPost(models.Model):
    """Forum post for sharing literacy results"""
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='literacy_posts')
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Related book review (optional)
    book_review = models.ForeignKey(
        BookReview, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='posts'
    )
    
    # Engagement
    likes = models.ManyToManyField(User, blank=True, related_name='liked_posts')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'created_at']),
        ]
        verbose_name = "Literacy Post"
        verbose_name_plural = "Literacy Posts"
    
    def __str__(self):
        return f"{self.title} - {self.student.get_full_name()}"
    
    def get_like_count(self):
        return self.likes.count()


class LiteracyComment(models.Model):
    """Comments on literacy posts"""
    
    post = models.ForeignKey(LiteracyPost, on_delete=models.CASCADE, related_name='comments')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='literacy_comments')
    content = models.TextField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = "Literacy Comment"
        verbose_name_plural = "Literacy Comments"
    
    def __str__(self):
        return f"Comment by {self.student.get_full_name()} on {self.post.title}"


class LiteracyLeaderboard(models.Model):
    """Cache model for leaderboard scores"""
    
    SCOPE_CHOICES = [
        ('class', 'By Class'),
        ('grade', 'By Grade'),
        ('school', 'School-wide'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaderboard_entries')
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    scope_value = models.CharField(max_length=100, help_text="Class name, grade, or 'school'")
    
    # Score components
    books_read = models.IntegerField(default=0)
    consistency_score = models.IntegerField(default=0, help_text="Based on consistent submissions")
    verified_reviews = models.IntegerField(default=0)
    total_score = models.IntegerField(default=0)
    
    # Ranking
    rank = models.IntegerField(default=0)
    is_monthly_ambassador = models.BooleanField(default=False)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-total_score', 'rank']
        unique_together = ['student', 'scope', 'scope_value']
        indexes = [
            models.Index(fields=['scope', 'scope_value', '-total_score']),
        ]
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.scope_value} (Score: {self.total_score})"


class LiteracyAchievement(models.Model):
    """Track literacy achievements and badges"""
    
    ACHIEVEMENT_TYPES = [
        ('first_review', 'First Review'),
        ('five_books', '5 Books Read'),
        ('ten_books', '10 Books Read'),
        ('consistent_reader', 'Consistent Reader'),
        ('ambassador', 'Literacy Ambassador'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='literacy_achievements')
    achievement_type = models.CharField(max_length=50, choices=ACHIEVEMENT_TYPES)
    earned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-earned_at']
        unique_together = ['student', 'achievement_type']
        verbose_name = "Literacy Achievement"
        verbose_name_plural = "Literacy Achievements"
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.get_achievement_type_display()}"
