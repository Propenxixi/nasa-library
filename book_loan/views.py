from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, F
from datetime import timedelta
import json

from .models import Loan, LoanExtension, WaitingList, Notification
from book.models import Book
from authentication.models import UserProfile


def _is_librarian_or_teacher(user):
    """Check if user is librarian or teacher"""
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.is_librarian() or profile.is_teacher()
    except:
        return False


def _is_librarian(user):
    """Check if user is librarian"""
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.is_librarian()
    except:
        return False


def _is_student(user):
    """Check if user is student"""
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.is_student()
    except:
        return False


@login_required
def loan_history(request):
    """Display user's loan history page with search and filtering"""
    if _is_librarian(request.user):
        loans = Loan.objects.all().select_related('user', 'book').prefetch_related('extensions')
    else:
        loans = Loan.objects.filter(user=request.user).select_related('book').prefetch_related('extensions')
    
    # Get filter parameters
    search = request.GET.get('search', '').strip()
    tanggal_pinjam = request.GET.get('tanggal_pinjam', '')
    jatuh_tempo = request.GET.get('jatuh_tempo', '')
    sisa_hari = request.GET.get('sisa_hari', '')
    status_filter = request.GET.get('status', '')
    
    # Apply search filter (nama, email, atau buku)
    if search:
        loans = loans.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(book__title__icontains=search) |
            Q(book__author__icontains=search)
        )
    
    # Apply tanggal pinjam filter
    if tanggal_pinjam:
        loans = loans.filter(loan_date__date=tanggal_pinjam)
    
    # Apply jatuh tempo filter
    if jatuh_tempo:
        loans = loans.filter(due_date__date=jatuh_tempo)
    
    # Apply sisa hari filter
    if sisa_hari:
        try:
            sisa_hari_int = int(sisa_hari)
            today = timezone.now().date()
            filter_date = today + timedelta(days=sisa_hari_int)
            loans = loans.filter(due_date__lte=filter_date, status='sedang_dipinjam')
        except (ValueError, TypeError):
            pass
    
    # Apply status filter
    if status_filter:
        if status_filter == 'siap_diambil':
            # Menampilkan keduanya: menunggu_konfirmasi dan siap_diambil
            loans = loans.filter(status__in=['menunggu_konfirmasi', 'siap_diambil'])
        else:
            loans = loans.filter(status=status_filter)
    
    # Determine if filters are active
    is_filtered = bool(search or tanggal_pinjam or jatuh_tempo or sisa_hari or status_filter)
    
    context = {
        'loans': loans,
        'status_filter': status_filter,
        'status_choices': Loan.STATUS_CHOICES,
        'search': search,
        'tanggal_pinjam': tanggal_pinjam,
        'jatuh_tempo': jatuh_tempo,
        'sisa_hari': sisa_hari,
        'is_filtered': is_filtered,
        'is_librarian': _is_librarian(request.user),
    }
    return render(request, 'loan_history.html', context)


@login_required
def waiting_list_view(request):
    """Display user's waiting list"""
    if _is_librarian(request.user):
        waiting_lists = WaitingList.objects.all().select_related('user', 'book')
    else:
        waiting_lists = WaitingList.objects.filter(user=request.user).select_related('book')
    
    context = {
        'waiting_lists': waiting_lists,
    }
    return render(request, 'waiting_list.html', context)


@login_required
def loan_management(request):
    """Librarian page for loan management with search and filtering"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('main:mainpage')
    
    # Get filter parameters
    search = request.GET.get('search', '').strip()
    tanggal_pinjam = request.GET.get('tanggal_pinjam', '')
    jatuh_tempo = request.GET.get('jatuh_tempo', '')
    sisa_hari = request.GET.get('sisa_hari', '')
    
    # Get all loans
    all_loans = Loan.objects.all().select_related('user', 'book').prefetch_related('extensions')
    
    # Apply search filter (nama, email, atau buku)
    if search:
        all_loans = all_loans.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(book__title__icontains=search) |
            Q(book__author__icontains=search)
        )
    
    # Apply tanggal pinjam filter
    if tanggal_pinjam:
        all_loans = all_loans.filter(loan_date__date=tanggal_pinjam)
    
    # Apply jatuh tempo filter
    if jatuh_tempo:
        all_loans = all_loans.filter(due_date__date=jatuh_tempo)
    
    # Apply sisa hari filter (only for sedang_dipinjam status)
    if sisa_hari:
        try:
            sisa_hari_int = int(sisa_hari)
            # Get current date and filter loans with days_remaining <= sisa_hari
            from datetime import datetime
            today = timezone.now().date()
            filter_date = today + timedelta(days=sisa_hari_int)
            all_loans = all_loans.filter(due_date__lte=filter_date, status='sedang_dipinjam')
        except (ValueError, TypeError):
            pass
    
    # Split by status
    today = timezone.now().date()
    
    pending_approvals = all_loans.filter(status='menunggu_konfirmasi')
    ready_for_pickup = all_loans.filter(status='siap_diambil')
    
    # Borrowed loans that are NOT overdue yet (due_date >= today)
    borrowed = all_loans.filter(status='sedang_dipinjam', due_date__gte=today)
    
    # Overdue loans: status='terlambat' OR (sedang_dipinjam AND due_date < today)
    overdue = all_loans.filter(
        Q(status='terlambat') | Q(status='sedang_dipinjam', due_date__lt=today)
    )
    
    pending_extensions = all_loans.filter(status='menunggu_persetujuan_perpanjangan')
    
    # Transform extensions data for template
    extensions_data = []
    for loan in pending_extensions:
        ext = loan.extensions.filter(status='pending').first()
        if ext:
            extensions_data.append({
                'id': ext.id,
                'loan_id': loan.id,
                'user': loan.user,
                'book': loan.book,
                'due_date': loan.due_date,
                'requested_extension_days': ext.requested_duration,
                'new_due_date': ext.new_due_date,
            })
    
    # Determine if filters are active
    is_filtered = bool(search or tanggal_pinjam or jatuh_tempo or sisa_hari)
    
    context = {
        'pending_approvals': pending_approvals,
        'ready_for_pickup': ready_for_pickup,
        'borrowed': borrowed,
        'overdue': overdue,
        'pending_extensions': extensions_data,
        'search': search,
        'tanggal_pinjam': tanggal_pinjam,
        'jatuh_tempo': jatuh_tempo,
        'sisa_hari': sisa_hari,
        'is_filtered': is_filtered,
    }
    return render(request, 'loan_management.html', context)


@login_required
def notifications(request):
    """Display user's notifications page"""
    return render(request, 'notifications.html')


