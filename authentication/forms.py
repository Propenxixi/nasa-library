from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError


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
