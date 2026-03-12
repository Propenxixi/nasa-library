from django import forms


class LoanFilterForm(forms.Form):
    """Form sederhana untuk filter peminjaman buku"""
    
    search = forms.CharField(
        required=False,
        label='Cari',
        widget=forms.TextInput(attrs={
            'placeholder': 'Cari nama, email, atau buku...',
        })
    )
    
    tanggal_pinjam = forms.DateField(
        required=False,
        label='Tanggal Pinjam',
        widget=forms.DateInput(attrs={
            'type': 'date',
        })
    )
    
    jatuh_tempo = forms.DateField(
        required=False,
        label='Jatuh Tempo',
        widget=forms.DateInput(attrs={
            'type': 'date',
        })
    )
    
    sisa_hari = forms.IntegerField(
        required=False,
        label='Sisa Hari (<=)',
        widget=forms.NumberInput(attrs={
            'placeholder': 'Contoh: 7',
        })
    )
