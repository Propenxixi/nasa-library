from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.utils import timezone
import json

from .models import BookRequest
from book.models import Book


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_staff(user):
    """True for superuser, is_staff, or librarian role."""
    if user.is_superuser or user.is_staff:
        return True
    try:
        return user.profile.is_librarian()
    except Exception:
        return False


def _can_request(user):
    """Return UserProfile if the user is a student or teacher, else None."""
    try:
        profile = user.profile
        return profile if (profile.is_student() or profile.is_teacher()) else None
    except Exception:
        return None


def _get_role_display(user):
    """Return role label in Indonesian."""
    try:
        profile = user.profile
        if profile.is_student():
            return 'Siswa'
        if profile.is_teacher():
            return 'Guru'
        if profile.is_librarian():
            return 'Petugas'
    except Exception:
        pass
    if user.is_staff or user.is_superuser:
        return 'Petugas'
    return 'Pengguna'


# ---------------------------------------------------------------------------
# Router: send staff to dashboard, students/teachers to their history
# ---------------------------------------------------------------------------

@login_required
def request_list_view(request):
    """Entry point – routes staff to dashboard, others to their own history."""
    if _is_staff(request.user):
        return redirect('book_request:staff_dashboard')

    profile = _can_request(request.user)
    if not profile:
        messages.error(request, "Hanya siswa dan guru yang dapat mengajukan usulan buku.")
        return redirect('main:mainpage')

    all_requests = BookRequest.objects.filter(requester=request.user)

    unseen = list(
        all_requests.filter(
            notification_seen=False,
            status__in=['approved', 'rejected'],
        ).values('id', 'title', 'status', 'catatan_petugas')
    )

    counts = {
        'total':    all_requests.count(),
        'pending':  all_requests.filter(status='pending').count(),
        'approved': all_requests.filter(status='approved').count(),
        'rejected': all_requests.filter(status='rejected').count(),
    }

    return render(request, 'book_request/request_list.html', {
        'requests': all_requests,
        'unseen_notifications': unseen,
        'user_profile': profile,
        'counts': counts,
    })


# ---------------------------------------------------------------------------
# Student / Teacher – submit a new request
# ---------------------------------------------------------------------------

@login_required
def request_create_view(request):
    if _is_staff(request.user):
        return redirect('book_request:staff_dashboard')

    profile = _can_request(request.user)
    if not profile:
        messages.error(request, "Hanya siswa dan guru yang dapat mengajukan usulan buku.")
        return redirect('main:mainpage')

    if request.method == 'POST':
        title    = request.POST.get('title', '').strip()
        author   = request.POST.get('author', '').strip()
        publisher = request.POST.get('publisher', '').strip()
        category  = request.POST.get('category', '').strip()
        reason    = request.POST.get('reason', '').strip()

        errors = {}
        if not title:
            errors['title'] = 'Judul buku wajib diisi.'
        if not author:
            errors['author'] = 'Nama penulis wajib diisi.'
        if not reason:
            errors['reason'] = 'Alasan pengajuan wajib diisi.'
        elif len(reason) > 500:
            errors['reason'] = 'Alasan pengajuan maksimal 500 karakter.'

        if errors:
            return render(request, 'book_request/request_form.html', {
                'errors': errors,
                'form_data': request.POST,
                'user_profile': profile,
            })

        confirmed = request.POST.get('duplicate_confirmed') == '1'

        if not confirmed:
            in_stock = Book.objects.filter(
                title__iexact=title
            ).exclude(status='tidak_aktif').exists()

            already_requested = BookRequest.objects.filter(
                title__iexact=title,
                status__in=['pending', 'approved'],
            ).exists()

            if in_stock:
                return render(request, 'book_request/request_form.html', {
                    'form_data': request.POST,
                    'user_profile': profile,
                    'duplicate_warning': True,
                    'duplicate_type': 'stock',
                    'duplicate_title': title,
                })

            elif already_requested:
                return render(request, 'book_request/request_form.html', {
                    'form_data': request.POST,
                    'user_profile': profile,
                    'duplicate_warning': True,
                    'duplicate_type': 'requested',
                    'duplicate_title': title,
                })

        book_request = BookRequest.objects.create(
            requester=request.user,
            title=title,
            author=author,
            publisher=publisher,
            category=category,
            reason=reason,
        )

        return redirect('book_request:request_success', pk=book_request.pk)

    return render(request, 'book_request/request_form.html', {
        'user_profile': profile,
    })


