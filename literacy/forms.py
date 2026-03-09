from django import forms
from .models import BookReview, LiteracyPost, LiteracyComment


class BookReviewForm(forms.ModelForm):
    """Form for students to submit book reviews"""
    
    year_published = forms.IntegerField(
        min_value=1900,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600',
            'placeholder': 'e.g., 2024'
        })
    )
    
    class Meta:
        model = BookReview
        fields = ['title', 'author', 'publisher', 'year_published', 'summary']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600',
                'placeholder': 'Enter book title',
                'maxlength': '255'
            }),
            'author': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600',
                'placeholder': 'Enter author name',
                'maxlength': '255'
            }),
            'publisher': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600',
                'placeholder': 'Enter publisher',
                'maxlength': '255'
            }),
            'summary': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 resize-none',
                'placeholder': 'Write your book summary and review here...',
                'rows': 8
            }),
        }
        labels = {
            'title': 'Book Title',
            'author': 'Author Name',
            'publisher': 'Publisher',
            'year_published': 'Year Published',
            'summary': 'Summary & Review',
        }
        help_texts = {
            'summary': 'Share your thoughts about the book, key takeaways, and why you enjoyed it.',
        }


class LiteracyPostForm(forms.ModelForm):
    """Form for students to create forum posts"""
    
    class Meta:
        model = LiteracyPost
        fields = ['title', 'content', 'book_review']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600',
                'placeholder': 'What do you want to share?',
                'maxlength': '200'
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 resize-none',
                'placeholder': 'Share your literacy journey, insights, or recommendations...',
                'rows': 6
            }),
            'book_review': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600'
            }),
        }
        labels = {
            'title': 'Post Title',
            'content': 'Share Your Thoughts',
            'book_review': 'Related Book Review (Optional)',
        }


class CommentForm(forms.ModelForm):
    """Form for students to comment on posts"""
    
    class Meta:
        model = LiteracyComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 resize-none',
                'placeholder': 'Add your comment...',
                'rows': 3
            }),
        }
        labels = {
            'content': '',
        }


class ReviewVerificationForm(forms.Form):
    """Form for teachers to verify or reject reviews"""
    
    action = forms.ChoiceField(
        choices=[
            ('verify', 'Approve Review'),
            ('reject', 'Reject Review'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'w-4 h-4'
        })
    )
    
    rejection_reason = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-red-600 focus:ring-1 focus:ring-red-600 resize-none',
            'placeholder': 'Please provide a reason for rejection...',
            'rows': 4
        }),
        label='Reason for Rejection (if applicable)'
    )