@login_required
def loan_history_admin(request):
    """Admin/Librarian page for viewing book borrowing history and analytics"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('main:mainpage')

    # Get filter parameters
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    # Get all completed loans (dikembalikan)
    loans = Loan.objects.filter(status='dikembalikan').select_related('user', 'book')

    # Apply search filter (judul buku, penulis, atau peminjam)
    if search:
        loans = loans.filter(
            Q(book__title__icontains=search) |
            Q(book__author__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )

    # Apply status filter
    if status_filter == 'tepat_waktu':
        loans = loans.filter(is_overdue=False)
    elif status_filter == 'terlambat':
        loans = loans.filter(is_overdue=True)

    # Calculate statistics
    total_loans = loans.count()
    unique_borrowers = loans.values('user').distinct().count()
    on_time_loans = loans.filter(is_overdue=False).count()
    late_loans = loans.filter(is_overdue=True).count()

    # Get book borrowing analytics - group by book and calculate stats
    from django.db.models import Count, Max
    book_stats = loans.values('book').annotate(
        total_loans=Count('id'),
        unique_borrowers=Count('user', distinct=True),
        last_borrowed_date=Max('loan_date')
    ).order_by('-total_loans')[:10]  # Top 10 most borrowed books

    # Enrich with book details and loan history
    book_analytics = []
    for stat in book_stats:
        book = Book.objects.get(id=stat['book'])
        # Determine popularity based on total loans
        total_loans = stat['total_loans']
        if total_loans >= 10:
            popularity = 'Sangat Populer'
            popularity_class = 'emerald'
            icon = '🔥'
        elif total_loans >= 5:
            popularity = 'Cukup Populer'
            popularity_class = 'amber'
            icon = '⭐'
        else:
            popularity = 'Jarang Dipinjam'
            popularity_class = 'slate'
            icon = '📚'

        # Get loan history for this book
        book_loans = loans.filter(book=book).select_related('user').order_by('-loan_date')[:10]  # Last 10 loans for this book

        book_analytics.append({
            'book': book,
            'total_loans': total_loans,
            'unique_borrowers': stat['unique_borrowers'],
            'last_borrowed': stat['last_borrowed_date'],
            'popularity': popularity,
            'popularity_class': popularity_class,
            'icon': icon,
            'loan_history': book_loans,
        })

    # Get timeline data (recent loans for timeline view)
    timeline_loans = loans.select_related('user', 'book').order_by('-loan_date')[:20]  # Last 20 loans

    context = {
        'search': search,
        'status_filter': status_filter,
        'total_loans': total_loans,
        'unique_borrowers': unique_borrowers,
        'on_time_loans': on_time_loans,
        'late_loans': late_loans,
        'book_analytics': book_analytics,
        'timeline_loans': timeline_loans,
    }
    return render(request, 'loan_history_admin.html', context)


@login_required
def waiting_list_admin(request):
    """Admin/Librarian page for monitoring current waiting lists and queue status"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('main:mainpage')

    # Get filter parameters
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    # Get all books that have active waiting lists
    books_with_queues = Book.objects.filter(
        waiting_lists__status__in=['menunggu', 'siap_dipinjam']
    ).distinct().prefetch_related(
        'waiting_lists'
    )

    # Apply search filter (judul buku, penulis)
    if search:
        books_with_queues = books_with_queues.filter(
            Q(title__icontains=search) |
            Q(author__icontains=search)
        )

    # Get comprehensive data about waiting lists
    book_queue_data = []
    
    for book in books_with_queues:
        # Get all waiting lists for this book
        waiting_lists = book.waiting_lists.select_related('user').filter(
            status__in=['menunggu', 'siap_dipinjam']
        ).order_by('position', 'registered_date')

        # Apply status filter
        if status_filter:
            waiting_lists = waiting_lists.filter(status=status_filter)
        
        if not waiting_lists.exists():
            continue

        # Count by status
        waiting_count = waiting_lists.filter(status='menunggu').count()
        ready_count = waiting_lists.filter(status='siap_dipinjam').count()

        # Determine queue status
        if ready_count > 0:
            queue_status = 'Ada Yang Siap Diambil'
            status_class = 'emerald'
            icon = '✓'
        elif waiting_count > 0:
            queue_status = 'Menunggu Ketersediaan'
            status_class = 'amber'
            icon = '⏳'
        else:
            queue_status = 'Kosong'
            status_class = 'slate'
            icon = '—'

        book_queue_data.append({
            'book': book,
            'waiting_count': waiting_count,
            'ready_count': ready_count,
            'total_queue': waiting_count + ready_count,
            'queue_status': queue_status,
            'status_class': status_class,
            'icon': icon,
            'waiting_lists': waiting_lists,
        })

    # Sort by total queue size (descending)
    book_queue_data.sort(key=lambda x: x['total_queue'], reverse=True)

    # Calculate overall statistics
    total_books_with_queue = len(book_queue_data)
    total_people_waiting = sum(x['total_queue'] for x in book_queue_data)
    books_ready = sum(1 for x in book_queue_data if x['ready_count'] > 0)
    people_ready = sum(x['ready_count'] for x in book_queue_data)

    context = {
        'search': search,
        'status_filter': status_filter,
        'book_queue_data': book_queue_data,
        'total_books_with_queue': total_books_with_queue,
        'total_people_waiting': total_people_waiting,
        'books_ready': books_ready,
        'people_ready': people_ready,
    }
    return render(request, 'waiting_list_admin.html', context)


