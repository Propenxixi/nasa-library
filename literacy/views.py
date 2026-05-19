from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
from collections import defaultdict
from itertools import chain
import json
import threading
from django.db import transaction
from django.contrib.auth.models import User

from .models import BookReview, LiteracyPost, LiteracyLeaderboard, LiteracySession
from .forms import BookReviewForm, LiteracyPostForm, CommentForm, LiteracySessionForm
from authentication.models import UserProfile
from book_loan.models import Loan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATUS_LABEL = {'pending': 'Menunggu', 'verified': 'Disetujui', 'rejected': 'Ditolak'}


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'student'})
    return profile


def _get_kelas(user):
    try:
        return user.profile.kelas or ''
    except Exception:
        return ''


def _parse_periode(raw):
    """Parse 'YYYY-MM' string; fallback to current month."""
    try:
        return datetime.strptime(raw.strip(), '%Y-%m')
    except (ValueError, AttributeError):
        return timezone.now().replace(day=1)


def _month_range(periode_dt):
    """Return (start_date, end_date) aware datetimes for the given month."""
    start = periode_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
        end = timezone.make_aware(end)
    return start, end


def _build_verified_entries(br_qs, lp_qs):
    """Flatten BookReview + LiteracyPost querysets into uniform dicts."""
    entries = []
    for r in chain(br_qs, lp_qs):
        entries.append({
            'student_id': r.student_id,
            'student': r.student,
            'verified_at': r.verified_at,
        })
    return entries


def _parse_book_meta(content):
    """
    Parse '[Buku: Judul — Penulis | Penerbit]\\n\\n...' prefix written by
    create_post_view.  Returns (judul, penulis, penerbit, rangkuman).
    """
    judul = penulis = penerbit = ''
    rangkuman = content
    try:
        bracket_end = content.index(']')
        meta_str = content[7:bracket_end]           # strip '[Buku: '
        rangkuman = content[bracket_end + 3:].strip()
        if ' | ' in meta_str:
            left, penerbit = meta_str.rsplit(' | ', 1)
        else:
            left = meta_str
        if ' — ' in left:
            judul, penulis = left.split(' — ', 1)
        else:
            judul = left
    except Exception:
        pass
    return judul, penulis, penerbit, rangkuman


def _streak_from_weeks(verified_dates):
    """
    Hitung streak mingguan berturut-turut dari kumpulan tanggal verified_at.
    Streak dihitung mundur dari minggu paling akhir yang ada dalam data.
    Menggunakan format ISO week (%G-%V) agar konsisten dengan leaderboard.
    """
    if not verified_dates:
        return 0
    active_weeks = {dt.strftime('%G-%V') for dt in verified_dates if dt}
    if not active_weeks:
        return 0
    # Mulai dari minggu paling akhir dalam data, hitung berturut-turut ke belakang
    sorted_weeks = sorted(active_weeks, reverse=True)

    def week_to_date(gv):
        # format: 'YYYY-WW' (ISO year + ISO week number)
        from datetime import date as _date
        year_str, week_str = gv.split('-')
        return _date.fromisocalendar(int(year_str), int(week_str), 1)

    streak = 0
    current_date = week_to_date(sorted_weeks[0])
    for _ in range(len(active_weeks) + 1):
        wk = current_date.strftime('%G-%V')
        if wk in active_weeks:
            streak += 1
            current_date -= timedelta(days=7)
        else:
            break
    return streak


def _per_siswa_from_entries(entries):
    siswa_map = defaultdict(lambda: {'nama': '', 'kelas': '', 'jumlah_review': 0, 'weeks': set(), 'verified_dates': [], 'siswa_id': None})
    for r in entries:
        uid = r['student_id']
        siswa_map[uid]['nama'] = r['student'].get_full_name()
        siswa_map[uid]['siswa_id'] = uid
        siswa_map[uid]['kelas'] = _get_kelas(r['student'])
        siswa_map[uid]['jumlah_review'] += 1
        if r['verified_at']:
            siswa_map[uid]['weeks'].add(r['verified_at'].strftime('%Y-W%W'))
            siswa_map[uid]['verified_dates'].append(r['verified_at'])
    return siswa_map


def _per_kelas_from_entries(entries):
    kelas_map = defaultdict(lambda: {'total_review': 0, 'siswa_ids': set()})
    for r in entries:
        kelas = _get_kelas(r['student']) or '—'
        kelas_map[kelas]['total_review'] += 1
        kelas_map[kelas]['siswa_ids'].add(r['student_id'])
    return kelas_map


def _available_kelas():
    return list(
        UserProfile.objects
        .filter(role='student', kelas__isnull=False)
        .exclude(kelas='')
        .values_list('kelas', flat=True)
        .distinct()
        .order_by('kelas')
    )


# ---------------------------------------------------------------------------
# Input Review Buku Literasi
# ---------------------------------------------------------------------------

@login_required
def submit_review_view(request):
    """Student submits a book review (form-based)."""
    user_profile = _get_or_create_profile(request.user)
    if not user_profile.is_student():
        messages.error(request, "Only students can submit book reviews.")
        return redirect('literacy:leaderboard')

    if request.method == 'POST':
        form = BookReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.student = request.user
            review.save()
            messages.success(
                request,
                f"✨ Great job! Your review of '{review.title}' is pending teacher verification.",
            )
            return redirect('literacy:history')
    else:
        form = BookReviewForm()

    stats = {
        'reviews_count': BookReview.objects.filter(student=request.user).count(),
        'verified_count': BookReview.objects.filter(student=request.user, status='verified').count(),
    }
    return render(request, 'submit-review.html', {'form': form, 'user_profile': user_profile, 'stats': stats})


