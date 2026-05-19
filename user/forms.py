from django import forms
from django.contrib.auth.models import User
from authentication.models import UserProfile


class UserCreateForm(forms.Form):
    first_name = forms.CharField(label="First Name", widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}))
    last_name  = forms.CharField(label="Last Name", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    username   = forms.CharField(label="Username / Student ID", widget=forms.TextInput(attrs={"class": "form-control"}))
    password   = forms.CharField(label="Password", required=False, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Leave blank to use username"}))
    email      = forms.EmailField(label="Email", required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    role       = forms.ChoiceField(label="Role", choices=UserProfile.ROLE_CHOICES, widget=forms.Select(attrs={"class": "form-select"}))
    nis        = forms.CharField(label="Student ID (NIS)", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    gender     = forms.ChoiceField(label="Gender", required=False, choices=[("", "-"), ("L", "Male"), ("P", "Female")], widget=forms.Select(attrs={"class": "form-select"}))
    kelas      = forms.CharField(label="Class", required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. XII IPA 1"}))
    profile_picture = forms.ImageField(label="Profile Picture", required=False, widget=forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}))

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already taken.")
        return username

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            # Check file size (max 5MB)
            if picture.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Ukuran file foto profil tidak boleh lebih dari 5MB.')

            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(picture, 'content_type') and picture.content_type not in allowed_types:
                raise forms.ValidationError('Format file foto profil harus JPEG, PNG, GIF, atau WebP.')

        return picture

    def save(self, created_by=None):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["username"],
            password=data.get("password") or data["username"],
            first_name=data["first_name"],
            last_name=data.get("last_name", ""),
            email=data.get("email", ""),
        )
        UserProfile.objects.create(
            user=user,
            role=data["role"],
            nis=data.get("nis") or None,
            gender=data.get("gender") or None,
            kelas=data.get("kelas") or None,
            profile_picture=data.get("profile_picture") or None,
        )
        return user


class UserUpdateForm(forms.Form):
    first_name = forms.CharField(label="First Name", widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name  = forms.CharField(label="Last Name", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    username   = forms.CharField(label="Username / Student ID", widget=forms.TextInput(attrs={"class": "form-control"}))
    email      = forms.EmailField(label="Email", required=False, widget=forms.EmailInput(attrs={"class": "form-control"}))
    role       = forms.ChoiceField(label="Role", choices=UserProfile.ROLE_CHOICES, widget=forms.Select(attrs={"class": "form-select"}))
    nis        = forms.CharField(label="Student ID (NIS)", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    gender     = forms.ChoiceField(label="Gender", required=False, choices=[("", "-"), ("L", "Male"), ("P", "Female")], widget=forms.Select(attrs={"class": "form-select"}))
    kelas      = forms.CharField(label="Class", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    remove_profile_picture = forms.BooleanField(label="Remove current profile picture", required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def __init__(self, *args, user_instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user_instance:
            self.fields["first_name"].initial = user_instance.first_name
            self.fields["last_name"].initial  = user_instance.last_name
            self.fields["username"].initial   = user_instance.username
            self.fields["email"].initial      = user_instance.email
            if hasattr(user_instance, "profile"):
                p = user_instance.profile
                self.fields["role"].initial   = p.role
                self.fields["nis"].initial    = p.nis
                self.fields["gender"].initial = p.gender
                self.fields["kelas"].initial  = p.kelas
                # Note: profile_picture field doesn't need initial value as it's a file upload

    def save(self, user_instance):
        data = self.cleaned_data
        user_instance.first_name = data["first_name"]
        user_instance.last_name  = data.get("last_name", "")
        user_instance.username   = data["username"]
        user_instance.email      = data.get("email", "")
        user_instance.save()

        profile, _ = UserProfile.objects.get_or_create(user=user_instance)

        # Handle profile picture removal only
        if data.get("remove_profile_picture"):
            if profile.profile_picture:
                try:
                    # Try to delete the file from storage
                    profile.profile_picture.delete(save=False)
                except (TypeError, AttributeError):
                    # If deletion fails (e.g., MEDIA_ROOT is None for Cloudinary), just clear the field
                    pass
            profile.profile_picture = None

        profile.role   = data["role"]
        profile.nis    = data.get("nis") or None
        profile.gender = data.get("gender") or None
        profile.kelas  = data.get("kelas") or None
        profile.save()
        return user_instance