@login_required
@require_http_methods(["POST"])
def loan_approve(request, loan_id):
    """Approve a loan request"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses.")
        return redirect('book_loan:loan_management')
    
    try:
        loan = get_object_or_404(Loan, id=loan_id)
        
        if loan.status != 'menunggu_konfirmasi':
            messages.error(request, 'Peminjaman ini tidak sedang menunggu persetujuan')
            return redirect('book_loan:loan_management')
        
        loan.approve()
        
        Notification.objects.create(
            user=loan.user,
            notification_type='loan_approved',
            title='Peminjaman Disetujui',
            message=f'Peminjaman {loan.book.title} telah disetujui. Jatuh tempo: {loan.due_date}',
            loan=loan,
            book=loan.book
        )
        
        messages.success(request, f'✓ Peminjaman disetujui! Jatuh tempo: {loan.due_date.strftime("%d %b %Y")}')
        return redirect('book_loan:loan_management')
    
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('book_loan:loan_management')


@login_required
@require_http_methods(["POST"])
def loan_reject(request, loan_id):
    """Reject a loan request"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses.")
        return redirect('book_loan:loan_management')
    
    try:
        loan = get_object_or_404(Loan, id=loan_id)
        reason = request.POST.get('reason', 'Tidak ada alasan yang diberikan')
        
        loan.reject(reason)
        
        Notification.objects.create(
            user=loan.user,
            notification_type='loan_rejected',
            title='Peminjaman Ditolak',
            message=f'Peminjaman {loan.book.title} telah ditolak. Alasan: {reason}',
            loan=loan,
            book=loan.book
        )
        
        messages.success(request, '✓ Peminjaman ditolak')
        return redirect('book_loan:loan_management')
    
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('book_loan:loan_management')


@login_required
@require_http_methods(["POST"])
def loan_confirm_pickup(request, loan_id):
    """Confirm that a user has picked up the book"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses.")
        return redirect('book_loan:loan_management')
    
    try:
        loan = get_object_or_404(Loan, id=loan_id)
        
        if loan.status != 'siap_diambil':
            messages.error(request, 'Peminjaman ini tidak dalam status siap diambil')
            return redirect('book_loan:loan_management')
        
        loan.pickup()
        
        messages.success(request, '✓ Pengambilan buku dikonfirmasi')
        return redirect('book_loan:loan_management')
    
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('book_loan:loan_management')


@login_required
@require_http_methods(["POST"])
def loan_cancel(request, loan_id):
    """Cancel a ready-for-pickup loan"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses.")
        return redirect('book_loan:loan_management')
    
    try:
        loan = get_object_or_404(Loan, id=loan_id)
        
        if loan.status != 'siap_diambil':
            messages.error(request, 'Hanya peminjaman dengan status "Siap Diambil" yang dapat dibatalkan')
            return redirect('book_loan:loan_management')
        
        loan.cancel()
        
        # Notify user about cancellation
        Notification.objects.create(
            user=loan.user,
            notification_type='loan_cancelled',
            title='Peminjaman Dibatalkan',
            message=f'Peminjaman {loan.book.title} telah dibatalkan oleh petugas perpustakaan.',
            loan=loan,
            book=loan.book
        )
        
        messages.success(request, '✓ Peminjaman dibatalkan dan stok buku dikembalikan')
        return redirect('book_loan:loan_management')
    
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('book_loan:loan_management')


