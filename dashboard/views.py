from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta, date
import json

from authentication.models import UserProfile
from attendance.models import Attendance, AttendanceActivity
from book_loan.models import Loan
from book.models import Book


def _is_authorized(user):
    """Check if user is a teacher or librarian"""
    if user.is_superuser or user.is_staff:
        return True
    try:
        profile = user.profile
        return profile.role in ['teacher', 'librarian']
    except Exception:
        return False


def _get_date_range(period, custom_start=None, custom_end=None):
    """Return (start_date, end_date) based on period string."""
    today = timezone.now().date()
    if period == 'today':
        return today, today
    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())  
        return start, today
    elif period == 'this_month':
        return today.replace(day=1), today
    elif period == 'custom' and custom_start and custom_end:
        try:
            s = date.fromisoformat(custom_start)
            e = date.fromisoformat(custom_end)
            return s, e
        except ValueError:
            return today, today
    else:
        return today, today


@login_required
def dashboard_view(request):
    """Main dashboard page – accessible only to teachers and librarians."""
    if not _is_authorized(request.user):
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('main:mainpage')

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None

    is_librarian = (
        request.user.is_superuser or
        request.user.is_staff or
        (user_profile and user_profile.role == 'librarian')
    )
    return render(request, 'index.html', {
        'user_profile': user_profile,
        'is_librarian': is_librarian,
    })


# ─── API Endpoints ──────────────────────────────────────────────────────────