@login_required
@require_http_methods(["POST"])
def submit_review_api(request):
    """
     POST /api/literacy/reviews

    Body JSON: judul_buku*, penulis*, penerbit, tahun_terbit, rangkuman* (max 1000)
    Returns 201 Created | 400 Bad Request
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Request body harus berupa JSON yang valid.'}, status=400)

    judul_buku = body.get('judul_buku', '').strip()
    penulis = body.get('penulis', '').strip()
    penerbit = body.get('penerbit', '').strip()
    tahun_terbit = body.get('tahun_terbit')
    rangkuman = body.get('rangkuman', '').strip()

    errors = {}
    if not judul_buku:
        errors['judul_buku'] = 'Judul buku wajib diisi.'
    if not penulis:
        errors['penulis'] = 'Penulis wajib diisi.'
    if not rangkuman:
        errors['rangkuman'] = 'Rangkuman wajib diisi.'
    elif len(rangkuman) > 1000:
        errors['rangkuman'] = 'Rangkuman maksimal 1000 karakter.'
    if tahun_terbit is not None:
        try:
            tahun_terbit = int(tahun_terbit)
            if tahun_terbit < 1900:
                errors['tahun_terbit'] = 'Tahun terbit tidak valid.'
        except (TypeError, ValueError):
            errors['tahun_terbit'] = 'Tahun terbit harus berupa angka.'
    if errors:
        return JsonResponse({'error': 'Validasi gagal.', 'detail': errors}, status=400)

    review = BookReview.objects.create(
        student=request.user,
        title=judul_buku,
        author=penulis,
        publisher=penerbit or '',
        year_published=tahun_terbit or 0,
        summary=rangkuman,
        status='pending',
    )
    return JsonResponse({
        'message': 'Review berhasil disubmit dan menunggu verifikasi wali kelas.',
        'id': review.pk,
        'judul_buku': review.title,
        'penulis': review.author,
        'penerbit': review.publisher,
        'tahun_terbit': review.year_published,
        'rangkuman': review.summary,
        'tanggal_submit': review.created_at.isoformat(),
        'status': review.status,
        'status_label': 'Menunggu',
        'user_id': request.user.pk,
    }, status=201)


# ---------------------------------------------------------------------------
#  Riwayat Review Literasi Siswa
# ---------------------------------------------------------------------------

@login_required
def history_view(request):
    """Student views their full submission history (BookReview + LiteracyPost)."""
    user_profile = _get_or_create_profile(request.user)
    if not user_profile.is_student():
        messages.error(request, "Halaman riwayat hanya dapat diakses oleh siswa.")
        return redirect('literacy:leaderboard')

    status_filter = request.GET.get('status')
    valid_statuses = {'pending', 'verified', 'rejected'}
    # Abaikan nilai status yang tidak valid agar tidak memfilter secara salah
    if status_filter not in valid_statuses:
        status_filter = None

    br_qs = BookReview.objects.filter(student=request.user)
    if status_filter:
        br_qs = br_qs.filter(status=status_filter)

    book_reviews = [
        {
            'type': 'book_review', 'pk': r.pk, 'title': r.title,
            'author': r.author, 'publisher': r.publisher,
            'year_published': r.year_published, 'summary': r.summary,
            'status': r.status, 'rejection_reason': r.rejection_reason,
            'verified_by': r.verified_by, 'created_at': r.created_at,
        }
        for r in br_qs
    ]

    lp_qs = LiteracyPost.objects.filter(student=request.user).select_related('session')
    if status_filter:
        lp_qs = lp_qs.filter(verification_status=status_filter)

    literacy_posts = [
        {
            'type': 'literacy_post', 'pk': p.pk, 'title': p.title,
            'author': '', 'publisher': p.session.title if p.session else '',
            'year_published': None, 'summary': p.content,
            'status': p.verification_status, 'rejection_reason': p.rejection_reason,
            'verified_by': p.verified_by, 'created_at': p.created_at,
        }
        for p in lp_qs
    ]

    all_items = sorted(book_reviews + literacy_posts, key=lambda x: x['created_at'], reverse=True)

    base_br = BookReview.objects.filter(student=request.user)
    base_lp = LiteracyPost.objects.filter(student=request.user)
    stats = {
        'total_reviews': base_br.count() + base_lp.count(),
        'pending_reviews': (
                base_br.filter(status='pending').count() +
                base_lp.filter(verification_status='pending').count()
        ),
        'verified_reviews': (
                base_br.filter(status='verified').count() +
                base_lp.filter(verification_status='verified').count()
        ),
        'rejected_reviews': (
                base_br.filter(status='rejected').count() +
                base_lp.filter(verification_status='rejected').count()
        ),
    }
    # literacy/views.py — di fungsi history_view
    return render(request, 'literacy-history.html', {   # ← ganti ini
        'items': all_items,
        'stats': stats,
        'current_filter': status_filter,
        'user_profile': user_profile,
    })


@login_required
@require_http_methods(["GET"])
def my_reviews_api(request):
    """ GET /api/literacy/reviews/my-reviews"""
    data = []

    for r in BookReview.objects.filter(student=request.user).values(
            'id', 'title', 'author', 'publisher', 'year_published',
            'summary', 'status', 'rejection_reason', 'created_at',
    ):
        status_key = r['status']
        data.append({
            'id': r['id'], 'type': 'book_review',
            'judul_buku': r['title'], 'penulis': r['author'],
            'penerbit': r['publisher'], 'tahun': r['year_published'],
            'rangkuman': r['summary'],
            'tanggal_submit': r['created_at'].isoformat() if r['created_at'] else None,
            '_sort_key': r['created_at'],
            'status_verifikasi': status_key,
            'status_label': STATUS_LABEL.get(status_key, status_key),
            'catatan_wali': r['rejection_reason'] if status_key == 'rejected' else '',
        })

    for p in LiteracyPost.objects.filter(student=request.user).values(
            'id', 'title', 'content', 'verification_status', 'rejection_reason', 'created_at',
    ):
        status_key = p['verification_status']
        is_book_post = p['content'].startswith('[Buku:')
        actual_type = 'book_review' if is_book_post else 'literacy_post'
        judul, penulis, penerbit, rangkuman = _parse_book_meta(p['content']) if is_book_post else ('', '', '', p['content'])
        data.append({
            'id': p['id'], 'type': actual_type,
            'judul_buku': p['title'], 'penulis': penulis, 'penerbit': penerbit, 'tahun': None,
            'rangkuman': rangkuman,
            'tanggal_submit': p['created_at'].isoformat() if p['created_at'] else None,
            '_sort_key': p['created_at'],
            'status_verifikasi': status_key,
            'status_label': STATUS_LABEL.get(status_key, status_key),
            'catatan_wali': p['rejection_reason'] if status_key == 'rejected' else '',
        })

    data.sort(key=lambda x: x['_sort_key'] or timezone.now(), reverse=True)
    for item in data:
        item.pop('_sort_key', None)

    return JsonResponse(data, safe=False, status=200)


@login_required
@require_http_methods(["GET"])
def my_forum_posts_api(request):
    """
    GET /api/literacy/forum/posts/my-posts
    Riwayat postingan forum (LiteracyPost) milik siswa yang sedang login.
    Dipakai oleh section 'Riwayat Postingan Saya' di forum.html.
    """
    data = []
    for p in LiteracyPost.objects.filter(student=request.user).select_related('session').order_by('-created_at'):
        status_key = p.verification_status
        data.append({
            'id': p.pk,
            'post_pk': p.pk,
            'judul_buku': p.title,
            'sesi': p.session.title if p.session else '',
            'tanggal_submit': p.created_at.isoformat() if p.created_at else None,
            'status_verifikasi': status_key,
            'status_label': STATUS_LABEL.get(status_key, status_key),
            'catatan_wali': p.rejection_reason if status_key == 'rejected' else '',
        })
    return JsonResponse(data, safe=False, status=200)


@login_required
def review_detail_view(request, pk):
    """Student views a single review detail."""
    review = get_object_or_404(BookReview, pk=pk)
    if review.student != request.user:
        return HttpResponseForbidden("You cannot view this review.")
    return render(request, 'review-detail.html', {'review': review})


# ---------------------------------------------------------------------------
#  Verifikasi Review oleh Guru
# ---------------------------------------------------------------------------

@login_required
def teacher_verify_reviews_view(request):
    """
     Halaman daftar review pending untuk guru.
    Data di-fetch oleh JS via pending_reviews_api.
    """
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if not user_profile.is_teacher():
        messages.error(request, "Hanya guru yang dapat mengakses halaman ini.")
        return redirect('literacy:leaderboard')

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    br_pending = BookReview.objects.filter(status='pending')
    lp_pending = LiteracyPost.objects.filter(verification_status='pending')
    if user_profile.kelas:
        br_pending = br_pending.filter(student__profile__kelas=user_profile.kelas)
        lp_pending = lp_pending.filter(student__profile__kelas=user_profile.kelas)

    stats = {
        'pending_count': br_pending.count() + lp_pending.count(),
        'verified_today': (
                BookReview.objects.filter(status='verified', verified_by=request.user, verified_at__gte=today_start).count() +
                LiteracyPost.objects.filter(verification_status='verified', verified_by=request.user, verified_at__gte=today_start).count()
        ),
        'total_verified': (
                BookReview.objects.filter(status='verified', verified_by=request.user).count() +
                LiteracyPost.objects.filter(verification_status='verified', verified_by=request.user).count()
        ),
    }
    return render(request, 'teacher-verify-reviews.html', {
        'stats': stats,
        'user_profile': user_profile,
        'available_kelas': _available_kelas(),
    })


@login_required
@require_http_methods(["GET"])
def pending_reviews_api(request):
    """
     GET /api/literacy/reviews/pending

    Query params: ?kelas=X-1, ?type=book_review|literacy_post
    """
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'Profil pengguna tidak ditemukan.'}, status=403)

    if not user_profile.is_teacher():
        return JsonResponse({'error': 'Hanya guru yang dapat mengakses endpoint ini.'}, status=403)

    raw_kelas = request.GET.get('kelas', '').strip()
    kelas_filter = '' if raw_kelas in ('', 'None') else raw_kelas
    if not kelas_filter and user_profile.kelas and user_profile.kelas != 'None':
        kelas_filter = user_profile.kelas
    type_filter = request.GET.get('type', '').strip()

    data = []

    if type_filter in ('', 'book_review'):
        br_qs = BookReview.objects.filter(status='pending').select_related('student__profile').order_by('-created_at')
        if kelas_filter:
            br_qs = br_qs.filter(student__profile__kelas=kelas_filter)
        for r in br_qs:
            data.append({
                'id': r.pk, 'type': 'book_review', 'source_model': 'book_review',
                'nama_siswa': r.student.get_full_name(), 'kelas': _get_kelas(r.student),
                'judul_buku': r.title, 'penulis': r.author,
                'penerbit': r.publisher, 'tahun': r.year_published,
                'rangkuman': r.summary,
                'tanggal_submit': r.created_at.isoformat() if r.created_at else None,
                'status': 'pending',
            })

    if type_filter in ('', 'literacy_post', 'book_review'):
        lp_qs = (
            LiteracyPost.objects
            .filter(verification_status='pending')
            .select_related('student__profile', 'session')
            .order_by('-created_at')
        )
        if kelas_filter:
            lp_qs = lp_qs.filter(student__profile__kelas=kelas_filter)

        for p in lp_qs:
            is_book_post = p.content.startswith('[Buku:')
            actual_type = 'book_review' if is_book_post else 'literacy_post'
            if type_filter and type_filter != actual_type:
                continue
            judul, penulis, penerbit, rangkuman = _parse_book_meta(p.content) if is_book_post else ('', '', '', p.content)
            data.append({
                'id': p.pk, 'type': actual_type, 'source_model': 'literacy_post',
                'nama_siswa': p.student.get_full_name(), 'kelas': _get_kelas(p.student),
                'judul_buku': p.title, 'penulis': penulis,
                'penerbit': penerbit if is_book_post else (p.session.title if p.session else ''),
                'tahun': None, 'rangkuman': rangkuman,
                'tanggal_submit': p.created_at.isoformat() if p.created_at else None,
                'status': 'pending',
                'session_id': p.session.pk if p.session else None,
            })

    data.sort(key=lambda x: x['tanggal_submit'] or '', reverse=True)
    return JsonResponse(data, safe=False, status=200)


@login_required
@require_http_methods(["PUT", "POST"])
def verify_review_api(request, id):
    """
     PUT /api/literacy/reviews/<id>/verify

    Body JSON: { "status": "Disetujui"|"Ditolak", "catatan": "...", "source_model": "book_review"|"literacy_post" }
    Returns 200 | 400 | 403 | 404
    """
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'Profil pengguna tidak ditemukan.'}, status=403)

    if not user_profile.is_teacher():
        return JsonResponse({'error': 'Hanya guru yang dapat memverifikasi review.'}, status=403)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Request body harus berupa JSON yang valid.'}, status=400)

    status_input = body.get('status', '').strip()
    catatan = body.get('catatan', '').strip()
    item_type = body.get('type', 'book_review')
    source_model = body.get('source_model', item_type)

    if status_input not in {'Disetujui', 'Ditolak'}:
        return JsonResponse({'error': 'status harus Disetujui atau Ditolak.'}, status=400)
    if status_input == 'Ditolak' and not catatan:
        return JsonResponse({'error': 'catatan wajib diisi ketika status adalah Ditolak.'}, status=400)

    def _check_kelas(obj_student):
        if user_profile.kelas and _get_kelas(obj_student) != user_profile.kelas:
            return False
        return True

    if source_model == 'literacy_post':
        obj = LiteracyPost.objects.filter(pk=id).select_related('student__profile').first()
        if obj is None:
            return JsonResponse({'error': 'LiteracyPost tidak ditemukan.'}, status=404)
        if not _check_kelas(obj.student):
            return JsonResponse({'error': 'Anda hanya dapat memverifikasi posting dari siswa di kelas Anda.'}, status=403)
        obj.verify(request.user) if status_input == 'Disetujui' else obj.reject(request.user, catatan)
        if status_input == 'Disetujui':
            m, y = obj.verified_at.month, obj.verified_at.year
            threading.Thread(
                target=calculate_student_score, args=(obj.student, m, y), daemon=True
            ).start()
        return JsonResponse({
            'message': 'Review berhasil diverifikasi.', 'id': obj.pk,
            'type': item_type, 'source_model': 'literacy_post',
            'status': obj.verification_status,
            'verified_at': obj.verified_at.isoformat() if obj.verified_at else None,
            'verified_by': request.user.get_full_name(),
        })

    else:  # book_review
        obj = BookReview.objects.filter(pk=id).select_related('student__profile').first()
        if obj is None:
            return JsonResponse({'error': 'BookReview tidak ditemukan.'}, status=404)
        if not _check_kelas(obj.student):
            return JsonResponse({'error': 'Anda hanya dapat memverifikasi review dari siswa di kelas Anda.'}, status=403)
        obj.verify(request.user) if status_input == 'Disetujui' else obj.reject(request.user, catatan)
        if status_input == 'Disetujui':
            m, y = obj.verified_at.month, obj.verified_at.year
            threading.Thread(
                target=calculate_student_score, args=(obj.student, m, y), daemon=True
            ).start()
        return JsonResponse({
            'message': 'Review berhasil diverifikasi.', 'id': obj.pk,
            'type': item_type, 'source_model': 'book_review',
            'status': obj.status,
            'verified_at': obj.verified_at.isoformat() if obj.verified_at else None,
            'verified_by': request.user.get_full_name(),
        })


# ---------------------------------------------------------------------------
# Rekap Data Literasi
# ---------------------------------------------------------------------------

def _build_recap_data(br_qs, lp_qs):
    """Shared aggregation logic for recap_view and recap_api."""
    entries = _build_verified_entries(br_qs, lp_qs)
    siswa_map = _per_siswa_from_entries(entries)
    kelas_map = _per_kelas_from_entries(entries)

    per_siswa = sorted([
        {
            'siswa_id': uid,
            'nama': d['nama'],
            'kelas': d['kelas'],
            'jumlah_review': d['jumlah_review'],
            'konsistensi': _streak_from_weeks(d['verified_dates']),
        }
        for uid, d in siswa_map.items()
    ], key=lambda x: x['jumlah_review'], reverse=True)

    per_kelas = sorted([
        {
            'kelas': kelas,
            'total_review': d['total_review'],
            'jumlah_siswa': len(d['siswa_ids']),
            'rata_per_siswa': round(d['total_review'] / len(d['siswa_ids']), 1) if d['siswa_ids'] else 0,
        }
        for kelas, d in kelas_map.items()
    ], key=lambda x: x['total_review'], reverse=True)

    return entries, per_siswa, per_kelas, siswa_map


@login_required
def recap_view(request):
    """ Halaman rekap data literasi (guru & petugas perpustakaan)."""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if not (user_profile.is_teacher() or user_profile.role in ('librarian', 'staff', 'admin')):
        messages.error(request, "Halaman ini hanya dapat diakses oleh guru dan petugas perpustakaan.")
        return redirect('literacy:leaderboard')

    periode_dt = _parse_periode(request.GET.get('periode', ''))
    start_date, end_date = _month_range(periode_dt)
    current_kelas = request.GET.get('kelas', '').strip()
    siswa_id = request.GET.get('siswa_id', '').strip()

    br_qs = BookReview.objects.filter(
        status='verified', verified_at__gte=start_date, verified_at__lt=end_date,
    ).select_related('student__profile')
    lp_qs = LiteracyPost.objects.filter(
        verification_status='verified', verified_at__gte=start_date, verified_at__lt=end_date,
    ).select_related('student__profile')

    if current_kelas:
        br_qs = br_qs.filter(student__profile__kelas=current_kelas)
        lp_qs = lp_qs.filter(student__profile__kelas=current_kelas)

    entries, per_siswa, per_kelas, siswa_map = _build_recap_data(br_qs, lp_qs)

    # Jumlah total siswa per kelas (termasuk yang belum punya review)
    all_student_kelas = (
        UserProfile.objects
        .filter(role='student', kelas__isnull=False)
        .exclude(kelas='')
        .values('kelas')
        .annotate(n=Count('id'))
    )
    student_count_by_kelas = {row['kelas']: row['n'] for row in all_student_kelas}
    if current_kelas:
        student_count_by_kelas = {current_kelas: student_count_by_kelas.get(current_kelas, 0)}

    # Re-calculate rata_per_siswa using total student count (not just those with reviews)
    for k in per_kelas:
        n = student_count_by_kelas.get(k['kelas'], k['jumlah_siswa'])
        k['jumlah_siswa'] = n
        k['rata_per_siswa'] = round(k['total_review'] / n, 1) if n else 0

    total_review = len(entries)
    n_students = len(siswa_map) or 1
    max_kelas_count = per_kelas[0]['total_review'] if per_kelas else 1
    partisipasi_kelas = [
        {
            'kelas': k['kelas'],
            'count': k['total_review'],
            'pct': round(k['total_review'] / max_kelas_count * 100) if max_kelas_count else 0,
        }
        for k in per_kelas[:10]
    ]
    overview = {
        'total_review': total_review,
        'kelas_terbaik': per_kelas[0]['kelas'] if per_kelas else '',
        'kelas_terbaik_count': per_kelas[0]['total_review'] if per_kelas else 0,
        'siswa_terbaik': per_siswa[0]['nama'] if per_siswa else '',
        'siswa_terbaik_count': per_siswa[0]['jumlah_review'] if per_siswa else 0,
        'rata_per_siswa': round(total_review / n_students, 1),
        'partisipasi_kelas': partisipasi_kelas,
    }

    # Detail satu siswa
    detail_siswa = None
    if siswa_id:
        try:
            target_user = User.objects.get(pk=siswa_id)
            br_d = BookReview.objects.filter(student=target_user, created_at__gte=start_date, created_at__lt=end_date).order_by('-created_at')
            lp_d = LiteracyPost.objects.filter(student=target_user, created_at__gte=start_date, created_at__lt=end_date).order_by('-created_at')
            verified_weeks = set()
            for r in br_d.filter(status='verified'):
                if r.verified_at:
                    verified_weeks.add(r.verified_at.strftime('%Y-W%W'))
            for p in lp_d.filter(verification_status='verified'):
                if p.verified_at:
                    verified_weeks.add(p.verified_at.strftime('%Y-W%W'))
            detail_siswa = {
                'nama': target_user.get_full_name(),
                'kelas': _get_kelas(target_user),
                'jumlah_review': br_d.filter(status='verified').count() + lp_d.filter(verification_status='verified').count(),
                'konsistensi': len(verified_weeks),
                'pending': br_d.filter(status='pending').count() + lp_d.filter(verification_status='pending').count(),
                'ditolak': br_d.filter(status='rejected').count() + lp_d.filter(verification_status='rejected').count(),
                'reviews': [
                               {'entry_type': 'book', 'title': r.title, 'session': '', 'created_at': r.created_at, 'status': r.status}
                               for r in br_d
                           ] + [
                               {'entry_type': 'post', 'title': p.title, 'session': p.session.title if p.session else '', 'created_at': p.created_at, 'status': p.verification_status}
                               for p in lp_d.select_related('session')
                           ],
            }
        except User.DoesNotExist:
            pass

    return render(request, 'recap.html', {
        'current_periode': periode_dt.strftime('%Y-%m'),
        'current_periode_label': periode_dt.strftime('%B %Y'),
        'current_kelas': current_kelas,
        'available_kelas': _available_kelas(),
        'overview': overview,
        'per_siswa': per_siswa,
        'per_kelas': per_kelas,
        'detail_siswa': detail_siswa,
        'user_profile': user_profile,
    })


@login_required
@require_http_methods(["GET"])
def recap_api(request):
    """PBI-25 — GET /api/literacy/recap"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    if not (user_profile.is_teacher() or user_profile.role in ('librarian', 'staff', 'admin')):
        return JsonResponse({'error': 'Hanya guru dan petugas yang dapat mengakses endpoint ini.'}, status=403)

    periode_dt = _parse_periode(request.GET.get('periode', ''))
    start_date, end_date = _month_range(periode_dt)
    current_kelas = request.GET.get('kelas', '').strip()
    siswa_id = request.GET.get('siswa_id', '').strip()

    br_qs = BookReview.objects.filter(
        status='verified', verified_at__gte=start_date, verified_at__lt=end_date,
    ).select_related('student__profile')
    lp_qs = LiteracyPost.objects.filter(
        verification_status='verified', verified_at__gte=start_date, verified_at__lt=end_date,
    ).select_related('student__profile')

    if current_kelas:
        br_qs = br_qs.filter(student__profile__kelas=current_kelas)
        lp_qs = lp_qs.filter(student__profile__kelas=current_kelas)
    if siswa_id:
        br_qs = br_qs.filter(student_id=siswa_id)
        lp_qs = lp_qs.filter(student_id=siswa_id)

    entries, per_siswa, per_kelas, siswa_map = _build_recap_data(br_qs, lp_qs)
    total_review = len(entries)
    n_students = len(siswa_map) or 1

    return JsonResponse({
        'periode': periode_dt.strftime('%Y-%m'),
        'kelas_filter': current_kelas or None,
        'per_siswa': per_siswa,
        'per_kelas': per_kelas,
        'overview': {
            'total_review': total_review,
            'rata_per_siswa': round(total_review / n_students, 1),
            'siswa_terbaik': per_siswa[0] if per_siswa else None,
            'kelas_terbaik': per_kelas[0] if per_kelas else None,
        },
    }, status=200)


