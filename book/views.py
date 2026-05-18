import json
import csv
import io
from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count, F, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Book, Review
from .forms import BookForm, ReviewForm
from .services import enrich_book_from_isbn


def _is_staff_or_librarian(user):
    if user.is_superuser or user.is_staff:
        return True
    if user.groups.filter(name__in=['Petugas', 'Librarian', 'Admin']).exists():
        return True
    # Also check UserProfile role
    return _is_librarian(user)


def _is_librarian(user):
    """Check if user is a librarian"""
    try:
        from authentication.models import UserProfile
        profile = UserProfile.objects.get(user=user)
        return profile.is_librarian()
    except:
        return False


# ─── Dashboard / Home ─────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    from book_loan.models import Loan
    from book_request.models import BookRequest

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

    category_summaries = []
    for genre in sorted(genre_set):
        count = Book.objects.filter(category__icontains=genre, status='tersedia').count()
        category_summaries.append({'name': genre, 'count': count})

    # Chunk into pages of 6 for the slider UI
    paginated_categories = [category_summaries[i:i + 6] for i in range(0, len(category_summaries), 6)]

    is_librarian = _is_staff_or_librarian(request.user)

    loan_requests = []
    book_requests = []
    if is_librarian:
        loan_requests = Loan.objects.filter(status='menunggu_konfirmasi').order_by('-created_at')[:3]
        book_requests = BookRequest.objects.filter(status='pending').order_by('-created_at')[:3]

    context = {
        'categories':   category_summaries,  # keep for fallback if needed
        'paginated_categories': paginated_categories,
        'can_manage':   is_librarian,
        'loan_requests': loan_requests,
        'book_requests': book_requests,
    }
    return render(request, 'dashboard.html', context)


# ─── Catalog (List) ───────────────────────────────────────────────────────────

@login_required
def book_list(request):
    q        = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    status   = request.GET.get('status', '').strip()

    books = Book.objects.annotate(
        borrowed_count=Coalesce(Count('loans', filter=Q(loans__status='sedang_dipinjam')), Value(0))
    ).order_by('title')

    if not _is_staff_or_librarian(request.user):
        books = books.exclude(status='tidak_aktif')

    if q:
        books = books.filter(Q(title__icontains=q) | Q(author__icontains=q) | Q(isbn__icontains=q))
    if category:
        books = books.filter(category__icontains=category)
    if status:
        if status == 'tersedia':
            # Available: status available AND good_copies > borrowed
            books = books.filter(
                status='tersedia',
                total_copies__gt=F('borrowed_count') + F('damaged_copies') + F('lost_copies')
            )
        elif status == 'tidak_tersedia':
            # Not Available: not inactive AND (total=0 OR total <= busy_copies)
            # BUT excluded from specific 'rusak' or 'hilang' tags if ALL copies are damaged/lost
            books = books.exclude(status='tidak_aktif').filter(
                Q(total_copies=0) |
                Q(total_copies__lte=F('borrowed_count') + F('damaged_copies') + F('lost_copies'))
            ).exclude(
                # If ALL copies are damaged or ALL are lost, they belong to those filters instead
                Q(total_copies__gt=0, damaged_copies=F('total_copies')) |
                Q(total_copies__gt=0, lost_copies=F('total_copies'))
            )
        elif status == 'rusak':
            books = books.filter(damaged_copies__gt=0).exclude(status='tidak_aktif')
        elif status == 'hilang':
            books = books.filter(lost_copies__gt=0).exclude(status='tidak_aktif')
        elif status == 'tidak_aktif':
            books = books.filter(status='tidak_aktif')

    paginator = Paginator(books, 12)
    page_obj  = paginator.get_page(request.GET.get('page', 1))

    all_cats = set()
    for cat in Book.objects.exclude(category__isnull=True).exclude(category='').values_list('category', flat=True):
        for c in cat.split(','):
            c = c.strip()
            if c:
                all_cats.add(c)

    # Create status choices
    status_choices = [
        ('tersedia', 'Tersedia'),
        ('tidak_tersedia', 'Tidak Tersedia'),
        ('rusak', 'Rusak'),
        ('hilang', 'Hilang'),
    ]
    if _is_staff_or_librarian(request.user):
        status_choices.append(('tidak_aktif', 'Tidak Aktif'))

    context = {
        'page_obj':       page_obj,
        'q':              q,
        'category':       category,
        'status':         status,
        'all_cats':       sorted(all_cats),
        'status_choices': status_choices,
        'total_count':    books.count(),
        'can_manage':     _is_staff_or_librarian(request.user),
    }
    return render(request, 'book_list.html', context)