@login_required
def request_success_view(request, pk):
    """Success page shown right after submitting a request."""
    book_request = get_object_or_404(BookRequest, pk=pk, requester=request.user)
    return render(request, 'book_request/request_success.html', {
        'book_request': book_request,
    })


# ---------------------------------------------------------------------------
# Staff – review dashboard
# ---------------------------------------------------------------------------

@login_required
def staff_dashboard_view(request):
    """Petugas/librarian/superuser: see all requests, approve or decline."""
    if not _is_staff(request.user):
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('main:mainpage')

    status_filter = request.GET.get('status', '')

    all_requests = BookRequest.objects.select_related('requester', 'reviewed_by').all()
    if status_filter in ('pending', 'approved', 'rejected'):
        all_requests = all_requests.filter(status=status_filter)

    counts = {
        'pending':  BookRequest.objects.filter(status='pending').count(),
        'approved': BookRequest.objects.filter(status='approved').count(),
        'rejected': BookRequest.objects.filter(status='rejected').count(),
        'total':    BookRequest.objects.count(),
    }

    return render(request, 'book_request/staff_dashboard.html', {
        'requests':      all_requests,
        'counts':        counts,
        'status_filter': status_filter,
    })


@login_required
@require_POST
def staff_review_view(request, pk):
    """POST handler: approve or reject a single request."""
    if not _is_staff(request.user):
        return JsonResponse({'error': 'Tidak diizinkan'}, status=403)

    book_request = get_object_or_404(BookRequest, pk=pk)
    action = request.POST.get('action', '')  # 'approve' or 'reject'
    catatan_petugas = request.POST.get('catatan_petugas', '').strip()

    if action == 'approve':
        book_request.status = 'approved'
        book_request.catatan_petugas = catatan_petugas
        book_request.reviewed_by = request.user
        book_request.notification_seen = False
        book_request.save()
        messages.success(request, f'✅ "{book_request.title}" telah disetujui.')

    elif action == 'reject':
        if not catatan_petugas:
            messages.error(request, 'Mohon isi alasan penolakan.')
            return redirect('book_request:staff_dashboard')
        book_request.status = 'rejected'
        book_request.catatan_petugas = catatan_petugas
        book_request.reviewed_by = request.user
        book_request.notification_seen = False
        book_request.save()
        messages.success(request, f'❌ "{book_request.title}" telah ditolak.')

    else:
        messages.error(request, 'Aksi tidak valid.')

    return redirect('book_request:staff_dashboard')


