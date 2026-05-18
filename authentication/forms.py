from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from .models import UserProfile


class LoginForm(forms.Form):
    """Custom login form using NIS as username"""
    
    nis = forms.CharField(
        label='NIS (Nomor Induk Siswa)',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan NIS Anda',
            'autocomplete': 'username',
        })
    )
    
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan Password Anda',
            'autocomplete': 'current-password',
        })
    )


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with better styling"""
    
    old_password = forms.CharField(
        label='Password Saat Ini',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan password lama Anda',
            'autocomplete': 'current-password',
        })
    )
    
    new_password1 = forms.CharField(
        label='Password Baru',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan password baru',
            'autocomplete': 'new-password',
        })
    )
    
    new_password2 = forms.CharField(
        label='Konfirmasi Password Baru',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Konfirmasi password baru',
            'autocomplete': 'new-password',
        })
    )


class ChangeUsernameForm(forms.Form):
    """Form to change username"""
    
    new_username = forms.CharField(
        label='Username Baru',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan username baru',
        })
    )
    
    password = forms.CharField(
        label='Password (untuk konfirmasi)',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan password Anda',
            'autocomplete': 'current-password',
        })
    )
    
    def clean_new_username(self):
        new_username = self.cleaned_data.get('new_username')
        if User.objects.filter(username=new_username).exists():
            raise ValidationError('Username ini sudah digunakan. Silahkan pilih username lain.')
        return new_username


class StudentBatchImportForm(forms.Form):
    """Form for batch importing students from Excel file"""

    excel_file = forms.FileField(
        label='File Excel (Daftar Siswa)',
        help_text='Format: .xlsx | Kolom wajib: NIS, Nama, Jenis Kelamin, Kelas',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls',
            'class': 'hidden',
            'id': 'file-input',
        })
    )

    update_existing = forms.BooleanField(
        label='Update data siswa yang sudah ada',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-gray-800 cursor-pointer',
        })
    )

    def clean_excel_file(self):
        file = self.cleaned_data.get('excel_file')
        if file:
            # Validate file extension
            if not file.name.lower().endswith(('.xlsx', '.xls')):
                raise ValidationError('File harus berformat .xlsx atau .xls')

            # Validate file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError('Ukuran file tidak boleh lebih dari 10MB')

        return file


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile including password, username, and profile picture"""

    # Password change fields
    old_password = forms.CharField(
        label='Password Saat Ini',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan password lama Anda',
            'autocomplete': 'current-password',
        }),
        required=False
    )

    new_password1 = forms.CharField(
        label='Password Baru',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan password baru',
            'autocomplete': 'new-password',
        }),
        required=False
    )

    new_password2 = forms.CharField(
        label='Konfirmasi Password Baru',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Konfirmasi password baru',
            'autocomplete': 'new-password',
        }),
        required=False
    )

    # Username change field
    new_username = forms.CharField(
        label='Username Baru',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-900 transition-all',
            'placeholder': 'Masukkan username baru',
        }),
        required=False
    )

    class Meta:
        model = UserProfile
        fields = ['profile_picture']
        widgets = {
            'profile_picture': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'hidden',
                'id': 'profile-picture-input',
            })
        }

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        old_password = cleaned_data.get('old_password', '').strip()
        new_password1 = cleaned_data.get('new_password1', '').strip()
        new_password2 = cleaned_data.get('new_password2', '').strip()
        new_username = cleaned_data.get('new_username', '').strip()
        profile_picture = cleaned_data.get('profile_picture')

        # Validate profile picture
        if profile_picture:
            # Check file size (max 5MB)
            if profile_picture.size > 5 * 1024 * 1024:
                raise ValidationError('Ukuran file foto profil tidak boleh lebih dari 5MB.')

            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if profile_picture.content_type not in allowed_types:
                raise ValidationError('Format file foto profil harus JPEG, PNG, GIF, atau WebP.')

        # Validate password change
        if new_password1 or new_password2 or old_password:
            if not old_password:
                raise ValidationError('Password saat ini diperlukan untuk mengubah password.')
            if not self.user.check_password(old_password):
                raise ValidationError('Password saat ini salah.')
            if not new_password1:
                raise ValidationError('Password baru kosong. Masukkan password baru.')
            if not new_password2:
                raise ValidationError('Konfirmasi password baru kosong. Masukkan konfirmasi password baru.')
            if new_password1 != new_password2:
                raise ValidationError('Konfirmasi password baru tidak sesuai.')

        # Validate username change
        if new_username:
            if not old_password:
                raise ValidationError('Password saat ini diperlukan untuk mengubah username.')
            if not self.user.check_password(old_password):
                raise ValidationError('Password saat ini salah.')
            if User.objects.filter(username=new_username).exclude(pk=self.user.pk).exists():
                raise ValidationError('Username ini sudah digunakan.')

        return cleaned_data

    def has_changes(self):
        """Check if there are any actual changes to be saved"""
        cleaned_data = self.cleaned_data
        new_username = cleaned_data.get('new_username', '').strip()
        new_password1 = cleaned_data.get('new_password1', '').strip()
        profile_picture = cleaned_data.get('profile_picture')
        
        # Check if username will change
        if new_username and new_username != self.user.username:
            return True
        
        # Check if password will change
        if new_password1:
            return True
        
        # Check if profile picture will change
        if profile_picture:
            return True
        
        return False

    def save(self, commit=True):
        profile = super().save(commit=False)

        # Update password if provided
        new_password = self.cleaned_data.get('new_password1', '').strip()
        if new_password:
            self.user.set_password(new_password)
            self.user.save()

        # Update username if provided
        new_username = self.cleaned_data.get('new_username', '').strip()
        if new_username and new_username != self.user.username:
            self.user.username = new_username
            self.user.save()

        if commit:
            profile.save()

        return profile