# ─── Book Detail ──────────────────────────────────────────────────────────────

@login_required
def book_detail(request, pk):
    try:
        book = Book.objects.get(pk=pk)
    except Book.DoesNotExist:
        return render(request, '404.html', {'message': 'Buku tidak ditemukan.'}, status=404)

    reviews    = book.reviews.select_related('user').filter(deleted_at__isnull=True)
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
    user_review = reviews.filter(user=request.user).first()
    review_form = ReviewForm(instance=user_review)

    # Get book-specific loans if user is librarian
    book_loans = None
    waiting_lists = None
    user_in_waitlist = False

    if _is_librarian(request.user):
        book_loans = book.loans.select_related('user').all().order_by('-loan_date')
        waiting_lists = book.waiting_lists.select_related('user').filter(status__in=['menunggu', 'siap_dipinjam']).order_by('position')

    # Check if current user is in waitlist
    if hasattr(request.user, 'waiting_lists'):
        user_in_waitlist = request.user.waiting_lists.filter(book=book, status__in=['menunggu', 'siap_dipinjam']).exists()

    # Get waiting list count for display
    waiting_count = book.waiting_lists.filter(status='menunggu').count()

    context = {
        'book':        book,
        'reviews':     reviews,
        'avg_rating':  round(avg_rating, 1) if avg_rating else None,
        'review_form': review_form,
        'user_review': user_review,
        'can_manage':  _is_staff_or_librarian(request.user),
        'is_librarian': _is_librarian(request.user),
        'book_loans': book_loans,
        'waiting_lists': waiting_lists,
        'user_in_waitlist': user_in_waitlist,
        'waiting_count': waiting_count,
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
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'redirect_url': reverse('book:book_detail', kwargs={'pk': book.pk}),
                    'title': book.title
                })
                
            messages.success(request, f'Buku "{book.title}" berhasil ditambahkan.')
            return redirect('book:book_detail', pk=book.pk)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False, 
                    'errors': {f: e[0] for f, e in form.errors.items()}
                }, status=400)
                
            # Tampilkan semua error ke messages supaya kelihatan
            for field, errs in form.errors.items():
                for err in errs:
                    label = form.fields[field].label or field if field != '__all__' else ''
                    messages.error(request, f'{label}: {err}' if label else err)

    return render(request, 'book_form.html', {'form': form, 'action': 'add'})


# ─── Edit Book ────────────────────────────────────────────────────────────────

@login_required
def book_edit(request, pk):
    try:
        book = Book.objects.get(pk=pk)
    except Book.DoesNotExist:
        return render(request, '404.html', {'message': 'Buku tidak ditemukan.'}, status=404)

    if not _is_staff_or_librarian(request.user):
        messages.error(request, 'Anda tidak memiliki izin untuk mengedit buku.')
        return redirect('book:book_detail', pk=pk)

    form = BookForm(instance=book)

    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            b            = form.save(commit=False)
            b.updated_by = request.user
            b.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'redirect_url': reverse('book:book_detail', kwargs={'pk': b.pk}),
                    'title': b.title
                })

            messages.success(request, f'Buku "{b.title}" berhasil diperbarui.')
            return redirect('book:book_detail', pk=b.pk)
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False, 
                    'errors': {f: e[0] for f, e in form.errors.items()}
                }, status=400)

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
    if book.borrowed_copies > 0:
        messages.error(request, f'Buku "{book.title}" tidak dapat dinonaktifkan karena sedang dipinjam.')
        return redirect('book:book_detail', pk=pk)

    book.status     = 'tidak_aktif'
    book.updated_by = request.user
    book.save()
    messages.success(request, f'Buku "{book.title}" berhasil dinonaktifkan.')
    return redirect('book:book_list')