# ---------------------------------------------------------------------------
# AJAX – mark pop-up notifications as seen (student side)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def mark_notifications_seen(request):
    BookRequest.objects.filter(
        requester=request.user,
        notification_seen=False,
        status__in=['approved', 'rejected'],
    ).update(notification_seen=True)
    return JsonResponse({'status': 'ok'})


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(["POST"])
def api_create_proposal(request):
    """
    POST /api/books/proposals
    Buat usulan buku baru. Return 201 jika berhasil, 400 jika validasi gagal.
    """
    profile = _can_request(request.user)
    if not profile:
        return JsonResponse({'error': 'Hanya siswa dan guru yang dapat mengajukan usulan.'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        data = request.POST

    title    = (data.get('title') or '').strip()
    author   = (data.get('author') or '').strip()
    publisher  = (data.get('publisher') or '').strip()
    category = (data.get('category') or '').strip()
    reason   = (data.get('reason') or '').strip()

    errors = {}
    if not title:
        errors['title'] = 'Judul buku wajib diisi.'
    if not author:
        errors['author'] = 'Nama penulis wajib diisi.'
    if not reason:
        errors['reason'] = 'Alasan pengajuan wajib diisi.'
    elif len(reason) > 500:
        errors['reason'] = 'Alasan pengajuan maksimal 500 karakter.'

    if errors:
        return JsonResponse({'errors': errors}, status=400)

    book_request = BookRequest.objects.create(
        requester=request.user,
        title=title,
        author=author,
        publisher=publisher,
        category=category,
        reason=reason,
    )

    return JsonResponse({
        'id': book_request.pk,
        'user_id': request.user.pk,
        'role': _get_role_display(request.user),
        'title': book_request.title,
        'author': book_request.author,
        'publisher': book_request.publisher,
        'category': book_request.category,
        'reason': book_request.reason,
        'status': 'Menunggu',
        'timestamp': book_request.created_at.isoformat(),
    }, status=201)


@login_required
@require_http_methods(["GET"])
def api_my_proposals(request):
    """
    GET /api/books/proposals/my-proposals
    Kembalikan daftar usulan milik pengaju yang sedang login.
    Return 200 dengan array data (kosong jika belum ada).
    """
    proposals = BookRequest.objects.filter(requester=request.user)

    STATUS_MAP = {'pending': 'Menunggu', 'approved': 'Disetujui', 'rejected': 'Ditolak'}

    data = [
        {
            'id': p.pk,
            'title': p.title,
            'author': p.author,
            'publisher': p.publisher,
            'category': p.category,
            'reason': p.reason,
            'status': STATUS_MAP.get(p.status, p.status),
            'catatan_petugas': p.catatan_petugas,
            'timestamp': p.created_at.isoformat(),
            'reviewed_at': p.updated_at.isoformat() if p.reviewed_by else None,
        }
        for p in proposals
    ]

    return JsonResponse({'data': data}, status=200)


@login_required
@require_http_methods(["GET"])
def api_pending_proposals(request):
    """
    GET /api/books/proposals/pending
    Kembalikan daftar usulan dengan status Menunggu (khusus petugas).
    """
    if not _is_staff(request.user):
        return JsonResponse({'error': 'Tidak diizinkan.'}, status=403)

    proposals = BookRequest.objects.filter(status='pending').select_related('requester')

    data = [
        {
            'id': p.pk,
            'user_id': p.requester.pk,
            'nama_pengaju': p.requester.get_full_name() or p.requester.username,
            'role': _get_role_display(p.requester),
            'title': p.title,
            'author': p.author,
            'publisher': p.publisher,
            'category': p.category,
            'reason': p.reason,
            'status': 'Menunggu',
            'timestamp': p.created_at.isoformat(),
        }
        for p in proposals
    ]

    return JsonResponse({'data': data}, status=200)


@login_required
@require_http_methods(["PUT"])
def api_review_proposal(request, pk):
    """
    PUT /api/books/proposals/{id}/review
    Approve atau reject usulan. Return 200/400/403/404.
    Body: { status: 'Disetujui'|'Ditolak', catatan_petugas: '...' }
    """
    if not _is_staff(request.user):
        return JsonResponse({'error': 'Tidak diizinkan.'}, status=403)

    book_request = get_object_or_404(BookRequest, pk=pk)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Request body tidak valid.'}, status=400)

    status_input    = (data.get('status') or '').strip()
    catatan_petugas = (data.get('catatan_petugas') or '').strip()

    STATUS_REVERSE = {'Disetujui': 'approved', 'Ditolak': 'rejected'}
    STATUS_MAP     = {'pending': 'Menunggu', 'approved': 'Disetujui', 'rejected': 'Ditolak'}

    if status_input not in STATUS_REVERSE:
        return JsonResponse(
            {'error': 'Status tidak valid. Gunakan "Disetujui" atau "Ditolak".'},
            status=400
        )

    if status_input == 'Ditolak' and not catatan_petugas:
        return JsonResponse(
            {'error': 'catatan_petugas wajib diisi saat menolak usulan.'},
            status=400
        )

    book_request.status          = STATUS_REVERSE[status_input]
    book_request.catatan_petugas = catatan_petugas
    book_request.reviewed_by     = request.user
    book_request.notification_seen = False
    book_request.save()

    return JsonResponse({
        'id': book_request.pk,
        'status': STATUS_MAP[book_request.status],
        'catatan_petugas': book_request.catatan_petugas,
        'reviewed_by': request.user.get_full_name() or request.user.username,
        'reviewed_at': book_request.updated_at.isoformat(),
    }, status=200)

@login_required
@require_http_methods(["GET"])
def check_duplicate_view(request):
    title = request.GET.get('title', '').strip()
    if not title:
        return JsonResponse({'duplicate_type': None})

    in_stock = Book.objects.filter(
        title__iexact=title
    ).exclude(status='tidak_aktif').exists()
    if in_stock:
        return JsonResponse({'duplicate_type': 'stock'})

    # Cek apakah USER INI SENDIRI sudah pernah mengajukan judul yang sama
    already_requested_by_me = BookRequest.objects.filter(
        title__iexact=title,
        requester=request.user,
    ).exists()
    if already_requested_by_me:
        return JsonResponse({'duplicate_type': 'own_request'})

    already_requested = BookRequest.objects.filter(
        title__iexact=title,
        status__in=['pending', 'approved'],
    ).exists()
    if already_requested:
        return JsonResponse({'duplicate_type': 'requested'})

    return JsonResponse({'duplicate_type': None})