# ---------------------------------------------------------------------------
# Forum Posting Hasil Literasi
# ---------------------------------------------------------------------------

@login_required
def forum_view(request):
    """Forum utama — menampilkan daftar sesi literasi."""
    user_profile = _get_or_create_profile(request.user)
    sessions = LiteracySession.objects.all().prefetch_related('posts')

    search_query = request.GET.get('q', '').strip()
    if search_query:
        sessions = sessions.filter(Q(title__icontains=search_query) | Q(topic__icontains=search_query))

    topic_filter = request.GET.get('topic', '').strip()
    if topic_filter:
        sessions = sessions.filter(topic=topic_filter)

    sort_by = request.GET.get('sort', 'recent')
    if sort_by == 'entries':
        sessions = sessions.annotate(
            verified_count=Count('posts', filter=Q(posts__verification_status='verified'))
        ).order_by('-verified_count', '-date')
    else:
        sessions = sessions.order_by('-date', '-created_at')

    for session in sessions:
        session.entry_count = session.posts.filter(verification_status='verified').count()
        session.pending_count = session.posts.filter(verification_status='pending').count()

    return render(request, 'forum.html', {
        'sessions': sessions,
        'search_query': search_query,
        'sort_by': sort_by,
        'topic_filter': topic_filter,
        'topic_choices': LiteracySession.TOPIC_CHOICES,
        'total_sessions': LiteracySession.objects.count(),
        'total_verified': LiteracyPost.objects.filter(verification_status='verified').count(),
        'total_pending': LiteracyPost.objects.filter(verification_status='pending').count(),
        'user_profile': user_profile,
    })


