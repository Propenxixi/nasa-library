from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended user profile with roles and student information"""
    
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('librarian', 'Librarian'),
    ]
    
    GENDER_CHOICES = [
        ('L', 'Laki-laki (Male)'),
        ('P', 'Perempuan (Female)'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    
    # Student-specific fields
    nis = models.CharField(max_length=20, unique=True, blank=True, null=True, help_text="Nomor Induk Siswa")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    kelas = models.CharField(max_length=50, blank=True, null=True, help_text="Kelas/Class")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.get_role_display()})"
    
    def is_student(self):
        return self.role == 'student'
    
    def is_teacher(self):
        return self.role == 'teacher'
    
    def is_librarian(self):
        return self.role == 'librarian'
