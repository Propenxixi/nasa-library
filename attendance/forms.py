from django import forms
from .models import Attendance, AttendanceActivity


class CheckInForm(forms.ModelForm):
    """Form for students to check-in to the library"""
    
    activities = forms.ModelMultipleChoiceField(
        queryset=AttendanceActivity.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="What will you do at the library today?"
    )
    
    custom_activity = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Add any other activities not listed above... (optional)',
            'rows': 3,
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-gray-900 resize-none'
        }),
        label="Other Activities"
    )
    
    class Meta:
        model = Attendance
        fields = ['activities', 'custom_activity']


class CheckOutForm(forms.Form):
    """Simple form for students to check-out"""
    
    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4'
        }),
        label="I confirm my check-out"
    )