@login_required
@require_http_methods(["POST"])
def create_forum_post_api(request):
    """
    PBI-26 — POST /api/literacy/forum/posts

    Body JSON: review_id* (harus milik siswa & sudah disetujui), caption (max 500), session_id
    Returns 201 Created | 400 Bad Request | 404 Not Found
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Request body harus berupa JSON yang valid.'}, status=400)

    review_id = body.get('review_id')
    caption = body.get('caption', '').strip()
    session_id = body.get('session_id')

    if not review_id:
        return JsonResponse({'error': 'review_id wajib diisi.'}, status=400)
    if caption and len(caption) > 500:
        return JsonResponse({'error': 'Caption maksimal 500 karakter.'}, status=400)

    try:
        review = BookReview.objects.get(pk=review_id, student=request.user)
    except BookReview.DoesNotExist:
        return JsonResponse({'error': 'Review tidak ditemukan.'}, status=404)

    if review.status != 'verified':
        return JsonResponse({'error': 'Hanya review yang sudah disetujui yang dapat diposting.'}, status=400)

    session = None
    if session_id:
        try:
            session = LiteracySession.objects.get(pk=session_id)
        except LiteracySession.DoesNotExist:
            return JsonResponse({'error': 'Sesi tidak ditemukan.'}, status=404)

    content = (caption + '\n\n' + review.summary) if caption else review.summary
    post = LiteracyPost.objects.create(
        student=request.user,
        title=review.title,
        content=content,
        book_review=review,
        session=session,
        verification_status='pending',
    )
    return JsonResponse({
        'message': 'Posting berhasil dibuat dan menunggu verifikasi guru.',
        'id': post.pk,
        'judul_buku': review.title,
        'penulis': review.author,
        'rangkuman': review.summary,
        'caption': caption,
        'nama_siswa': request.user.get_full_name(),
        'kelas': _get_kelas(request.user),
        'session_id': session.pk if session else None,
        'tanggal_submit': post.created_at.isoformat(),
        'status': post.verification_status,
    }, status=201)


# ---------------------------------------------------------------------------
# Forum — Sesi
# ---------------------------------------------------------------------------

@login_required
def create_session_view(request):
    """Guru membuat sesi literasi baru."""
    user_profile = _get_or_create_profile(request.user)
    if not user_profile.is_teacher():
        messages.error(request, "Hanya guru yang dapat membuat sesi literasi.")
        return redirect('literacy:forum')

    if request.method == 'POST':
        form = LiteracySessionForm(request.POST)
        if form.is_valid():
            session = form.save(commit=False)
            session.created_by = request.user
            session.is_open = True  # selalu terbuka saat dibuat
            session.save()
            messages.success(request, f"✅ Sesi '{session.title}' berhasil dibuat.")
            return redirect('literacy:session_detail', pk=session.pk)
    else:
        form = LiteracySessionForm()

    return render(request, 'create-session.html', {
        'form': form,
        'user_profile': user_profile,
        'next_number': LiteracySession.objects.count() + 1,
    })


@login_required
def session_detail_view(request, pk):
    """Detail satu sesi — tampilkan posting dalam sesi ini."""
    session = get_object_or_404(LiteracySession, pk=pk)
    user_profile = _get_or_create_profile(request.user)
    is_teacher = user_profile.is_teacher()

    if is_teacher:
        posts = session.posts.all().order_by('verification_status', 'created_at')
    else:
        posts = session.posts.filter(
            Q(verification_status='verified') | Q(student=request.user)
        ).order_by('-created_at')

    posts = posts.prefetch_related('likes', 'comments').select_related('student__profile', 'book_review')

    search_query = request.GET.get('q', '').strip()
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) | Q(content__icontains=search_query) |
            Q(student__first_name__icontains=search_query) | Q(student__last_name__icontains=search_query)
        )

    for post in posts:
        post.like_count = post.likes.count()
        post.comment_count = post.comments.count()
        post.user_liked = request.user in post.likes.all()

    session.pending_count = session.posts.filter(verification_status='pending').count()
    session.entry_count = session.posts.filter(verification_status='verified').count()

    return render(request, 'forum-session.html', {
        'session': session,
        'posts': posts,
        'search_query': search_query,
        'is_teacher': is_teacher,
        'user_profile': user_profile,
        'user_already_submitted': False if is_teacher else session.posts.filter(student=request.user).exists(),
    })


@login_required
def create_post_view(request):
    """Create a new literacy post via form (siswa).

    Hanya ada satu jenis postingan: Postingan Literasi.
    Field buku (judul, penulis, penerbit) bersifat opsional — diisi kalau
    postingan berkaitan dengan buku, boleh kosong untuk lesson learned dll.
    Sesi dideteksi otomatis dari query param ?session=<pk> yang sudah
    disertakan saat siswa menekan tombol "Buat Posting" di halaman sesi.
    """
    user_profile = _get_or_create_profile(request.user)
    session_pk = request.GET.get('session') or request.POST.get('session')
    active_session = get_object_or_404(LiteracySession, pk=session_pk) if session_pk else None

    if request.method == 'POST':
        # Kalau sesi sudah auto-detected, inject title dari nama sesi ke POST data
        # supaya form.title tidak gagal validasi required
        post_data = request.POST.copy()
        if active_session and not post_data.get('title', '').strip():
            post_data['title'] = active_session.title
        form = LiteracyPostForm(post_data)
        if form.is_valid():
            post = form.save(commit=False)
            post.student = request.user
            if active_session:
                post.session = active_session

            # Field buku opsional — hanya tambahkan meta jika judul buku diisi
            book_title = request.POST.get('book_title', '').strip()
            author = request.POST.get('author', '').strip()
            publisher = request.POST.get('publisher', '').strip()

            if book_title:
                book_meta = f"[Buku: {book_title}"
                if author:
                    book_meta += f" — {author}"
                if publisher:
                    book_meta += f" | {publisher}"
                book_meta += "]\n\n"
                post.content = book_meta + post.content

            post.save()
            messages.success(request, "✅ Posting berhasil disubmit dan menunggu verifikasi guru.")
            return redirect('literacy:session_detail', pk=active_session.pk) if active_session else redirect('literacy:history')
    else:
        form = LiteracyPostForm()
        form.fields['book_review'].queryset = BookReview.objects.filter(student=request.user, status='verified')

    return render(request, 'create-post.html', {
        'form': form,
        'user_profile': user_profile,
        'active_session': active_session,
        'stats': {
            'reviews_count': LiteracyPost.objects.filter(student=request.user).count(),
            'verified_count': LiteracyPost.objects.filter(student=request.user, book_review__status='verified').count(),
        },
    })


@login_required
def post_detail_view(request, pk):
    """View detailed post with comments."""
    post = get_object_or_404(LiteracyPost, pk=pk)
    post.like_count = post.likes.count()
    post.comment_count = post.comments.count()
    post.user_liked = request.user in post.likes.all()

    status = post.verification_status  # 'pending' | 'verified' | 'rejected'
    interactions_allowed = (status == 'verified')

    if request.method == 'POST':
        if not interactions_allowed:
            # Silently block like/comment attempts on non-verified posts
            return redirect('literacy:post_detail', pk=pk)
        if 'comment' in request.POST:
            form = CommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.post = post
                comment.student = request.user
                comment.save()
                messages.success(request, "Komentar berhasil ditambahkan!")
                return redirect('literacy:post_detail', pk=pk)
        elif 'like' in request.POST:
            if request.user in post.likes.all():
                post.likes.remove(request.user)
            else:
                post.likes.add(request.user)
            return redirect('literacy:post_detail', pk=pk)
    else:
        form = CommentForm()

    # Extract book metadata embedded in content (if no FK book_review set)
    book_info = None
    display_content = post.content
    if post.book_review:
        book_info = {
            'title': post.book_review.title,
            'author': post.book_review.author,
            'publisher': getattr(post.book_review, 'publisher', ''),
        }
    elif post.content.startswith('[Buku:'):
        judul, penulis, penerbit, rangkuman = _parse_book_meta(post.content)
        display_content = rangkuman
        if judul:
            book_info = {'title': judul, 'author': penulis, 'publisher': penerbit}

    return render(request, 'post-detail.html', {
        'post': post,
        'form': form,
        'comments': post.comments.all(),
        'book_info': book_info,
        'display_content': display_content,
        'is_pending': status == 'pending',
        'is_rejected': status == 'rejected',
        'interactions_allowed': interactions_allowed,
        'rejection_reason': post.rejection_reason if status == 'rejected' else '',
    })


@login_required
def delete_post_view(request, pk):
    """Fitur hapus post dinonaktifkan (tidak ada di PBI)."""
    return redirect('literacy:forum')

# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

@login_required
def leaderboard_view(request):
    """
    Halaman Leaderboard Siswa (EPIC07).
    Menampilkan ranking 1-50 berdasarkan skor satu sekolah.
    Mendukung filter: periode (bulan-tahun), kelas, angkatan.
    Ranking tetap berdasarkan posisi di satu sekolah.
    """
    user_profile = get_object_or_404(UserProfile, user=request.user)

    # 1. Handle Periode (Default bulan berjalan)
    raw_month = request.GET.get('month')
    raw_year  = request.GET.get('year')
    now = timezone.now()

    try:
        month = int(raw_month) if raw_month else now.month
        year  = int(raw_year)  if raw_year  else now.year
    except ValueError:
        month, year = now.month, now.year

    # 2. Ambil Leaderboard Satu Sekolah (untuk kalkulasi rank global)
    # AC: "Maksimal menampilkan top 50 siswa"
    leaderboard_qs = LiteracyLeaderboard.objects.filter(
        month=month, year=year
    ).select_related('student__profile').order_by('-total_score', 'first_activity_at', 'student__first_name')

    # Simpan dalam list untuk mempermudah indexing rank
    all_school_entries = list(leaderboard_qs)
    for idx, entry in enumerate(all_school_entries, 1):
        entry.global_rank = idx
        entry.streak = entry.consistency_score // 5
        entry.grade  = entry.student.profile.kelas.split()[0] if entry.student.profile.kelas else "?"

    # Filter: Hanya tampilkan siswa yang sudah berpartisipasi (skor > 0)
    participating_entries = [e for e in all_school_entries if e.total_score > 0]

    # 3. Handle Filtering & Searching (Nama, Kelas & Angkatan)
    # Meskipun difilter, global_rank tetap menempel pada objek entry
    search_query   = request.GET.get('q', '').strip().lower()
    scope_kelas    = request.GET.get('kelas', '').strip()
    scope_angkatan = request.GET.get('angkatan', '').strip()

    filtered_entries = participating_entries

    if search_query:
        filtered_entries = [e for e in filtered_entries if search_query in e.student.get_full_name().lower()]

    if scope_kelas:
        filtered_entries = [e for e in filtered_entries if e.student.profile.kelas == scope_kelas]
    elif scope_angkatan:
        filtered_entries = [e for e in filtered_entries if e.student.profile.kelas and e.student.profile.kelas.split()[0] == scope_angkatan]

    # 4. Global Statistics (Hanya dari partisipan aktif)
    total_active = len(participating_entries)
    avg_score = sum(e.total_score for e in participating_entries) / total_active if total_active > 0 else 0

    # Limit top 50 (Sesuai AC)
    display_entries = filtered_entries[:50]

    # 5. Stats Sekolah (Sesuai AC)
    angkatan_points = defaultdict(int)
    for e in all_school_entries:
        if e.student.profile.kelas:
            grade = e.student.profile.kelas.split()[0]
            angkatan_points[grade] += e.total_score
    angkatan_teraktif = max(angkatan_points, key=angkatan_points.get) if angkatan_points else "N/A"

    stats = {
        'total_partisipan':  total_active,
        'rata_rata_skor':    round(avg_score, 1),
        'angkatan_teraktif': angkatan_teraktif,
    }

    # Siswa Login Rank & Specific Stats
    user_entry = next((e for e in all_school_entries if e.student_id == request.user.id), None)

    # Extra stats for mockup: "Books currently borrowed"
    user_borrowed_count = 0
    if user_profile.is_student():
        user_borrowed_count = Loan.objects.filter(
            user=request.user,
            status__in=['siap_diambil', 'sedang_dipinjam', 'terlambat']
        ).count()

    # Available options for filters
    available_kelas = list(UserProfile.objects.filter(role='student', kelas__isnull=False).values_list('kelas', flat=True).distinct().order_by('kelas'))
    available_angkatan = sorted(list(set(k.split()[0] for k in available_kelas if k)))

    # Months for dropdown
    month_choices = [
        (1, 'Januari'), (2, 'Februari'), (3, 'Maret'), (4, 'April'),
        (5, 'Mei'), (6, 'Juni'), (7, 'Juli'), (8, 'Agustus'),
        (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Desember')
    ]
    year_choices = range(now.year - 2, now.year + 1)

    return render(request, 'leaderboard.html', {
        'leaderboard':        display_entries,
        'user_rank':          user_entry.global_rank if user_entry else None,
        'user_entry':         user_entry,
        'user_borrowed_count': user_borrowed_count,
        'stats':              stats,
        'user_profile':       user_profile,
        'current_month':      month,
        'current_year':       year,
        'current_q':          search_query,
        'current_kelas':      scope_kelas,
        'current_angkatan':   scope_angkatan,
        'month_choices':      month_choices,
        'year_choices':       year_choices,
        'available_kelas':    available_kelas,
        'available_angkatan': available_angkatan,
        'hero_winner':        all_school_entries[0] if all_school_entries else None,
    })
# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def calculate_leaderboard_scores(target_month=None, target_year=None):
    """
    PBI-27: Kalkulasi skor literasi sesuai Acceptance Criteria (EPIC07).

    1. Buku/Post Disetujui: 10 poin per item.
    2. Konsistensi (Streak): 5 poin per minggu berturut-turut (max 20 minggu).
    3. Bonus Kualitas: +5 poin jika konten/rangkuman > 500 karakter.
    """
    now = timezone.now()
    month = target_month if target_month else now.month
    year  = target_year  if target_year  else now.year

    start_date = timezone.datetime(year, month, 1)
    if month == 12:
        end_date = timezone.datetime(year + 1, 1, 1)
    else:
        end_date = timezone.datetime(year, month + 1, 1)

    start_date = timezone.make_aware(start_date)
    end_date = timezone.make_aware(end_date)

    students = UserProfile.objects.filter(role='student', is_active_student=True)

    for student_profile in students:
        student = student_profile.user

        # --- 1. Jumlah Buku & Bonus Kualitas (Verified in this period) ---
        br_qs = BookReview.objects.filter(
            student=student, status='verified',
            verified_at__gte=start_date, verified_at__lt=end_date
        )
        lp_qs = LiteracyPost.objects.filter(
            student=student, verification_status='verified',
            verified_at__gte=start_date, verified_at__lt=end_date
        )

        books_count = br_qs.count() + lp_qs.count()
        books_score = books_count * 10

        # Bonus Kualitas: 5 poin jika rangkuman > 500 karakter
        quality_bonus = 0
        for r in br_qs:
            if r.summary and len(r.summary) > 500:
                quality_bonus += 5
        for p in lp_qs:
            if p.content and len(p.content) > 500:
                quality_bonus += 5

        # --- 2. Konsistensi (Streak Mingguan) ---
        # AC: "5 poin per minggu berturut-turut (max 20 minggu)"

        # Ambil semua minggu unik di mana siswa memiliki verified activity (sepanjang waktu)
        all_activities = list(BookReview.objects.filter(student=student, status='verified').values_list('created_at', flat=True)) + \
                         list(LiteracyPost.objects.filter(student=student, verification_status='verified').values_list('created_at', flat=True))

        active_weeks = set()
        for dt in all_activities:
            if dt:
                # Pastikan aware datetime
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                # Geser 3 hari ke belakang agar Kamis jadi awal minggu (Kamis-Rabu menjadi Senin-Minggu secara ISO)
                shifted_dt = dt - timedelta(days=3)
                active_weeks.add(shifted_dt.strftime('%G-%V'))

        # Hitung streak ke belakang mulai dari minggu terakhir di periode target
        streak_count = 0
        if year == now.year and month == now.month:
            current_check_date = now
            # Sesuai request: Tidak ada "kemaafan". Jika di siklus berjalan (Kamis-Rabu) kosong, reset 0.
        else:
            current_check_date = end_date - timedelta(days=1)

        # Maksimal cek 20 minggu ke belakang
        for i in range(20):
            shifted_check = current_check_date - timedelta(days=3)
            week_key = shifted_check.strftime('%G-%V')
            if week_key in active_weeks:
                streak_count += 1
                current_check_date -= timedelta(days=7)
            else:
                break

        # --- 3. First Activity in Period (for tie-breaking) ---
        period_activities = list(chain(
            br_qs.values_list('created_at', flat=True),
            lp_qs.values_list('created_at', flat=True)
        ))
        first_activity = min([dt for dt in period_activities if dt], default=None)

        streak_score = streak_count * 5
        total_score  = books_score + quality_bonus + streak_score

        LiteracyLeaderboard.objects.update_or_create(
            student=student, month=month, year=year,
            defaults={
                'books_read':          books_count,
                'books_read_score':    books_score,
                'quality_bonus_score': quality_bonus,
                'consistency_score':   streak_score,
                'total_score':         total_score,
                'first_activity_at':   first_activity,
            }
        )

    # 3. Update Global Rank (School-wide) untuk periode ini
    all_entries = LiteracyLeaderboard.objects.filter(month=month, year=year).order_by('-total_score', 'first_activity_at', 'student__first_name')
    for idx, entry in enumerate(all_entries, 1):
        entry.rank = idx
        # Tandai ranking 1 sebagai kandidat duta (Monthly Ambassador)
        entry.is_monthly_ambassador = (idx == 1)
        entry.save()

def _update_ranks_for_period(month, year):
    """Bulk-update rank & is_monthly_ambassador untuk semua entry di periode tertentu."""
    all_entries = list(
        LiteracyLeaderboard.objects.filter(month=month, year=year)
        .order_by('-total_score', 'student__first_name')
        .only('id', 'rank', 'is_monthly_ambassador')
    )
    for idx, entry in enumerate(all_entries, 1):
        entry.rank = idx
        entry.is_monthly_ambassador = (idx == 1)
    LiteracyLeaderboard.objects.bulk_update(all_entries, ['rank', 'is_monthly_ambassador'])

def calculate_student_score(student, month, year):
    """
    Recalculate skor leaderboard hanya untuk SATU siswa, lalu update rank sekolah.
    Dipanggil saat guru approve review — jauh lebih cepat dari calculate_leaderboard_scores.
    """
    start_date = timezone.make_aware(timezone.datetime(year, month, 1))
    end_date = (
        timezone.make_aware(timezone.datetime(year + 1, 1, 1))
        if month == 12
        else timezone.make_aware(timezone.datetime(year, month + 1, 1))
    )

    br_qs = BookReview.objects.filter(
        student=student, status='verified',
        verified_at__gte=start_date, verified_at__lt=end_date,
    )
    lp_qs = LiteracyPost.objects.filter(
        student=student, verification_status='verified',
        verified_at__gte=start_date, verified_at__lt=end_date,
    )

    books_count = br_qs.count() + lp_qs.count()
    books_score = books_count * 10

    quality_bonus = 0
    for r in br_qs:
        if r.summary and len(r.summary) > 500:
            quality_bonus += 5
    for p in lp_qs:
        if p.content and len(p.content) > 500:
            quality_bonus += 5

    # Streak: cukup ambil verified_at dalam rentang yang relevan (max 20 minggu ke belakang)
    lookback_start = end_date - timedelta(weeks=20)
    all_dates = list(chain(
        BookReview.objects.filter(
            student=student, status='verified',
            verified_at__gte=lookback_start,
        ).values_list('verified_at', flat=True),
        LiteracyPost.objects.filter(
            student=student, verification_status='verified',
            verified_at__gte=lookback_start,
        ).values_list('verified_at', flat=True),
    ))

    active_weeks = {dt.strftime('%G-%V') for dt in all_dates if dt}

    streak_count = 0
    current_check_date = end_date - timedelta(days=1)
    for _ in range(20):
        week_key = current_check_date.strftime('%G-%V')
        if week_key in active_weeks:
            streak_count += 1
            current_check_date -= timedelta(days=7)
        else:
            break

    streak_score = streak_count * 5
    total_score = books_score + quality_bonus + streak_score

    LiteracyLeaderboard.objects.update_or_create(
        student=student, month=month, year=year,
        defaults={
            'books_read':          books_count,
            'books_read_score':    books_score,
            'quality_bonus_score': quality_bonus,
            'consistency_score':   streak_score,
            'total_score':         total_score,
        },
    )

    # Update rank untuk semua siswa di periode ini (bulk, bukan loop save)
    _update_ranks_for_period(month, year)

@login_required
@require_http_methods(["GET"])
def api_leaderboard(request):
    """
    PBI-28: GET /api/literacy/leaderboard/
    Mengembalikan data leaderboard 50 besar.
    """
    raw_month = request.GET.get('month')
    raw_year  = request.GET.get('year')
    now = timezone.now()

    month = int(raw_month) if raw_month else now.month
    year  = int(raw_year)  if raw_year  else now.year

    entries = LiteracyLeaderboard.objects.filter(
        month=month, year=year
    ).select_related('student__profile').order_by('-total_score', 'rank')[:50]

    data = []
    for e in entries:
        data.append({
            'rank':        e.rank,
            'siswa_id':    e.student.id,
            'nama':        e.student.get_full_name(),
            'kelas':       e.student.profile.kelas or '',
            'angkatan':    e.student.profile.kelas.split()[0] if e.student.profile.kelas else '',
            'skor_total':  e.total_score,
            'jumlah_buku': e.books_read,
            'konsistensi': e.consistency_score // 5, # dalam minggu
            'is_ambassador': e.is_monthly_ambassador
        })

    return JsonResponse(data, safe=False)

@login_required
@require_http_methods(["GET"])
def api_scores(request):
    """
    PBI-27: GET /api/literacy/scores
    Mengembalikan breakdown skor milik siswa yang login.
    """
    now = timezone.now()
    entry = LiteracyLeaderboard.objects.filter(
        student=request.user, month=now.month, year=now.year
    ).first()

    if not entry:
        return JsonResponse({
            'siswa_id': request.user.id,
            'nama': request.user.get_full_name(),
            'skor_total': 0,
            'breakdown_skor': {
                'jumlah_buku': 0,
                'poin_buku': 0,
                'konsistensi_minggu': 0,
                'poin_konsistensi': 0,
                'bonus_kualitas': 0
            }
        })

    return JsonResponse({
        'siswa_id':   request.user.id,
        'nama':       request.user.get_full_name(),
        'kelas':      request.user.profile.kelas or '',
        'skor_total': entry.total_score,
        'rank_sekolah': entry.rank,
        'breakdown_skor': {
            'jumlah_buku':        entry.books_read,
            'poin_buku':         entry.books_read_score,
            'konsistensi_minggu': entry.consistency_score // 5,
            'poin_konsistensi':  entry.consistency_score,
            'bonus_kualitas':    entry.quality_bonus_score
        }
    })