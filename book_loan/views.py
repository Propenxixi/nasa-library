from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
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
    context = {
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
    }
    return render(request, 'notifications.html', context)


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
        
        existing = WaitingList.objects.filter(
            user=request.user,
            book=book,
            status__in=['menunggu', 'siap_dipinjam']
        ).first()
        
        if existing:
            return JsonResponse({
                'status': 'error',
                'message': 'Anda sudah dalam antrian untuk buku ini',
                'error_code': 'ALREADY_IN_QUEUE'
            }, status=409)
        
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
        
        last_in_queue = WaitingList.objects.filter(book=book).order_by('-position').first()
        next_position = (last_in_queue.position + 1) if last_in_queue else 1
        
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
        
        # Create loan with default 7 days duration (as per system requirements)
        duration_days = 7
        loan = Loan.objects.create(
            user=request.user,
            book=waiting.book,
            status='menunggu_konfirmasi',
            duration_days=duration_days
        )
        
        # Mark waiting as claimed
        waiting.claim()
        
        # Notify librarians
        librarians = UserProfile.objects.filter(is_staff=True).values_list('user_id', flat=True)
        for librarian_id in librarians:
            Notification.objects.create(
                user_id=librarian_id,
                notification_type='loan_approved',
                title='Pengajuan Peminjaman dari Antrian',
                message=f'{request.user.first_name} mengklaim antrian untuk {waiting.book.title}',
                loan=loan,
                book=waiting.book
            )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Berhasil mengklaim antrian. Menunggu persetujuan petugas.',
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
