import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Avg

from .models import Book, Review
from .forms import BookForm, ReviewForm
from .services import enrich_book_from_isbn


def _is_staff_or_librarian(user):
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=['Petugas', 'Librarian', 'Admin']).exists()


# ─── Dashboard / Home ─────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    genres = (
        Book.objects
        .exclude(category__isnull=True).exclude(category='')
        .values_list('category', flat=True).distinct()
    )
    genre_set = set()
    for cat in genres:
        for g in cat.split(','):
            g = g.strip()
            if g:
                genre_set.add(g)

    genre_books = {}
    for genre in sorted(genre_set)[:8]:
        books = Book.objects.filter(category__icontains=genre, status='tersedia')[:6]
        if books:
            genre_books[genre] = books

    recent_books = Book.objects.filter(status='tersedia').order_by('-created_at')[:8]

    context = {
        'genre_books':  genre_books,
        'recent_books': recent_books,
        'can_manage':   _is_staff_or_librarian(request.user),
    }
    return render(request, 'dashboard.html', context)


# ─── Catalog (List) ───────────────────────────────────────────────────────────

@login_required
def book_list(request):
    q        = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    status   = request.GET.get('status', '').strip()

    books = Book.objects.all()
    if q:
        books = books.filter(Q(title__icontains=q) | Q(author__icontains=q) | Q(isbn__icontains=q))
    if category:
        books = books.filter(category__icontains=category)
    if status:
        books = books.filter(status=status)

    paginator = Paginator(books, 12)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    all_cats = set()
    for cat in Book.objects.exclude(category__isnull=True).exclude(category='').values_list('category', flat=True):
        for c in cat.split(','):
            c = c.strip()
            if c:
                all_cats.add(c)

    context = {
        'page_obj':       page_obj,
        'q':              q,
        'category':       category,
        'status':         status,
        'all_cats':       sorted(all_cats),
        'status_choices': Book.STATUS_CHOICES,
        'total_count':    books.count(),
        'can_manage':     _is_staff_or_librarian(request.user),
    }
    return render(request, 'book_list.html', context)


# ─── Book Detail ──────────────────────────────────────────────────────────────

@login_required
def book_detail(request, pk):
    book       = get_object_or_404(Book, pk=pk)
    reviews    = book.reviews.select_related('user').all()
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
    user_review = reviews.filter(user=request.user).first()
    review_form = ReviewForm(instance=user_review)

    if request.method == 'POST' and 'review_submit' in request.POST:
        review_form = ReviewForm(request.POST, instance=user_review)
        if review_form.is_valid():
            r      = review_form.save(commit=False)
            r.book = book
            r.user = request.user
            r.save()
            messages.success(request, 'Ulasan berhasil disimpan.')
            return redirect('book:book_detail', pk=pk)

    context = {
        'book':        book,
        'reviews':     reviews,
        'avg_rating':  round(avg_rating, 1) if avg_rating else None,
        'review_form': review_form,
        'user_review': user_review,
        'can_manage':  _is_staff_or_librarian(request.user),
    }
    return render(request, 'book_detail.html', context)


# ─── Add Book ─────────────────────────────────────────────────────────────────

@login_required
def book_add(request):
    if not _is_staff_or_librarian(request.user):
        messages.error(request, 'Anda tidak memiliki izin untuk menambah buku.')
        return redirect('book:book_list')

    form = BookForm()

    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            book            = form.save(commit=False)
            book.updated_by = request.user

            # Auto-enrich field yang masih kosong
            if book.isbn and not all([book.cover_url, book.publisher, book.synopsis]):
                enriched = enrich_book_from_isbn(book.isbn)
                for field, value in enriched.items():
                    if value and not getattr(book, field):
                        setattr(book, field, value)

            book.save()
            messages.success(request, f'Buku "{book.title}" berhasil ditambahkan.')
            return redirect('book:book_detail', pk=book.pk)
        else:
            # Tampilkan semua error ke messages supaya kelihatan
            for field, errs in form.errors.items():
                for err in errs:
                    label = form.fields[field].label or field if field != '__all__' else ''
                    messages.error(request, f'{label}: {err}' if label else err)

    return render(request, 'book_form.html', {'form': form, 'action': 'add'})


# ─── Edit Book ────────────────────────────────────────────────────────────────

@login_required
def book_edit(request, pk):
    if not _is_staff_or_librarian(request.user):
        messages.error(request, 'Anda tidak memiliki izin untuk mengedit buku.')
        return redirect('book:book_detail', pk=pk)

    book = get_object_or_404(Book, pk=pk)
    form = BookForm(instance=book)

    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            b            = form.save(commit=False)
            b.updated_by = request.user
            b.save()
            messages.success(request, f'Buku "{b.title}" berhasil diperbarui.')
            return redirect('book:book_detail', pk=b.pk)
        else:
            for field, errs in form.errors.items():
                for err in errs:
                    label = form.fields[field].label or field if field != '__all__' else ''
                    messages.error(request, f'{label}: {err}' if label else err)

    return render(request, 'book_form.html', {'form': form, 'action': 'edit', 'book': book})


# ─── Delete (Soft) Book ───────────────────────────────────────────────────────

