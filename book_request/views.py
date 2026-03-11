from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import BookRequest


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
        messages.error(request, "Only students and teachers can request books.")
        return redirect('main:mainpage')

    # ── Student / Teacher: personal history ──────────────────────────────
    all_requests = BookRequest.objects.filter(requester=request.user)

    unseen = list(
        all_requests.filter(
            notification_seen=False,
            status__in=['approved', 'rejected'],
        ).values('id', 'title', 'status', 'reason')
    )

    counts = {
        'pending':  all_requests.filter(status='pending').count(),
        'approved': all_requests.filter(status='approved').count(),
        'rejected': all_requests.filter(status='rejected').count(),
        'total':    all_requests.count(),
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
    """Form to submit a new book request (students & teachers only)."""
    if _is_staff(request.user):
        return redirect('book_request:staff_dashboard')

    profile = _can_request(request.user)
    if not profile:
        messages.error(request, "Only students and teachers can request books.")
        return redirect('main:mainpage')

    if request.method == 'POST':
        title    = request.POST.get('title', '').strip()
        author   = request.POST.get('author', '').strip()
        category = request.POST.get('category', '').strip()
        reason   = request.POST.get('reason', '').strip()

        errors = {}
        if not title:
            errors['title'] = 'Book title is required.'
        if not author:
            errors['author'] = 'Author name is required.'
        if not reason:
            errors['reason'] = 'Please provide a reason for your request.'

        if errors:
            return render(request, 'book_request/request_form.html', {
                'errors': errors,
                'form_data': request.POST,
                'user_profile': profile,
            })

        book_request = BookRequest.objects.create(
            requester=request.user,
            title=title,
            author=author,
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
        messages.error(request, "You don't have permission to access this page.")
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
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    book_request = get_object_or_404(BookRequest, pk=pk)
    action = request.POST.get('action', '')  # 'approve' or 'reject'
    rejection_reason = request.POST.get('rejection_reason', '').strip()

    if action == 'approve':
        book_request.status = 'approved'
        book_request.reason = ''
        book_request.reviewed_by = request.user
        book_request.notification_seen = False
        book_request.save()
        messages.success(request, f'✅ "{book_request.title}" has been approved.')

    elif action == 'reject':
        if not rejection_reason:
            messages.error(request, 'Please provide a reason for rejection.')
            return redirect('book_request:staff_dashboard')
        book_request.status = 'rejected'
        book_request.reason = rejection_reason
        book_request.reviewed_by = request.user
        book_request.notification_seen = False
        book_request.save()
        messages.success(request, f'❌ "{book_request.title}" has been declined.')

    else:
        messages.error(request, 'Invalid action.')

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