@login_required
@require_http_methods(["POST"])
def loan_process_return(request, loan_id):
    """Process book return"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses.")
        return redirect('book_loan:loan_management')
    
    try:
        loan = get_object_or_404(Loan, id=loan_id)
        condition = request.POST.get('condition', 'baik')
        notes = request.POST.get('notes', '')
        
        if loan.status != 'sedang_dipinjam':
            messages.error(request, 'Peminjaman ini tidak dalam status sedang dipinjam')
            return redirect('book_loan:loan_management')
        
        loan.process_return(condition)
        loan.return_notes = notes
        loan.save()
        
        # Message based on condition
        if condition == 'baik':
            msg = '✓ Pengembalian buku diproses - Buku tersedia kembali'
        elif condition == 'rusak':
            msg = '✓ Pengembalian buku diproses - Buku dicatat sebagai Rusak'
        else:  # hilang
            msg = '✓ Pengembalian buku diproses - Buku dicatat sebagai Hilang'
        
        messages.success(request, msg)
        return redirect('book_loan:loan_management')
    
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('book_loan:loan_management')


@login_required
@require_http_methods(["POST"])
def api_create_loan(request):
    """
    Create a new loan request
    POST /api/loans
    Body: { book_id, duration_days }
    """
    try:
        data = json.loads(request.body)
        book_id = data.get('book_id')
        duration_days = data.get('duration_days', 7)
        
        if not book_id:
            return JsonResponse({'status': 'error', 'message': 'book_id diperlukan'}, status=400)
        
        # Validasi durasi maksimal 7 hari
        if not isinstance(duration_days, int) or duration_days < 1 or duration_days > 7:
            return JsonResponse({
                'status': 'error', 
                'message': 'Durasi peminjaman harus antara 1-7 hari'
            }, status=400)
        
        book = get_object_or_404(Book, id=book_id)
        
        # Only students and teachers can borrow, NOT librarians
        if _is_librarian(request.user):
            return JsonResponse({
                'status': 'error',
                'message': 'Petugas perpustakaan tidak dapat meminjam buku'
            }, status=403)
        
        if not (_is_student(request.user) or _is_librarian_or_teacher(request.user)):
            return JsonResponse({
                'status': 'error',
                'message': 'Hanya siswa dan guru yang dapat meminjam buku'
            }, status=403)
        
        active_loan = Loan.objects.filter(
            user=request.user,
            book=book,
            status__in=['menunggu_konfirmasi', 'siap_diambil', 'sedang_dipinjam', 'menunggu_persetujuan_perpanjangan']
        ).first()
        
        if active_loan:
            return JsonResponse({
                'status': 'error',
                'message': 'Anda sudah meminjam atau mengajukan peminjaman buku ini'
            }, status=400)
        
        if book.status == 'tersedia' and book.available_copies > 0:
            loan = Loan.objects.create(
                user=request.user,
                book=book,
                status='menunggu_konfirmasi',
                duration_days=duration_days
            )
            
            librarians = UserProfile.objects.filter(role='librarian').values_list('user_id', flat=True)
            for librarian_id in librarians:
                Notification.objects.create(
                    user_id=librarian_id,
                    notification_type='loan_approved',
                    title='Pengajuan Peminjaman Baru',
                    message=f'{request.user.first_name} mengajukan peminjaman {book.title}',
                    loan=loan,
                    book=book
                )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Pengajuan peminjaman berhasil. Menunggu persetujuan petugas.',
                'loan_id': loan.id
            }, status=201)
        else:
            # Check if book is active but out of stock
            if book.is_active and book.available_copies <= 0:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Buku sedang tidak tersedia. Anda dapat menambahkan ke antrian.',
                    'is_waitlist_available': True,
                    'waiting_count': book.waiting_lists.filter(status='menunggu').count()
                }, status=400)
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Buku tidak tersedia'
                }, status=400)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_list_loans(request):
    """
    Get user's loans or all loans (for librarians)
    GET /api/loans
    """
    try:
        if _is_librarian(request.user):
            loans = Loan.objects.all().select_related('user', 'book')
        else:
            loans = Loan.objects.filter(user=request.user).select_related('book')
        
        status_filter = request.GET.get('status', '')
        if status_filter:
            loans = loans.filter(status=status_filter)
        
        loans_data = [{
            'id': loan.id,
            'book_title': loan.book.title,
            'book_author': loan.book.author,
            'user_name': f"{loan.user.first_name} {loan.user.last_name}",
            'status': loan.status,
            'status_display': loan.get_status_display(),
            'loan_date': loan.loan_date.isoformat(),
            'due_date': loan.due_date.isoformat() if loan.due_date else None,
            'return_date': loan.return_date.isoformat() if loan.return_date else None,
            'duration_days': loan.duration_days,
            'days_overdue': loan.days_overdue,
            'is_overdue': loan.days_overdue > 0,
            'can_extend': loan.can_extend,
        } for loan in loans]
        
        return JsonResponse({
            'status': 'success',
            'count': loans.count(),
            'loans': loans_data
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["PUT"])
def api_approve_loan(request, loan_id):
    """Approve a loan request"""
    try:
        if not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        loan = get_object_or_404(Loan, id=loan_id)
        
        if loan.status != 'menunggu_konfirmasi':
            return JsonResponse({
                'status': 'error',
                'message': 'Peminjaman ini tidak sedang menunggu persetujuan'
            }, status=400)
        
        loan.approve()
        
        # Update waiting list status to "siap_diambil_di_perpustakaan" if loan came from waiting list
        waiting = WaitingList.objects.filter(
            user=loan.user,
            book=loan.book,
            status='menunggu_konfirmasi_dari_admin'
        ).first()
        
        if waiting:
            waiting.status = 'siap_diambil_di_perpustakaan'
            waiting.approved_by_admin_date = timezone.now()
            waiting.save()
        
        Notification.objects.create(
            user=loan.user,
            notification_type='loan_approved',
            title='Peminjaman Disetujui',
            message=f'Peminjaman {loan.book.title} telah disetujui. Jatuh tempo: {loan.due_date}',
            loan=loan,
            book=loan.book
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Peminjaman disetujui',
            'due_date': loan.due_date.isoformat()
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["PUT"])
def api_pickup_loan(request, loan_id):
    """Mark loan as picked up"""
    try:
        loan = get_object_or_404(Loan, id=loan_id)
        
        if loan.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        if loan.status != 'siap_diambil':
            return JsonResponse({
                'status': 'error',
                'message': 'Buku ini belum siap diambil atau sudah diambil'
            }, status=400)
        
        loan.pickup()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Buku berhasil diambil. Harap kembalikan tepat pada tanggal jatuh tempo.',
            'due_date': loan.due_date.isoformat()
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["PUT"])
def api_reject_loan(request, loan_id):
    """Reject a loan request"""
    try:
        if not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        data = json.loads(request.body)
        reason = data.get('reason', '')
        
        loan = get_object_or_404(Loan, id=loan_id)
        
        if loan.status != 'menunggu_konfirmasi':
            return JsonResponse({
                'status': 'error',
                'message': 'Peminjaman ini tidak sedang menunggu persetujuan'
            }, status=400)
        
        loan.reject(reason)
        
        Notification.objects.create(
            user=loan.user,
            notification_type='loan_rejected',
            title='Peminjaman Ditolak',
            message=f'Peminjaman {loan.book.title} telah ditolak. Alasan: {reason}',
            loan=loan,
            book=loan.book
        )
        
        return JsonResponse({'status': 'success', 'message': 'Peminjaman ditolak'}, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["PUT"])
def api_return_loan(request, loan_id):
    """Process book return"""
    try:
        if not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        data = json.loads(request.body)
        condition = data.get('condition', '').lower()
        notes = data.get('notes', '')
        
        if condition not in ['baik', 'rusak', 'hilang']:
            return JsonResponse({'status': 'error', 'message': 'Kondisi tidak valid'}, status=400)
        
        loan = get_object_or_404(Loan, id=loan_id)
        
        if loan.status != 'sedang_dipinjam':
            return JsonResponse({
                'status': 'error',
                'message': 'Peminjaman ini tidak sedang dipinjam'
            }, status=400)
        
        loan.return_notes = notes
        loan.process_return(condition)
        
        condition_display = dict(Loan.BOOK_CONDITION_CHOICES).get(condition, condition)
        Notification.objects.create(
            user=loan.user,
            notification_type='loan_approved',
            title='Buku Dikembalikan',
            message=f'Pengembalian {loan.book.title} telah diproses. Kondisi: {condition_display}',
            loan=loan,
            book=loan.book
        )
        
        if condition == 'baik' and loan.book.waiting_lists.filter(status='menunggu').exists():
            next_in_queue = loan.book.waiting_lists.filter(status='menunggu').first()
            next_in_queue.mark_ready()
            
            Notification.objects.create(
                user=next_in_queue.user,
                notification_type='waitlist_ready',
                title='Giliran Antrian Tiba',
                message=f'{loan.book.title} sudah siap dipinjam. Punya 24 jam untuk mengklaimnya.',
                book=loan.book
            )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Pengembalian berhasil diproses'
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_request_extension(request, loan_id):
    """Request loan extension"""
    try:
        data = json.loads(request.body)
        duration_days = data.get('duration_days', 7)
        
        # Validasi durasi maksimal 7 hari
        if not isinstance(duration_days, int) or duration_days < 1 or duration_days > 7:
            return JsonResponse({
                'status': 'error', 
                'message': 'Durasi perpanjangan harus antara 1-7 hari'
            }, status=400)
        
        loan = get_object_or_404(Loan, id=loan_id)
        
        if loan.user != request.user and not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        if not loan.can_extend:
            return JsonResponse({
                'status': 'error',
                'message': 'Peminjaman tidak dapat diperpanjang. Cek tanggal jatuh tempo Anda.'
            }, status=400)
        
        if loan.book.waiting_lists.filter(status='menunggu').exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Perpanjangan tidak dapat dilakukan karena ada waiting list untuk buku ini'
            }, status=400)
        
        extension = LoanExtension.objects.create(
            loan=loan,
            requested_duration=duration_days,
            status='pending'
        )
        
        loan.status = 'menunggu_persetujuan_perpanjangan'
        loan.save()
        
        librarians = UserProfile.objects.filter(role='librarian').values_list('user_id', flat=True)
        for librarian_id in librarians:
            Notification.objects.create(
                user_id=librarian_id,
                notification_type='extension_approved',
                title='Permintaan Perpanjangan Peminjaman',
                message=f'{loan.user.first_name} mengajukan perpanjangan {loan.book.title}',
                loan=loan,
                book=loan.book
            )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Permintaan perpanjangan dikirim',
            'extension_id': extension.id
        }, status=201)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_approve_extension(request, loan_id):
    """Approve extension request"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses.")
        return redirect('book_loan:loan_management')
    
    try:
        extension = LoanExtension.objects.filter(loan_id=loan_id, status='pending').first()
        
        if not extension:
            messages.error(request, 'Tidak ada permintaan perpanjangan yang menunggu persetujuan')
            return redirect('book_loan:loan_management')
        
        extension.approve()
        
        Notification.objects.create(
            user=extension.loan.user,
            notification_type='extension_approved',
            title='Perpanjangan Disetujui',
            message=f'Perpanjangan {extension.loan.book.title} telah disetujui. Jatuh tempo baru: {extension.new_due_date.strftime("%d %b %Y")}',
            loan=extension.loan,
            book=extension.loan.book
        )
        
        messages.success(request, f'✓ Perpanjangan disetujui! Jatuh tempo baru: {extension.new_due_date.strftime("%d %b %Y")}')
        return redirect('book_loan:loan_management')
    
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('book_loan:loan_management')