@login_required
@require_POST
def book_delete(request, pk):
    if not _is_staff_or_librarian(request.user):
        messages.error(request, 'Anda tidak memiliki izin untuk menonaktifkan buku.')
        return redirect('book:book_detail', pk=pk)

    book = get_object_or_404(Book, pk=pk)

    # Cek peminjaman aktif
    active_loans = getattr(book, 'loan_set', None)
    if active_loans and active_loans.filter(status='dipinjam').exists():
        messages.error(request, f'Buku "{book.title}" tidak dapat dinonaktifkan karena sedang dipinjam.')
        return redirect('book:book_detail', pk=pk)

    book.status     = 'tidak_aktif'
    book.updated_by = request.user
    book.save()
    messages.success(request, f'Buku "{book.title}" berhasil dinonaktifkan.')
    return redirect('book:book_list')


# ─── API: Enrich from ISBN ────────────────────────────────────────────────────

@login_required
@require_GET
def api_enrich_isbn(request):
    isbn = request.GET.get('isbn', '').strip()
    if not isbn:
        return JsonResponse({'error': 'ISBN diperlukan'}, status=400)
    data = enrich_book_from_isbn(isbn)
    return JsonResponse(data)


# ─── API: Search by Title (Perpusnas) ────────────────────────────────────────

@login_required
@require_GET
def api_search_title(request):
    title = request.GET.get('title', '').strip()
    if not title:
        return JsonResponse({'error': 'Title diperlukan'}, status=400)
    from .services import search_perpusnas_by_title
    results = search_perpusnas_by_title(title, limit=5)
    return JsonResponse({'results': results})


# ─── API: Book Detail JSON ────────────────────────────────────────────────────

@login_required
@require_GET
def api_book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk)

    if book.isbn and not book.cover_url:
        enriched = enrich_book_from_isbn(book.isbn)
        updated  = False
        for field, value in enriched.items():
            if value and not getattr(book, field):
                setattr(book, field, value)
                updated = True
        if updated:
            book.save(update_fields=list(enriched.keys()))

    return JsonResponse({
        'id':           book.pk,
        'title':        book.title,
        'author':       book.author,
        'isbn':         book.isbn,
        'pages':        book.pages,
        'language':     book.language,
        'status':       book.get_status_display(),
        'total_copies': book.total_copies,
        'available':    book.available_copies,
        'shelf':        book.shelf_location,
        'cover_url':    book.cover_url,
        'publisher':    book.publisher,
        'publish_year': book.publish_year,
        'category':     book.category,
        'synopsis':     book.synopsis,
    })

# ─── REST API ──────────────────────────────────────────

@csrf_exempt
@require_http_methods(["GET", "POST"])
def book_api_list_create(request):
    if request.method == "GET":
        q        = request.GET.get('search', '').strip()
        category = request.GET.get('kategori', '').strip()
        status   = request.GET.get('status', '').strip()
        page     = request.GET.get('page', 1)

        books = Book.objects.all()
        if q:
            books = books.filter(Q(title__icontains=q) | Q(author__icontains=q))
        if category:
            books = books.filter(category__icontains=category)
        if status:
            books = books.filter(status=status)

        paginator = Paginator(books, 10)  # 10 per page for API
        page_obj  = paginator.get_page(page)

        data = [{
            'id': b.id,
            'title': b.title,
            'author': b.author,
            'isbn': b.isbn,
            'pages': b.pages,
            'category': b.category,
            'status': b.status,
            'total_copies': b.total_copies,
        } for b in page_obj]

        return JsonResponse({
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'current_page': page_obj.number,
            'results': data
        })

    elif request.method == "POST":
        if not _is_staff_or_librarian(request.user):
            return JsonResponse({'error': 'Forbidden'}, status=403)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Map Stock to total_copies if provided in AC format
        if 'jumlah_stok' in body and 'total_copies' not in body:
            body['total_copies'] = body['jumlah_stok']

        form = BookForm(body)
        if form.is_valid():
            book = form.save(commit=False)
            book.updated_by = request.user
            book.save()
            return JsonResponse({
                'id': book.id,
                'message': 'Buku berhasil ditambahkan'
            }, status=201)
        else:
            return JsonResponse({'errors': form.errors}, status=400)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def book_api_detail(request, pk):
    if not _is_staff_or_librarian(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    book = get_object_or_404(Book, pk=pk)

    if request.method == "PUT":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        # Allow partial updates for PUT for flexibility
        form = BookForm(body, instance=book)
        if form.is_valid():
            b = form.save(commit=False)
            b.updated_by = request.user
            b.save()
            return JsonResponse({'message': 'Buku berhasil diperbarui'})
        else:
            return JsonResponse({'errors': form.errors}, status=400)

    elif request.method == "DELETE":
        active_loans = getattr(book, 'loan_set', None)
        if active_loans and active_loans.filter(status='dipinjam').exists():
            return JsonResponse({
                'error': 'Buku tidak dapat dihapus karena masih ada peminjaman aktif.'
            }, status=400)

        book.status = 'tidak_aktif'
        book.updated_by = request.user
        book.save()
        return JsonResponse({'message': 'Buku berhasil dinonaktifkan (soft delete)'})
