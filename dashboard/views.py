from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta, date
import json

from authentication.models import UserProfile
from attendance.models import Attendance
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
        start = today - timedelta(days=today.weekday())  # Monday
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
    borrowed_qs = (
        Loan.objects.filter(
            loan_date__date__range=(start_date, end_date),
            status__in=['sedang_dipinjam', 'dikembalikan', 'terlambat', 'menunggu_persetujuan_perpanjangan']
        )
        .values('loan_date__date')
        .annotate(count=Count('id'))
    )

    for row in borrowed_qs:
        key = row['loan_date__date'].isoformat()
        if key in day_map:
            day_map[key]['borrowed'] = row['count']

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
            status__in=ALL_TIME_STATUSES,
            loan_date__date__range=(start_date, end_date),  # Tambahkan ini ↓
        )
        .select_related('book')
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
    recent_loans = (
        Loan.objects.select_related('user', 'book')
        .order_by('-updated_at')[:20]
    )

    activities = []
    for loan in recent_loans:
        if loan.status == 'sedang_dipinjam':
            activity_type = 'Borrowed'
            timestamp = loan.loan_date
        elif loan.status == 'dikembalikan':
            activity_type = 'Returned'
            timestamp = loan.return_date or loan.updated_at
        elif loan.status in ('terlambat',) or loan.is_overdue:
            activity_type = 'Overdue'
            timestamp = loan.due_date  # due_date is a date, handled below
        else:
            continue

        # Normalise timestamp to string
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
        })

        if len(activities) >= 10:
            break

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
        "status": "success",  # ← tambah ini
        "stats": {            # ← ganti "summary" jadi "stats"
            "total_visitors": total_visitors,
            "active_loans": active_loans,
            "returned": returned,
            "overdue_loans": overdue_loans,
        }
    })