@login_required
def api_summary_stats(request):
    """
    GET /dashboard/api/summary/?period=today|this_week|this_month|custom
                                &start=YYYY-MM-DD&end=YYYY-MM-DD

    Returns four summary cards:
      total_visitors, active_loans, returned, overdue_loans
    """
    if not _is_authorized(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    period = request.GET.get('period', 'today')
    start_date, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    # 1. Total Visitors – attendance records in range
    total_visitors = Attendance.objects.filter(
        check_in_time__date__range=(start_date, end_date)
    ).count()

    today = timezone.now().date()

    # 2. Active Loans (currently borrowed)
    active_loans = Loan.objects.filter(
        status='sedang_dipinjam',
        due_date__gte=today
    ).count()

    # 3. Returned – loans returned within the period
    returned = Loan.objects.filter(
        return_date__date__range=(start_date, end_date),
        status='dikembalikan',
    ).count()

    # 4. Overdue Loans
    overdue_loans = Loan.objects.filter(
        Q(status='terlambat') |
        Q(status='sedang_dipinjam', due_date__lt=today)
    ).count()

    return JsonResponse({
        'status': 'success',
        'period': period,
        'period_label': f"{start_date} s/d {end_date}",
        'stats': {
            'total_visitors': total_visitors,
            'active_loans': active_loans,
            'returned': returned,
            'overdue_loans': overdue_loans,
        }
    })


@login_required
def api_loan_chart(request):
    """
    GET /dashboard/api/loan-chart/?period=today|this_week|this_month|custom
                                   &start=YYYY-MM-DD&end=YYYY-MM-DD

    Returns daily Borrowed vs Returned counts grouped by date for the
    requested period, ready for bar-chart visualisation.
    """
    if not _is_authorized(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    period = request.GET.get('period', 'this_month')
    start_date, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    # Build a day-by-day dict so every date in range is present
    delta = (end_date - start_date).days + 1
    day_map = {}
    for i in range(delta):
        d = (start_date + timedelta(days=i)).isoformat()
        day_map[d] = {'date': d, 'borrowed': 0, 'returned': 0}

    # Borrowed per day
    today = timezone.now().date()
    borrowed_qs = (
        Loan.objects.filter(
            loan_date__date__range=(start_date, end_date),
            status__in=['sedang_dipinjam', 'dikembalikan', 'terlambat', 'menunggu_persetujuan_perpanjangan']
        )
        .exclude(
            Q(status='terlambat') |
            Q(status='sedang_dipinjam', due_date__lt=today)
        )
        .values('loan_date__date')
        .annotate(count=Count('id'))
    )

    for row in borrowed_qs:
        key = row['loan_date__date'].isoformat()
        if key in day_map:
            day_map[key]['borrowed'] += row['count']

    # Pinjaman aktif yang dipinjam sebelum period tapi masih berlaku
    active_ongoing = Loan.objects.filter(
        status='sedang_dipinjam',
        loan_date__date__lt=start_date,
        due_date__gte=today,
    ).count()
    key = start_date.isoformat()
    if key in day_map:
        day_map[key]['borrowed'] += active_ongoing

    # Overdue: masuk sebagai borrowed di tanggal due_date+1
    today = timezone.now().date()
    overdue_qs = (
        Loan.objects.filter(
            Q(status='terlambat') |
            Q(status='sedang_dipinjam', due_date__lt=today),
            due_date__lt=end_date + timedelta(days=1),
        )
        .values('due_date')
        .annotate(count=Count('id'))
    )
    for row in overdue_qs:
        due_plus_one = row['due_date'] + timedelta(days=1)
        # kalau due_date+1 ada di range, pakai itu; kalau sudah lewat, masukkan ke start_date
        if due_plus_one.isoformat() in day_map:
            key = due_plus_one.isoformat()
        else:
            key = start_date.isoformat()
        if key in day_map:
            day_map[key]['borrowed'] += row['count']

    # Returned per day
    returned_qs = (
        Loan.objects.filter(
            return_date__date__range=(start_date, end_date),
            status='dikembalikan',
        )
        .values('return_date__date')
        .annotate(count=Count('id'))
    )
    for row in returned_qs:
        key = row['return_date__date'].isoformat()
        if key in day_map:
            day_map[key]['returned'] = row['count']

    data = list(day_map.values())

    # Summary totals
    total_borrowed = sum(d['borrowed'] for d in data)
    total_returned = sum(d['returned'] for d in data)

    return JsonResponse({
        'status': 'success',
        'period': period,
        'data': data,
        'labels': [d['date'] for d in data],
        'borrowed': [d['borrowed'] for d in data],
        'returned': [d['returned'] for d in data],
        'summary': {
            'total_borrowed': total_borrowed,
            'total_returned': total_returned,
        }
    })


@login_required
def api_popular_categories(request):
    if not _is_authorized(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # Tambahkan ini ↓
    period = request.GET.get('period', 'this_month')
    start_date, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    ALL_TIME_STATUSES = [
        'sedang_dipinjam',
        'menunggu_persetujuan_perpanjangan',
        'terlambat',
        'dikembalikan',
    ]

    loans = (
        Loan.objects.filter(
            Q(
                status__in=ALL_TIME_STATUSES,
                loan_date__date__range=(start_date, end_date),
            ) |
            Q(
                status='sedang_dipinjam',
                loan_date__date__lt=start_date,
                due_date__gte=start_date,
            ) |
            Q(
                status='terlambat',
                due_date__lt=end_date + timedelta(days=1),
            ) |
            Q(
                status='sedang_dipinjam',
                due_date__lt=timezone.now().date(),
            )
        )
        .select_related('book')
        .distinct()
    )

    category_counts = {}
    for loan in loans:
        cats = loan.book.category
        if not cats or not cats.strip():
            continue
        for cat in cats.split(','):
            cat = cat.strip()
            if cat:
                category_counts[cat] = category_counts.get(cat, 0) + 1

    sorted_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    if not sorted_cats:
        return JsonResponse({
            'status': 'success',
            'categories': [],
            'message': 'Data tidak tersedia',
        })

    max_count = sorted_cats[0][1]
    categories = [
        {
            'name': name,
            'count': count,
            'percentage': round((count / max_count) * 100),
        }
        for name, count in sorted_cats
    ]

    return JsonResponse({
        'status': 'success',
        'categories': categories,
    })


@login_required
def api_recent_activity(request):
    """
    GET /dashboard/api/recent-activity/

    Returns up to 10 most recent library activities:
    Borrowed, Returned, or Overdue events.
    """
    try:
        is_librarian = (
            request.user.is_superuser or
            request.user.is_staff or
            request.user.profile.role == 'librarian'
        )
    except Exception:
        is_librarian = request.user.is_superuser or request.user.is_staff

    if not is_librarian:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    # Fetch the 20 most recent loans (we'll pick the 10 most relevant)
    period = request.GET.get('period', 'today')
    _, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    recent_loans = (
        Loan.objects.select_related('user', 'book')
        .filter(
            Q(status__in=['sedang_dipinjam', 'dikembalikan']) |
            Q(status='terlambat'),
            loan_date__date__lte=end_date,
        )
        .order_by('-updated_at')[:50]
    )

    today = timezone.now().date()
    activities = []
    for loan in recent_loans:
        if loan.status == 'terlambat' or (
            loan.status == 'sedang_dipinjam' and
            loan.due_date and
            loan.due_date < today
        ):
            activity_type = 'Overdue'
            sort_key = loan.due_date + timedelta(days=1)
            timestamp = sort_key
        elif loan.status == 'sedang_dipinjam':
            activity_type = 'Borrowed'
            timestamp = loan.loan_date
            sort_key = loan.loan_date.date() if hasattr(loan.loan_date, 'date') else loan.loan_date
        elif loan.status == 'dikembalikan':
            activity_type = 'Returned'
            timestamp = loan.return_date or loan.updated_at
            sort_key = timestamp.date() if hasattr(timestamp, 'date') else timestamp
        else:
            continue

        if hasattr(timestamp, 'isoformat'):
            ts_str = timestamp.isoformat()
        else:
            ts_str = str(timestamp)

        activities.append({
            'type': activity_type,
            'member_name': (
                f"{loan.user.first_name} {loan.user.last_name}".strip()
                or loan.user.username
            ),
            'book_title': loan.book.title,
            'timestamp': ts_str,
            'loan_id': loan.id,
            '_sort_key': sort_key,
        })

    # Sort by timestamp terbaru, ambil 10
    activities.sort(key=lambda x: x['_sort_key'], reverse=True)
    activities = activities[:10]
    for a in activities:
        a.pop('_sort_key', None)

    return JsonResponse({
        'status': 'success',
        'activities': activities,
    })

@login_required
def api_dashboard(request):
    if not _is_authorized(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    period = request.GET.get('period', 'today')
    start_date, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    total_visitors = Attendance.objects.filter(
        check_in_time__date__range=(start_date, end_date)
    ).count()

    today = timezone.now().date()

    active_loans = Loan.objects.filter(
        status='sedang_dipinjam',
        due_date__gte=today
    ).count()

    returned = Loan.objects.filter(
        return_date__date__range=(start_date, end_date),
        status='dikembalikan'
    ).count()

    overdue_loans = Loan.objects.filter(
        Q(status='terlambat') |
        Q(status='sedang_dipinjam', due_date__lt=today)
    ).count()

    return JsonResponse({
        "status": "success",  
        "stats": {            
            "total_visitors": total_visitors,
            "active_loans": active_loans,
            "returned": returned,
            "overdue_loans": overdue_loans,
        }
    })

@login_required
def api_visitors_summary(request):
    """
    GET /api/dashboard/visitors/summary
    PBI-50: Active & Left Visitors
    """
    if not _is_authorized(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    period = request.GET.get('period', 'today')
    start_date, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    today = timezone.now().date()
    active_visitors = Attendance.objects.filter(
        check_in_time__date__range=(start_date, end_date),
        status='checked_in',
        check_in_time__date=today  # ← hanya yang check-in hari ini
    ).count()

    left_visitors = Attendance.objects.filter(
        check_in_time__date__range=(start_date, end_date),
    ).filter(
        Q(status__in=['checked_out', 'auto_checked_out']) |
        Q(status='checked_in', check_in_time__date__lt=today)
    ).count()

    return JsonResponse({
        'status': 'success',
        'period': period,
        'stats': {
            'active_visitors': active_visitors,
            'left_visitors': left_visitors,
        }
    })


@login_required
def api_visitors_trend(request):
    """
    GET /api/dashboard/visitors/trend
    PBI-51: Visitor Trend Line Chart
    """
    if not _is_authorized(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    period = request.GET.get('period', 'this_week')
    start_date, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    delta = (end_date - start_date).days + 1
    day_map = {}
    for i in range(delta):
        d = (start_date + timedelta(days=i)).isoformat()
        day_map[d] = {'date': d, 'visitors': 0}

    qs = (
        Attendance.objects.filter(
            check_in_time__date__range=(start_date, end_date)
        )
        .values('check_in_time__date')
        .annotate(count=Count('id'))
    )
    for row in qs:
        key = row['check_in_time__date'].isoformat()
        if key in day_map:
            day_map[key]['visitors'] = row['count']

    data = list(day_map.values())
    return JsonResponse({
        'status': 'success',
        'period': period,
        'data': data,
        'labels': [d['date'] for d in data],
        'visitors': [d['visitors'] for d in data],
        'summary': {
            'total_visitors': sum(d['visitors'] for d in data),
        }
    })


@login_required
def api_visitors_activity(request):
    """
    GET /api/dashboard/visitors/activity
    PBI-52: Activity Log check-in/check-out, hanya librarian
    """
    try:
        is_librarian = (
            request.user.is_superuser or
            request.user.is_staff or
            request.user.profile.role == 'librarian'
        )
    except Exception:
        is_librarian = request.user.is_superuser or request.user.is_staff

    if not is_librarian:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    period = request.GET.get('period', 'today')
    _, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    records = (
        Attendance.objects.select_related('user')
        .filter(check_in_time__date__lte=end_date)
        .order_by('-check_in_time')[:50]
    )

    activities = []
    for record in records:
        visitor_name = (
            f"{record.user.first_name} {record.user.last_name}".strip()
            or record.user.username
        )

        today = timezone.now().date()
        is_old_checkin = record.check_in_time.date() < today

        if record.status in ['checked_out', 'auto_checked_out'] or is_old_checkin:
            checkout_time = record.check_out_time or record.updated_at
            activities.append({
                'visitor_name': visitor_name,
                'action': 'Keluar',
                'timestamp': checkout_time.isoformat(),
                'record_id': record.id,
            })

        activities.append({
            'visitor_name': visitor_name,
            'action': 'Masuk',
            'timestamp': record.check_in_time.isoformat(),
            'record_id': record.id,
        })

    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    activities = activities[:10]

    return JsonResponse({
        'status': 'success',
        'activities': activities,
    })


@login_required
def api_visitors_popular_activities(request):
    """
    GET /api/dashboard/visitors/popular-activities
    PBI-53: Top 5 kategori aktivitas check-in
    """
    if not _is_authorized(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    period = request.GET.get('period', 'this_month')
    start_date, end_date = _get_date_range(
        period,
        request.GET.get('start'),
        request.GET.get('end'),
    )

    activity_counts = (
        AttendanceActivity.objects
        .filter(
            attendance_records__check_in_time__date__range=(start_date, end_date)
        )
        .annotate(total=Count('attendance_records'))
        .order_by('-total')[:5]
    )

    if not activity_counts:
        return JsonResponse({
            'status': 'success',
            'activities': [],
            'message': 'Data tidak tersedia',
        })

    max_count = activity_counts[0].total
    result = [
        {
            'name': a.name,
            'emoji': a.emoji,
            'count': a.total,
            'percentage': round((a.total / max_count) * 100),
        }
        for a in activity_counts
    ]

    return JsonResponse({
        'status': 'success',
        'activities': result,
    })

@login_required
def visitors_dashboard_view(request):
    if not _is_authorized(request.user):
        messages.error(request, "Anda tidak memiliki akses ke halaman ini.")
        return redirect('main:mainpage')

    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        user_profile = None

    is_librarian = (
        request.user.is_superuser or
        request.user.is_staff or
        (user_profile and user_profile.role == 'librarian')
    )
    return render(request, 'visitors.html', {
        'user_profile': user_profile,
        'is_librarian': is_librarian,
    })