@login_required
@require_POST
def book_reactivate(request, pk):
    if not _is_staff_or_librarian(request.user):
        messages.error(request, 'Anda tidak memiliki izin untuk mengaktifkan buku.')
        return redirect('book:book_detail', pk=pk)

    book = get_object_or_404(Book, pk=pk)
    book.status = 'tersedia'
    book.updated_by = request.user
    book.save()
    messages.success(request, f'Buku "{book.title}" berhasil diaktifkan kembali.')
    return redirect('book:book_detail', pk=pk)


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
        if book.borrowed_copies > 0:
            return JsonResponse({
                'error': f'Buku "{book.title}" tidak dapat dihapus karena masih ada peminjaman aktif.'
            }, status=400)

        book.status = 'tidak_aktif'
        book.updated_by = request.user
        book.save()
        return JsonResponse({'message': 'Buku berhasil dinonaktifkan (soft delete)'})


# ─── API: Book Reviews ──────────────────────────────────────────────────────────

@login_required
@require_http_methods(["GET", "POST"])
def api_book_reviews(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    all_reviews = Review.objects.filter(book=book, deleted_at__isnull=True).select_related('user')
    reviews = all_reviews  # default to all

    if request.method == "GET":
        # Filter reviews if rating specified
        rating_filter = request.GET.get('rating', '').strip()
        if rating_filter and rating_filter.isdigit():
            rating = int(rating_filter)
            if 1 <= rating <= 5:
                reviews = reviews.filter(rating=rating)

        # ── Sorting: 'newest' (default, by created_at) atau 'recently_edited' (by updated_at)
        sort_by = request.GET.get('sort', 'newest').strip()
        if sort_by == 'recently_edited':
            reviews = reviews.order_by('-updated_at')
        else:
            reviews = reviews.order_by('-created_at')

        # Get reviews with pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        paginator = Paginator(reviews, per_page)
        page_obj = paginator.get_page(page)

        # Statistics (always for all reviews)
        total_reviews = all_reviews.count()
        avg_rating = all_reviews.aggregate(avg=Avg('rating'))['avg']
        distribution = {}
        for r in range(1, 6):
            distribution[r] = all_reviews.filter(rating=r).count()

        # ── Persistensi rating: kirim rating user saat ini (jika sudah pernah review)
        user_rating = None
        user_review_obj = all_reviews.filter(user=request.user).first()
        if user_review_obj:
            user_rating = user_review_obj.rating

        # Get user profile info
        review_data = []
        for review in page_obj:
            try:
                from authentication.models import UserProfile
                profile = UserProfile.objects.get(user=review.user)
                role = profile.get_role_display()
            except:
                role = 'Siswa'  # default

            # ── is_edited: True jika updated_at berbeda dari created_at
            is_edited = (
                review.updated_at is not None
                and review.created_at is not None
                and review.updated_at != review.created_at
            )

            review_data.append({
                'id': review.id,
                'user_id': review.user.id,
                'nama_reviewer': review.user.get_full_name() or review.user.username,
                'foto_profil': '',  # TODO: add profile picture if available
                'role': role,
                'rating': review.rating,
                'comment': review.comment,
                # Dual timestamp
                'created_at': review.created_at.isoformat() if review.created_at else None,
                'updated_at': review.updated_at.isoformat() if review.updated_at else (
                    review.created_at.isoformat() if review.created_at else None
                ),
                'is_edited': is_edited,
                # Legacy field — tetap dikirim agar tidak ada breaking change
                'timestamp': review.created_at.isoformat() if review.created_at else None,
            })

        return JsonResponse({
            'average_rating': round(avg_rating, 1) if avg_rating else None,
            'total_reviews': total_reviews,
            'rating_distribution': distribution,
            'reviews': review_data,
            'has_next': page_obj.has_next(),
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
            # Persistensi rating untuk pre-fill form
            'user_rating': user_rating,
        })

    elif request.method == "POST":
        # Check if user is librarian
        if _is_librarian(request.user):
            return JsonResponse({'error': 'Librarians cannot submit reviews.'}, status=403)

        # Submit review
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        rating = data.get('rating')
        comment = data.get('comment', '').strip()

        if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
            return JsonResponse({'error': 'Rating harus antara 1-5'}, status=400)

        if comment and len(comment) > 500:
            return JsonResponse({'error': 'Komentar maksimal 500 karakter'}, status=400)

        # Check for active review first
        active_review = all_reviews.filter(user=request.user).first()
        if active_review:
            # ── Update review: hanya updated_at yang berubah, created_at tetap
            active_review.rating  = rating
            active_review.comment = comment
            active_review.updated_at = timezone.now()
            active_review.save(update_fields=['rating', 'comment', 'updated_at'])
            return JsonResponse({
                'message': 'Review berhasil diperbarui',
                'review_id': active_review.id
            })

        # Check for soft-deleted review to restore
        deleted_review = Review.objects.filter(
            book=book,
            user=request.user,
            deleted_at__isnull=False
        ).first()

        if deleted_review:
            # ── Restore: anggap sebagai review baru — reset kedua timestamp
            deleted_review.rating     = rating
            deleted_review.comment    = comment
            deleted_review.deleted_at = None
            deleted_review.deleted_by = None
            deleted_review.created_at = timezone.now()
            deleted_review.updated_at = timezone.now()
            deleted_review.save()
            return JsonResponse({
                'message': 'Review berhasil dikirim',
                'review_id': deleted_review.id
            })

        # Create new review — created_at & updated_at di-set sama (auto via model)
        review = Review.objects.create(
            book=book,
            user=request.user,
            rating=rating,
            comment=comment,
        )

        return JsonResponse({
            'message': 'Review berhasil dikirim',
            'review_id': review.id
        }, status=201)


@login_required
@require_http_methods(["DELETE"])
def api_delete_review(request, book_id, review_id):
    book = get_object_or_404(Book, pk=book_id)
    review = get_object_or_404(Review, pk=review_id, book=book, deleted_at__isnull=True)

    # Check permissions: owner or staff/librarian
    if review.user != request.user and not _is_staff_or_librarian(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # Soft delete for owner, hard delete for admin
    if review.user == request.user:
        review.deleted_at = timezone.now()
        review.deleted_by = request.user
        review.save()
    else:
        review.delete()  # hard delete

    return JsonResponse({'message': 'Review berhasil dihapus'})

# ─── Bulk Upload Page ─────────────────────────────────────────────────────────

@login_required
def book_bulk_upload(request):
    if not _is_staff_or_librarian(request.user):
        messages.error(request, 'Anda tidak memiliki izin untuk mengakses fitur ini.')
        return redirect('book:book_list')
    return render(request, 'book_bulk_upload.html')


# ─── API: Bulk Upload Books ───────────────────────────────────────────────────

@login_required
@require_POST
def api_bulk_upload_books(request):
    """
    POST /api/books/bulk
    Menerima file CSV atau Excel, validasi setiap baris, lalu bulk insert (atomic).
    Hanya bisa diakses oleh Petugas Perpustakaan.
    ISBN bersifat opsional — jika kosong, buku diidentifikasi berdasarkan judul.
    """
    if not _is_staff_or_librarian(request.user):
        return JsonResponse({'error': 'Forbidden: hanya Petugas Perpustakaan yang dapat mengakses fitur ini.'}, status=403)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'Tidak ada file yang diunggah.'}, status=400)

    # Validasi tipe & ukuran file
    filename = uploaded_file.name.lower()
    allowed_extensions = ('.csv', '.xlsx', '.xls')
    if not filename.endswith(allowed_extensions):
        return JsonResponse({'error': 'Tipe file tidak valid. Hanya CSV dan Excel (.xlsx/.xls) yang diperbolehkan.'}, status=400)

    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    if uploaded_file.size > MAX_FILE_SIZE:
        return JsonResponse({'error': 'Ukuran file terlalu besar. Maksimal 5 MB.'}, status=400)

    # Parse file menjadi list of dicts
    rows = []

    try:
        if filename.endswith('.csv'):
            content = uploaded_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content))
            rows = list(reader)
        else:
            try:
                import openpyxl
            except ImportError:
                return JsonResponse({'error': 'Library openpyxl tidak terinstall. Gunakan file CSV.'}, status=500)

            wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
            ws = wb.active
            headers = None
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i == 0:
                    headers = [str(h).strip() if h is not None else '' for h in row]
                else:
                    if all(cell is None for cell in row):
                        continue
                    rows.append(dict(zip(headers, [str(c).strip() if c is not None else '' for c in row])))
            wb.close()
    except Exception as e:
        return JsonResponse({'error': f'Gagal membaca file: {str(e)}'}, status=400)

    if not rows:
        return JsonResponse({'error': 'File kosong atau tidak ada data yang dapat dibaca.'}, status=400)

    # Kolom yang diterima (case-insensitive, strip whitespace)
    COLUMN_MAP = {
        'title':         ['title', 'judul'],
        'author':        ['author', 'authors', 'author(s)', 'penulis'],
        'isbn':          ['isbn', 'isbn code', 'kode isbn'],
        'pages':         ['pages', 'length', 'jumlah halaman', 'halaman'],
        'language':      ['language', 'bahasa'],
        'total_copies':  ['total copies', 'total_copies', 'jumlah stok', 'stok'],
        'shelf_location':['shelf location', 'shelf_location', 'lokasi rak', 'rak'],
        'cover_url':     ['image', 'image(url)', 'cover url', 'cover_url', 'url gambar'],
        'category':      ['category', 'kategori'],
    }

    def normalize_key(raw_key):
        """Normalisasi header kolom ke field name standar."""
        k = raw_key.strip().lower()
        for field, aliases in COLUMN_MAP.items():
            if k in [a.lower() for a in aliases]:
                return field
        return None

    # Normalisasi header dari baris pertama
    if not rows:
        return JsonResponse({'error': 'File tidak memiliki data.'}, status=400)

    sample_keys = list(rows[0].keys())
    key_mapping = {}
    for raw_key in sample_keys:
        normalized = normalize_key(raw_key)
        if normalized:
            key_mapping[raw_key] = normalized

    # Cek kolom wajib ada di file — ISBN tidak lagi wajib
    REQUIRED_FIELDS_IN_FILE = ['title', 'author', 'total_copies']
    found_fields = set(key_mapping.values())
    missing_columns = [f for f in REQUIRED_FIELDS_IN_FILE if f not in found_fields]
    if missing_columns:
        col_display = {'title': 'Title', 'author': 'Author(s)', 'total_copies': 'Total Copies'}
        missing_labels = [col_display.get(f, f) for f in missing_columns]
        return JsonResponse({
            'error': f'Kolom wajib tidak ditemukan di file: {", ".join(missing_labels)}. Pastikan header sesuai template.'
        }, status=400)

    def normalize_isbn(isbn_val):
        """Kembalikan ISBN bersih, atau None jika kosong/tidak valid.
        Menangani nilai string kosong, '0', 'nan', 'none', serta float dari Excel."""
        if isbn_val is None:
            return None
        cleaned = str(isbn_val).strip()
        if cleaned.lower() in ('', '0', 'nan', 'none', 'null'):
            return None
        # Hapus desimal jika Excel membaca ISBN sebagai float (mis. 9786234727210.0)
        if cleaned.endswith('.0') and cleaned[:-2].isdigit():
            cleaned = cleaned[:-2]
        return cleaned

    # Bangun lookup dari DB:
    # - Buku ber-ISBN  → diindex by isbn
    # - Buku tanpa ISBN (isbn None) → diindex by title lowercase
    existing_by_isbn  = {}
    existing_by_title = {}
    for b in Book.objects.all():
        if b.isbn:
            existing_by_isbn[b.isbn.strip()] = b
        else:
            key = b.title.strip().lower()
            if key not in existing_by_title:
                existing_by_title[key] = b

    errors = []
    books_to_insert = []
    books_to_update = []
    books_to_skip   = []
    books_to_reject = []  # Buku yang ditolak karena ISBN sudah terdaftar di sistem
    seen_isbns_in_file   = set()  # Melacak ISBN duplikat dalam file
    seen_titles_in_file  = set()  # Melacak judul duplikat (untuk buku tanpa ISBN) dalam file

    for idx, raw_row in enumerate(rows, start=2):  # start=2 karena baris 1 = header
        # Remap keys
        row = {}
        for raw_key, val in raw_row.items():
            mapped = key_mapping.get(raw_key)
            if mapped:
                row[mapped] = str(val).strip() if val is not None else ''

        row_errors = []

        # Validasi field wajib tidak kosong (ISBN tidak termasuk)
        field_labels = {
            'title':        'Title',
            'author':       'Author(s)',
            'total_copies': 'Total Copies',
        }
        for field, label in field_labels.items():
            if not row.get(field, '').strip():
                row_errors.append(f'{label} tidak boleh kosong.')

        isbn      = normalize_isbn(row.get('isbn', ''))
        title     = row.get('title', '').strip()
        title_key = title.lower()

        # ── Deteksi duplikat dalam file ──────────────────────────────────────
        if isbn:
            # Buku ber-ISBN: duplikat = ISBN sama
            if isbn in seen_isbns_in_file:
                row_errors.append(f'ISBN "{isbn}" muncul lebih dari satu kali dalam file.')
            else:
                seen_isbns_in_file.add(isbn)
        else:
            # Buku tanpa ISBN: duplikat = judul sama (case-insensitive)
            if title_key in seen_titles_in_file:
                row_errors.append(f'Judul "{title}" muncul lebih dari satu kali dalam file (keduanya tanpa ISBN).')
            else:
                if title_key:
                    seen_titles_in_file.add(title_key)

        # Validasi format angka
        pages_raw = row.get('pages', '').strip()
        pages = None
        if pages_raw:
            if not pages_raw.isdigit() or int(pages_raw) < 0:
                row_errors.append('Jumlah halaman (Length) harus berupa angka positif.')
            else:
                pages = int(pages_raw)

        total_copies_raw = row.get('total_copies', '').strip()
        total_copies = None
        if total_copies_raw:
            if not total_copies_raw.isdigit() or int(total_copies_raw) < 0:
                row_errors.append('Total Copies harus berupa angka positif.')
            else:
                total_copies = int(total_copies_raw)
        elif 'total_copies' in found_fields:
            row_errors.append('Total Copies tidak boleh kosong.')

        if row_errors:
            errors.append({'row': idx, 'title': title or f'(Baris {idx})', 'errors': row_errors})
            continue

        # ── Cek ISBN sudah terdaftar di sistem → TOLAK (masuk books_to_reject) ──
        if isbn and isbn in existing_by_isbn:
            conflict_book = existing_by_isbn[isbn]
            books_to_reject.append({
                'row':    idx,
                'title':  title,
                'isbn':   isbn,
                'reason': f'ISBN "{isbn}" sudah terdaftar atas buku "{conflict_book.title}" di sistem.',
            })
            continue

        # ── Cek duplikat tanpa ISBN berdasarkan judul ────────────────────────
        if not isbn:
            existing_book = existing_by_title.get(title_key)
        else:
            existing_book = None  # ISBN baru, pasti tidak konflik

        new_total = total_copies or 1

        if existing_book:
            if new_total > existing_book.total_copies:
                existing_book.total_copies = new_total
                existing_book.updated_by   = request.user
                books_to_update.append({'book': existing_book, 'row': idx})
            else:
                books_to_skip.append({'title': existing_book.title, 'row': idx})
        else:
            books_to_insert.append({
                'data': {
                    'title':          title,
                    'author':         row.get('author', ''),
                    'isbn':           isbn or None,
                    'pages':          pages,
                    'language':       row.get('language', 'Indonesian') or 'Indonesian',
                    'total_copies':   new_total,
                    'shelf_location': row.get('shelf_location', ''),
                    'cover_url':      row.get('cover_url', '') or None,
                    'category':       row.get('category', '') or None,
                    'status':         'tersedia',
                    'updated_by':     request.user,
                },
                'row': idx,
            })

    # Jika ada error format/data → tolak semua (data belum ada yang tersimpan)
    if errors:
        return JsonResponse({
            'success': False,
            'message': f'Terdapat {len(errors)} baris dengan data tidak valid. Tidak ada data yang disimpan.',
            'errors': errors,
        }, status=400)

    # Tidak ada yang perlu dilakukan sama sekali
    if not books_to_insert and not books_to_update:
        return JsonResponse({
            'success': True,
            'message': 'Tidak ada buku baru yang ditambahkan.',
            'count_inserted': 0,
            'count_updated':  0,
            'count_skipped':  len(books_to_skip),
            'count_rejected': len(books_to_reject),
            'skipped':  books_to_skip,
            'rejected': books_to_reject,
        }, status=200)

    # Eksekusi insert + update dalam satu transaksi
    from django.db import transaction

    def _make_book(data):
        """Buat instance Book dengan normalisasi ISBN (mirip logika save())."""
        isbn_raw = data.get('isbn')
        if not isbn_raw or str(isbn_raw).strip() in ('', '0'):
            data['isbn'] = None
        else:
            data['isbn'] = str(isbn_raw).strip()
        return Book(**data)

    inserted_books = []
    updated_books  = []

    try:
        with transaction.atomic():
            if books_to_insert:
                created = Book.objects.bulk_create([_make_book(item['data']) for item in books_to_insert])
                inserted_books = [
                    {'title': item['data']['title'], 'isbn': item['data'].get('isbn'), 'row': item['row']}
                    for item in books_to_insert
                ]
            if books_to_update:
                Book.objects.bulk_update([item['book'] for item in books_to_update], ['total_copies', 'updated_by'])
                updated_books = [
                    {'title': item['book'].title, 'isbn': item['book'].isbn, 'row': item['row']}
                    for item in books_to_update
                ]
    except Exception as e:
        return JsonResponse({'error': f'Gagal menyimpan data: {str(e)}'}, status=500)

    # Susun pesan ringkasan
    parts = []
    if inserted_books:
        parts.append(f'{len(inserted_books)} buku baru ditambahkan')
    if updated_books:
        parts.append(f'{len(updated_books)} buku diperbarui stoknya')
    if books_to_skip:
        parts.append(f'{len(books_to_skip)} buku dilewati (sudah ada, stok sama)')
    if books_to_reject:
        parts.append(f'{len(books_to_reject)} buku ditolak (ISBN sudah terdaftar)')

    return JsonResponse({
        'success':        True,
        'message':        ' · '.join(parts) + '.',
        'count_inserted': len(inserted_books),
        'count_updated':  len(updated_books),
        'count_skipped':  len(books_to_skip),
        'count_rejected': len(books_to_reject),
        'inserted':       inserted_books,
        'updated':        updated_books,
        'skipped':        books_to_skip,
        'rejected':       books_to_reject,
    }, status=201 if inserted_books else 200)