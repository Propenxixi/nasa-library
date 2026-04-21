from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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
    
    # Soft delete for graduated students
    is_active_student = models.BooleanField(
        default=True, 
        help_text="Status aktif siswa. False jika sudah lulus atau tidak aktif."
    )
    deactivated_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Waktu siswa dinonaktifkan (soft delete)"
    )
    deactivation_reason = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ('graduated', 'Lulus Sekolah'),
            ('transferred', 'Pindah Sekolah'),
            ('other', 'Lainnya'),
        ],
        help_text="Alasan deactivasi"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
        ordering = ['-created_at']
    
    def __str__(self):
        status = "(Aktif)" if self.is_active_student else "(Nonaktif)"
        return f"{self.user.first_name} {self.user.last_name} ({self.get_role_display()}) {status}"
    
    def is_student(self):
        return self.role == 'student'
    
    def is_teacher(self):
        return self.role == 'teacher'
    
    def is_librarian(self):
        return self.role == 'librarian'
    
    def deactivate(self, reason='graduated'):
        """Soft delete: deactivate student"""
        self.is_active_student = False
        self.deactivated_at = timezone.now()
        self.deactivation_reason = reason
        self.user.is_active = False
        self.user.save()
        self.save()
    
    def activate(self):
        """Re-activate student"""
        self.is_active_student = True
        self.deactivated_at = None
        self.deactivation_reason = None
        self.user.is_active = True
        self.user.save()
        self.save()
