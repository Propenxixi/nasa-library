from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class AttendanceActivity(models.Model):
    """Pre-defined activities that students can select during check-in"""
    
    name = models.CharField(max_length=100, unique=True)
    emoji = models.CharField(max_length=10, default='📖', help_text="Emoji representation")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0, help_text="Display order")
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = "Attendance Activities"
    
    def __str__(self):
        return f"{self.emoji} {self.name}"


class Attendance(models.Model):
    """Track library attendance with check-in and check-out times"""
    
    STATUS_CHOICES = [
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('auto_checked_out', 'Auto Checked Out'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='checked_in')
    
    # Activity selection
    activities = models.ManyToManyField(AttendanceActivity, blank=True, related_name='attendance_records')
    custom_activity = models.TextField(blank=True, help_text="Custom activity if not in predefined list")
    
    # Duration calculation
    duration_minutes = models.IntegerField(null=True, blank=True, help_text="Visit duration in minutes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-check_in_time']
        indexes = [
            models.Index(fields=['user', 'check_in_time']),
            models.Index(fields=['status', 'check_in_time']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.check_in_time.date()}"
    
    def save(self, *args, **kwargs):
        """Calculate duration when checking out"""
        if self.check_out_time and self.check_in_time:
            delta = self.check_out_time - self.check_in_time
            self.duration_minutes = int(delta.total_seconds() / 60)
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if attendance record is currently active (checked in but not checked out)"""
        return self.status == 'checked_in'
    
    @property
    def duration_display(self):
        """Return formatted duration display"""
        if not self.duration_minutes:
            return "—"
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
