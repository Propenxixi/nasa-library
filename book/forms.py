from django import forms
from .models import Book, Review


class BookForm(forms.ModelForm):
    class Meta:
        model  = Book
        fields = [
            'title', 'author', 'isbn', 'pages', 'language',
            'total_copies', 'damaged_copies', 'lost_copies', 'shelf_location',
            'cover_url', 'publisher', 'publish_year', 'category', 'synopsis',
        ]
        widgets = {
            'title':          forms.TextInput(attrs={'placeholder': 'Judul buku'}),
            'author':         forms.TextInput(attrs={'placeholder': 'Nama pengarang'}),
            'isbn':           forms.TextInput(attrs={'placeholder': '13-digit ISBN'}),
            'pages':          forms.NumberInput(attrs={'placeholder': 'Jumlah halaman'}),
            'language':       forms.TextInput(attrs={'placeholder': 'Indonesian'}),
            'total_copies':   forms.NumberInput(attrs={'min': 0}),
            'damaged_copies': forms.NumberInput(attrs={'min': 0}),
            'lost_copies':    forms.NumberInput(attrs={'min': 0}),
            'shelf_location': forms.TextInput(attrs={'placeholder': 'Contoh: Rak A-3'}),
            'cover_url':      forms.URLInput(attrs={'placeholder': 'https://...'}),
            'publisher':      forms.TextInput(attrs={'placeholder': 'Nama penerbit'}),
            'publish_year':   forms.TextInput(attrs={'placeholder': 'Contoh: 2021'}),
            'category':       forms.TextInput(attrs={'placeholder': 'Novel, Fiksi, ...'}),
            'synopsis':       forms.Textarea(attrs={'rows': 5, 'placeholder': 'Sinopsis buku...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set damaged and lost copies as optional (defaults to 0 in model)
        self.fields['damaged_copies'].required = False
        self.fields['lost_copies'].required = False
        # Set initial status for new books
        if not self.instance.pk:
            self.instance.status = 'tersedia'

    def clean_isbn(self):
        isbn_raw = self.cleaned_data.get('isbn')
        if not isbn_raw or isbn_raw.strip() == '0':
            return None
        
        isbn = isbn_raw.strip()
        qs = Book.objects.filter(isbn=isbn)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        existing = qs.first()
        if existing:
            if existing.status == 'tidak_aktif':
                raise forms.ValidationError('Buku ini sudah ada di sistem tapi berstatus tidak aktif. Silakan aktifkan kembali buku tersebut melalui daftar katalog.')
            raise forms.ValidationError('ISBN ini sudah terdaftar di sistem.')
        return isbn


class ReviewForm(forms.ModelForm):
    class Meta:
        model  = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating':  forms.Select(choices=[(i, f'{i} ⭐') for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tulis ulasan...', 'maxlength': '500'}),
        }