@login_required
@require_http_methods(["POST"])
def api_reject_extension(request, loan_id):
    """Reject extension request"""
    if not _is_librarian(request.user):
        messages.error(request, "Anda tidak memiliki akses.")
        return redirect('book_loan:loan_management')
    
    try:
        reason = request.POST.get('rejection_reason', '')
        
        extension = LoanExtension.objects.filter(loan_id=loan_id, status='pending').first()
        
        if not extension:
            messages.error(request, 'Tidak ada permintaan perpanjangan yang menunggu persetujuan')
            return redirect('book_loan:loan_management')
        
        extension.reject(reason)
        
        Notification.objects.create(
            user=extension.loan.user,
            notification_type='extension_rejected',
            title='Perpanjangan Ditolak',
            message=f'Perpanjangan {extension.loan.book.title} telah ditolak. Alasan: {reason}' if reason else f'Perpanjangan {extension.loan.book.title} telah ditolak.',
            loan=extension.loan,
            book=extension.loan.book
        )
        
        messages.success(request, f'✓ Perpanjangan ditolak')
        return redirect('book_loan:loan_management')
    
    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('book_loan:loan_management')


@login_required
@require_http_methods(["GET"])
def api_get_notifications(request):
    """Get user's notifications"""
    try:
        notifications = Notification.objects.filter(user=request.user)
        unread_count = notifications.filter(is_read=False).count()
        
        notif_data = [{
            'id': n.id,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
            'loan_id': n.loan_id,
            'book_id': n.book_id,
        } for n in notifications[:20]]
        
        return JsonResponse({
            'status': 'success',
            'count': unread_count,
            'notifications': notif_data
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["PUT"])
def api_mark_notification_read(request, notification_id):
    """Mark notification as read"""
    try:
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        
        return JsonResponse({'status': 'success', 'message': 'Notifikasi ditandai sebagai sudah dibaca'}, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_create_waiting_list(request):
    """Join waiting list for a book"""
    try:
        # Librarians cannot join waiting lists
        if _is_librarian(request.user):
            return JsonResponse({
                'status': 'error',
                'message': 'Petugas perpustakaan tidak dapat masuk antrian'
            }, status=403)
        
        data = json.loads(request.body)
        book_id = data.get('book_id')
        
        if not book_id:
            return JsonResponse({'status': 'error', 'message': 'book_id diperlukan'}, status=400)
        
        book = get_object_or_404(Book, id=book_id)
        
        if book.status == 'tersedia' and book.available_copies > 0:
            return JsonResponse({
                'status': 'error',
                'message': 'Buku tersedia, tidak perlu antrian'
            }, status=400)
        
        # Check for active waiting list entries
        existing_active = WaitingList.objects.filter(
            user=request.user,
            book=book,
            status__in=['menunggu', 'siap_dipinjam']
        ).first()
        
        if existing_active:
            return JsonResponse({
                'status': 'error',
                'message': 'Anda sudah dalam antrian untuk buku ini',
                'error_code': 'ALREADY_IN_QUEUE'
            }, status=409)
        
        # Check for old cancelled/completed entries to reuse
        existing_old = WaitingList.objects.filter(
            user=request.user,
            book=book,
            status__in=['dibatalkan', 'selesai']
        ).first()
        
        active_loan = Loan.objects.filter(
            user=request.user,
            book=book,
            status__in=['menunggu_konfirmasi', 'siap_diambil', 'sedang_dipinjam']
        ).first()
        
        if active_loan:
            return JsonResponse({
                'status': 'error',
                'message': 'Anda sudah meminjam buku ini'
            }, status=400)
        
        # Count only active waiting list entries to determine next position
        active_count = WaitingList.objects.filter(
            book=book,
            status__in=['menunggu', 'siap_dipinjam']
        ).count()
        next_position = active_count + 1
        
        # If there's an old entry, reuse it instead of creating a new one
        if existing_old:
            existing_old.status = 'menunggu'
            existing_old.position = next_position
            existing_old.registered_date = timezone.now()
            existing_old.ready_date = None
            existing_old.claim_deadline = None
            existing_old.is_claimed = False
            existing_old.claimed_date = None
            existing_old.approved_by_admin_date = None
            existing_old.save()
            waiting = existing_old
        else:
            waiting = WaitingList.objects.create(
                user=request.user,
                book=book,
                position=next_position,
                status='menunggu'
            )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Anda berhasil masuk antrian. Posisi antrian kamu: #{next_position}',
            'position': next_position,
            'waiting_list_id': waiting.id,
            'queue_length': book.waiting_lists.filter(status='menunggu').count()
        }, status=201)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_my_waiting_list(request):
    """Get user's waiting list"""
    try:
        waiting_lists = WaitingList.objects.filter(user=request.user).select_related('book')
        
        data = [{
            'id': w.id,
            'book_title': w.book.title,
            'book_author': w.book.author,
            'position': w.position,
            'status': w.status,
            'status_display': w.get_status_display(),
            'registered_date': w.registered_date.isoformat(),
            'is_expired': w.is_expired,
            'claim_deadline': w.claim_deadline.isoformat() if w.claim_deadline else None,
        } for w in waiting_lists]
        
        return JsonResponse({
            'status': 'success',
            'count': waiting_lists.count(),
            'waiting_lists': data
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_cancel_waiting_list(request, waiting_id):
    """Cancel from waiting list"""
    try:
        waiting = get_object_or_404(WaitingList, id=waiting_id)
        
        if waiting.user != request.user and not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        waiting.cancel()

        # Update positions for remaining waiting list entries
        WaitingList.objects.filter(
            book=waiting.book,
            position__gt=waiting.position,
            status__in=['menunggu', 'siap_dipinjam']
        ).update(position=F('position') - 1)

        return JsonResponse({'status': 'success', 'message': 'Antrian dibatalkan'}, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
@login_required
@require_http_methods(["POST"])
def api_claim_waiting_list(request, waiting_id):
    """
    Claim a waiting list spot and create a loan
    POST /api/waitlist/<waiting_id>/claim/
    """
    try:
        waiting = get_object_or_404(WaitingList, id=waiting_id)
        
        # Check ownership
        if waiting.user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        # Check if already claimed or expired
        if waiting.is_claimed:
            return JsonResponse({'status': 'error', 'message': 'Antrian sudah diklaim'}, status=400)
        
        if waiting.is_expired:
            return JsonResponse({'status': 'error', 'message': 'Waktu klaim telah berakhir'}, status=400)
        
        if waiting.status != 'siap_dipinjam':
            return JsonResponse({'status': 'error', 'message': 'Antrian belum siap untuk diklaim'}, status=400)
        
        # Check if user already has active loan for this book
        active_loan = Loan.objects.filter(
            user=request.user,
            book=waiting.book,
            status__in=['menunggu_konfirmasi', 'siap_diambil', 'sedang_dipinjam', 'menunggu_persetujuan_perpanjangan']
        ).first()
        
        if active_loan:
            return JsonResponse({
                'status': 'error',
                'message': 'Anda sudah meminjam atau mengajukan peminjaman buku ini'
            }, status=400)
        
        # Create loan with default 7 days duration and auto-approve status
        duration_days = 7
        loan = Loan.objects.create(
            user=request.user,
            book=waiting.book,
            status='siap_diambil',  # Auto-approve directly to ready for pickup
            duration_days=duration_days,
            approved_date=timezone.now(),
            due_date=(timezone.now() + timedelta(days=duration_days)).date()
        )
        
        # Mark waiting list as claimed - completed status
        claimed_position = waiting.position
        waiting.is_claimed = True
        waiting.claimed_date = timezone.now()
        waiting.status = 'selesai'  # Mark as completed/claimed
        waiting.save()

        # Shift positions down for all remaining waiters behind this entry.
        # Do NOT promote the next person here — claiming the book does not free
        # up a copy. Promotion to 'siap_dipinjam' only happens when a book is
        # returned (handled in api_return_loan / process_return).
        WaitingList.objects.filter(
            book=waiting.book,
            position__gt=claimed_position,
            status='menunggu'
        ).update(position=F('position') - 1)

        # Notify user that their loan is ready
        Notification.objects.create(
            user=request.user,
            notification_type='loan_approved',
            title='Peminjaman Siap Diambil',
            message=f'{waiting.book.title} sudah siap untuk diambil. Jatuh tempo: {loan.due_date.strftime("%d %b %Y")}',
            loan=loan,
            book=waiting.book
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Peminjaman berhasil! Buku sudah masuk ke "Peminjaman Saya"',
            'loan_id': loan.id,
            'due_date': loan.due_date.isoformat() if loan.due_date else None
        }, status=201)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_get_waiting_list_by_book(request, book_id):
    """
    Get waiting list for a specific book (Librarian only)
    GET /api/waitlist/book/<book_id>/
    """
    try:
        if not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        book = get_object_or_404(Book, id=book_id)
        waiting_lists = WaitingList.objects.filter(book=book).select_related('user').order_by('position')
        
        data = [{
            'id': w.id,
            'position': w.position,
            'user_name': f"{w.user.first_name} {w.user.last_name}",
            'user_class': getattr(w.user.profile, 'grade', ''),
            'user_role': getattr(w.user.profile, 'role', ''),
            'registered_date': w.registered_date.isoformat(),
            'status': w.status,
            'status_display': w.get_status_display(),
            'claim_deadline': w.claim_deadline.isoformat() if w.claim_deadline else None,
            'is_expired': w.is_expired,
            'is_claimed': w.is_claimed,
        } for w in waiting_lists]
        
        return JsonResponse({
            'status': 'success',
            'book_title': book.title,
            'book_id': book.id,
            'count': waiting_lists.count(),
            'waiting_lists': data
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def api_notify_waiting_list(request, waiting_id):
    """
    Resend notification to waiting list user (Librarian only)
    POST /api/waitlist/<waiting_id>/notify/
    """
    try:
        if not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        waiting = get_object_or_404(WaitingList, id=waiting_id)
        
        # Create notification
        Notification.objects.create(
            user=waiting.user,
            notification_type='waitlist_ready',
            title='Pengingatan Antrian Anda',
            message=f'Giliran Anda untuk "{waiting.book.title}" sudah tiba. Silakan klaim dalam 24 jam.',
            book=waiting.book
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'Notifikasi telah dikirim ke {waiting.user.first_name}'
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_check_waiting_list(request, book_id):
    """
    Check if a book has active waiting list (for extension request)
    GET /api/waitlist/check/<book_id>/
    """
    try:
        book = get_object_or_404(Book, id=book_id)
        waiting_count = WaitingList.objects.filter(book=book, status='menunggu').count()
        
        return JsonResponse({
            'status': 'success',
            'has_waiting_list': waiting_count > 0,
            'waiting_count': waiting_count
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_get_active_loans(request):
    """Get active borrowed loans (for librarians)"""
    try:
        if not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        loans = Loan.objects.filter(status='sedang_dipinjam').select_related('user', 'book').order_by('due_date')
        
        data = [{
            'id': loan.id,
            'user_name': f"{loan.user.first_name} {loan.user.last_name}",
            'user_phone': getattr(loan.user, 'phone', ''),
            'book_title': loan.book.title,
            'book_isbn': loan.book.isbn,
            'due_date': loan.due_date.isoformat(),
            'loan_date': loan.loan_date.isoformat(),
            'days_overdue': loan.days_overdue,
            'is_overdue': loan.days_overdue > 0,
        } for loan in loans]
        
        return JsonResponse({
            'status': 'success',
            'count': loans.count(),
            'active_loans': data,
            'overdue_count': len([l for l in data if l['is_overdue']])
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_loan_detail(request, loan_id):
    """
    Get loan detail
    GET /api/loans/<loan_id>/detail/
    Returns: book info, borrower info, dates, and location
    """
    try:
        loan = get_object_or_404(Loan, id=loan_id)
        
        # Check access: user can only view their own loans, librarians can view all
        if loan.user != request.user and not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        # Format dates using locale-aware format
        loan_date_str = loan.loan_date.strftime('%d %b %Y').replace('Jan', 'Jan').replace('Feb', 'Feb').replace('Mar', 'Mar').replace('Apr', 'Apr').replace('May', 'May').replace('Jun', 'Jun').replace('Jul', 'Jul').replace('Aug', 'Aug').replace('Sep', 'Sep').replace('Oct', 'Oct').replace('Nov', 'Nov').replace('Dec', 'Dec')
        
        # Using natural date format for better display
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        loan_month = months[loan.loan_date.month - 1]
        loan_date_formatted = f"{loan.loan_date.day} {loan_month} {loan.loan_date.year}"
        
        # Handle due_date that might be None for rejected loans
        due_date_formatted = ''
        if loan.due_date:
            due_month = months[loan.due_date.month - 1]
            due_date_formatted = f"{loan.due_date.day} {due_month} {loan.due_date.year}"
        
        data = {
            'id': loan.id,
            'book_id': loan.book.id,
            'book_title': loan.book.title,
            'book_author': loan.book.author,
            'book_location': loan.book.shelf_location or 'Informasi lokasi tidak tersedia',
            'status': loan.status,
            'status_display': loan.get_status_display(),
            'loan_date': loan_date_formatted,
            'due_date': due_date_formatted,
            'borrower': f"{loan.user.first_name} {loan.user.last_name}",
            'borrower_name': f"{loan.user.first_name} {loan.user.last_name}",
            'quantity': 1,  # Standard quantity for single loan
            'days_overdue': loan.days_overdue,
            'is_overdue': loan.days_overdue > 0,
            'rejection_reason': loan.rejection_reason or '',  # Include rejection reason if loan was rejected
        }
        
        return JsonResponse({
            'status': 'success',
            'data': data
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def api_waiting_list_detail(request, waiting_id):
    """
    Get waiting list detail with current status
    GET /api/waitlist/<waiting_id>/detail/
    """
    try:
        waiting = get_object_or_404(WaitingList, id=waiting_id)
        
        # Check access: user can only view their own waiting lists, librarians can view all
        if waiting.user != request.user and not _is_librarian(request.user):
            return JsonResponse({'status': 'error', 'message': 'Akses ditolak'}, status=403)
        
        data = {
            'id': waiting.id,
            'book_id': waiting.book.id,
            'book_title': waiting.book.title,
            'book_author': waiting.book.author,
            'status': waiting.status,
            'status_display': waiting.get_status_display(),
            'position': waiting.position,
            'registered_date': waiting.registered_date.isoformat(),
            'is_claimed': waiting.is_claimed,
            'is_expired': waiting.is_expired,
            'claim_deadline': waiting.claim_deadline.isoformat() if waiting.claim_deadline else None,
            'available_copies': waiting.book.available_copies,
            'total_copies': waiting.book.total_copies,
        }
        
        return JsonResponse({
            'status': 'success',
            'data': data
        }, status=200)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)