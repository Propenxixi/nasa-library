from django import forms
from .models import Book, Review


class BookForm(forms.ModelForm):
    class Meta:
        model  = Book
        fields = [
            'title', 'author', 'isbn', 'pages', 'language',
            'total_copies', 'shelf_location', 'status',
            'cover_url', 'publisher', 'publish_year', 'category', 'synopsis',
        ]
        widgets = {
            'title':          forms.TextInput(attrs={'placeholder': 'Judul buku'}),
            'author':         forms.TextInput(attrs={'placeholder': 'Nama pengarang'}),
            'isbn':           forms.TextInput(attrs={'placeholder': '13-digit ISBN'}),
            'pages':          forms.NumberInput(attrs={'placeholder': 'Jumlah halaman'}),
            'language':       forms.TextInput(attrs={'placeholder': 'Indonesian'}),
            'total_copies':   forms.NumberInput(attrs={'min': 1}),
            'shelf_location': forms.TextInput(attrs={'placeholder': 'Contoh: Rak A-3'}),
            'cover_url':      forms.URLInput(attrs={'placeholder': 'https://...'}),
            'publisher':      forms.TextInput(attrs={'placeholder': 'Nama penerbit'}),
            'publish_year':   forms.TextInput(attrs={'placeholder': 'Contoh: 2021'}),
            'category':       forms.TextInput(attrs={'placeholder': 'Novel, Fiksi, ...'}),
            'synopsis':       forms.Textarea(attrs={'rows': 5, 'placeholder': 'Sinopsis buku...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Saat tambah buku baru (belum punya pk), status tidak ditampilkan
        # di form → jangan require, default ke 'tersedia'
        if not self.instance.pk:
            self.fields['status'].required = False
            self.fields['status'].initial  = 'tersedia'

    def clean_status(self):
        status = self.cleaned_data.get('status')
        if not status:
            return 'tersedia'  # default untuk buku baru
        return status

    def clean_isbn(self):
        isbn = self.cleaned_data['isbn'].strip()
        qs   = Book.objects.filter(isbn=isbn)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('ISBN ini sudah terdaftar di sistem.')
        return isbn


class ReviewForm(forms.ModelForm):
    class Meta:
        model  = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating':  forms.Select(choices=[(i, f'{i} ⭐') for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tulis ulasan...'}),
        }