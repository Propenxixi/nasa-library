from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta, date
import json

from .models import Attendance, AttendanceActivity
from .forms import CheckInForm
from authentication.models import UserProfile


@login_required
def check_in_view(request):
    """Student and teacher check-in page"""
    # Get user profile
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    # Check if user is a student or teacher
    if not (user_profile.is_student() or user_profile.is_teacher()):
        messages.error(request, "Only students and teachers can check in to the library.")
        return redirect('main:mainpage')
    
    # Check if already checked in today
    today = timezone.now().date()
    active_attendance = Attendance.objects.filter(
        user=request.user,
        check_in_time__date=today,
        status='checked_in'
    ).first()
    
    if active_attendance:
        # Already checked in, show check-out option
        return redirect('attendance:active_attendance')
    
    if request.method == 'POST':
        form = CheckInForm(request.POST)
        if form.is_valid():
            attendance = form.save(commit=False)
            attendance.user = request.user
            attendance.save()
            form.save_m2m()
            
            messages.success(
                request,
                f"Welcome to the library! ✨ You checked in at {attendance.check_in_time.strftime('%H:%M')}"
            )
            return redirect('attendance:active_attendance')
    else:
        form = CheckInForm()
    
    # Get reading stats for gamification (if available)
    reading_stats = get_reading_stats(request.user)
    
    # Get activities for the check-in form
    activities = AttendanceActivity.objects.filter(is_active=True)
    
    context = {
        'form': form,
        'user_profile': user_profile,
        'reading_stats': reading_stats,
        'activities': activities,
    }
    
    return render(request, 'check-in.html', context)


@login_required
def active_attendance_view(request):
    """Show active attendance and provide check-out option"""
    today = timezone.now().date()
    
    # Get current active attendance
    active_attendance = Attendance.objects.filter(
        user=request.user,
        check_in_time__date=today,
        status='checked_in'
    ).first()
    
    if not active_attendance:
        messages.info(request, "You are not currently checked in.")
        return redirect('attendance:check_in')
    
    # Calculate time spent
    time_spent = timezone.now() - active_attendance.check_in_time
    minutes_spent = int(time_spent.total_seconds() / 60)
    hours_spent = minutes_spent // 60
    remaining_minutes = minutes_spent % 60
    
    context = {
        'active_attendance': active_attendance,
        'minutes_spent': minutes_spent,
        'hours_spent': hours_spent,
        'remaining_minutes': remaining_minutes,
        'current_server_time': timezone.now(),
    }
    
    return render(request, 'active-attendance.html', context)


@login_required
def dashboard_view(request):
    """Dashboard for librarian and teacher - real-time statistics"""
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        messages.error(request, "User profile not found. Please contact administrator.")
        return redirect('main:mainpage')
    
    # Check if user has authorization
    if not user_profile.is_librarian() and not user_profile.is_teacher():
        messages.error(request, "You don't have permission to access this page.")
        return redirect('main:mainpage')
    
    today = timezone.now().date()
    
    # Real-time statistics
    active_visitors = Attendance.objects.filter(
        check_in_time__date=today,
        status='checked_in'
    ).count()
    
    total_visitors_today = Attendance.objects.filter(
        check_in_time__date=today
    ).count()
    
    # Last 7 days trend
    week_ago = today - timedelta(days=6)
    daily_stats = []
    for i in range(7):
        current_date = week_ago + timedelta(days=i)
        count = Attendance.objects.filter(check_in_time__date=current_date).count()
        daily_stats.append({
            'date': current_date.strftime('%a'),
            'count': count
        })
    
    # Activity statistics
    activity_stats = []
    activities = AttendanceActivity.objects.filter(is_active=True)
    for activity in activities:
        count = Attendance.objects.filter(
            check_in_time__date=today,
            activities=activity
        ).count()
        if count > 0:
            activity_stats.append({
                'name': str(activity),
                'count': count
            })
    
    # Average visit duration today
    avg_duration = Attendance.objects.filter(
        check_in_time__date=today,
        status__in=['checked_out', 'auto_checked_out']
    ).aggregate(avg=Avg('duration_minutes'))
    avg_duration_display = "—"
    if avg_duration['avg']:
        avg_minutes = int(avg_duration['avg'])
        hours = avg_minutes // 60
        minutes = avg_minutes % 60
        if hours > 0:
            avg_duration_display = f"{hours}h {minutes}m"
        else:
            avg_duration_display = f"{minutes}m"
    
    # Get all active visitors with details
    active_visitor_list = Attendance.objects.select_related('user__profile').filter(
        check_in_time__date=today,
        status='checked_in'
    ).order_by('-check_in_time')
    
    
    context = {
        'active_visitors': active_visitor_list,
        'active_count': active_visitors,
        'total_count': total_visitors_today,
        'daily_stats': daily_stats,
        'activity_stats': activity_stats,
        'avg_duration': avg_duration_display,
        'user_profile': user_profile,
        'today': today,
    }
    
    return render(request, 'attendance-dashboard.html', context)





@require_http_methods(["POST"])
@login_required
def auto_checkout_view(request, record_id):
    """Force check-out for a specific attendance record (admin use)"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    if not user_profile.is_librarian():
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    
    attendance = get_object_or_404(Attendance, id=record_id)
    
    if attendance.status == 'checked_in':
        attendance.check_out_time = timezone.now()
        attendance.status = 'checked_out'
        attendance.save()
        return JsonResponse({'status': 'success', 'duration': attendance.duration_display})
    
    return JsonResponse({'status': 'error', 'message': 'Already checked out'})


@login_required
def attendance_history_view(request):
    """Student's attendance history page"""
    # Get user profile
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    # Check if user is a student
    if not user_profile.is_student():
        messages.error(request, "Only students can view their attendance history.")
        return redirect('main:mainpage')
    
    # Get all attendance records for the student
    all_records = Attendance.objects.filter(
        user=request.user,
        status='checked_out'  # Only show completed visits
    ).prefetch_related('activities').order_by('-check_in_time')
    
    # Filter by month and year if provided
    month = request.GET.get('month')
    year = request.GET.get('year')
    
    if month and year:
        filtered_records = all_records.filter(
            check_in_time__month=int(month),
            check_in_time__year=int(year)
        )
    else:
        # Default to current month
        today = timezone.now()
        filtered_records = all_records.filter(
            check_in_time__month=today.month,
            check_in_time__year=today.year
        )
    
    # Calculate statistics
    total_visits = all_records.count()
    total_duration = all_records.aggregate(total=Avg('duration_minutes'))['total'] or 0
    
    month_visits = filtered_records.count()
    month_duration = filtered_records.aggregate(total=Avg('duration_minutes'))['total'] or 0
    
    # Get top activities
    activity_counts = {}
    for record in all_records:
        for activity in record.activities.all():
            activity_counts[activity.name] = activity_counts.get(activity.name, 0) + 1
    
    top_activities = sorted(
        activity_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:5]
    
    context = {
        'user_profile': user_profile,
        'records': filtered_records,
        'total_visits': total_visits,
        'total_duration': int(total_duration),
        'month_visits': month_visits,
        'month_duration': int(month_duration),
        'top_activities': top_activities,
        'selected_month': int(month) if month else timezone.now().month,
        'selected_year': int(year) if year else timezone.now().year,
        'current_month': timezone.now().month,
        'current_year': timezone.now().year,
    }
    
    return render(request, 'history.html', context)


@login_required
def report_view(request):
    """Attendance report page for teachers and librarians"""
    # Get user profile
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    # Check access - only teachers and librarians
    if not (user_profile.is_teacher() or user_profile.is_librarian()):
        messages.error(request, "Only teachers and librarians can view attendance reports.")
        return redirect('main:mainpage')
    
    context = {
        'user_profile': user_profile,
    }
    
    return render(request, 'report.html', context)


def get_reading_stats(user):
    """
    Placeholder for reading statistics
    This will be populated when reading tracker feature is implemented
    """
    # For now, return empty stats
    return {
        'books_read_this_month': 0,
        'reading_minutes_this_week': 0,
        'reading_streak': 0,
        'next_milestone': 5,  # Next goal: 5 books
        'message': 'Ready to read today?'
    }


# ─── API ENDPOINTS ───────────────────────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def api_checkin(request):
    """
    API endpoint for checking in students and teachers to the library
    POST /attendance/api/checkin
    
    Required fields in request body (JSON or form data):
    - activities: list of activity IDs (optional)
    - custom_activity: custom activity text (optional)
    """
    try:
        # Get user profile
        try:
            user_profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'User profile not found. Please contact administrator.'
            }, status=400)
        
        # Check if user is a student or teacher
        if not (user_profile.is_student() or user_profile.is_teacher()):
            return JsonResponse({
                'status': 'error',
                'message': 'Only students and teachers can check in to the library.'
            }, status=403)
        
        # Check if already checked in today
        today = timezone.now().date()
        active_attendance = Attendance.objects.filter(
            user=request.user,
            check_in_time__date=today,
            status='checked_in'
        ).first()
        
        if active_attendance:
            return JsonResponse({
                'status': 'error',
                'message': 'You are already checked in. Please check out first.',
                'check_in_time': active_attendance.check_in_time.isoformat()
            }, status=400)
        
        # Parse request data
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = request.POST.dict()
        
        # Create attendance record with explicit datetime
        check_in_datetime = timezone.now()
        
        attendance = Attendance.objects.create(
            user=request.user,
            status='checked_in',
            custom_activity=data.get('custom_activity', '').strip(),
            check_in_time=check_in_datetime
        )
        
        # Add selected activities
        activity_ids = data.get('activities', [])
        if activity_ids:
            if isinstance(activity_ids, str):
                activity_ids = [int(x.strip()) for x in activity_ids.split(',') if x.strip().isdigit()]
            elif isinstance(activity_ids, list):
                activity_ids = [int(x) if isinstance(x, (int, float)) else int(x) for x in activity_ids if x]
            
            if activity_ids:
                activities = AttendanceActivity.objects.filter(id__in=activity_ids, is_active=True)
                attendance.activities.set(activities)
        
        # Convert to Jakarta timezone for display
        check_in_local = timezone.localtime(attendance.check_in_time)
        formatted_time = check_in_local.strftime('%H:%M')
        
        return JsonResponse({
            'status': 'success',
            'message': f'✨ Welcome! You checked in at {formatted_time}',
            'record_id': attendance.id,
            'check_in_time': attendance.check_in_time.isoformat(),
            'check_in_time_formatted': formatted_time,
            'user': request.user.first_name
        }, status=201)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_checkout(request):
    """
    API endpoint for checking out students and teachers from the library
    POST /api/attendance/checkout
    """
    try:
        # Get user profile
        try:
            user_profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'User profile not found. Please contact administrator.'
            }, status=400)
        
        # Check if user is a student or teacher
        if not (user_profile.is_student() or user_profile.is_teacher()):
            return JsonResponse({
                'status': 'error',
                'message': 'Only students and teachers can check out from the library.'
            }, status=403)
        
        # Find active check-in
        today = timezone.now().date()
        active_attendance = Attendance.objects.filter(
            user=request.user,
            check_in_time__date=today,
            status='checked_in'
        ).first()
        
        if not active_attendance:
            return JsonResponse({
                'status': 'error',
                'message': 'No active check-in found. Please check in first.',
                'error_code': 'NO_ACTIVE_CHECKIN'
            }, status=400)
        
        # Record check-out time and calculate duration
        check_out_datetime = timezone.now()
        active_attendance.check_out_time = check_out_datetime
        active_attendance.status = 'checked_out'
        active_attendance.save()  # Duration is calculated automatically in save()
        
        # Convert to Jakarta timezone for display
        check_in_local = timezone.localtime(active_attendance.check_in_time)
        check_out_local = timezone.localtime(active_attendance.check_out_time)
        
        return JsonResponse({
            'status': 'success',
            'message': f'Thank you for visiting! See you soon! 📚',
            'record_id': active_attendance.id,
            'check_in_time': active_attendance.check_in_time.isoformat(),
            'check_in_time_formatted': check_in_local.strftime('%H:%M'),
            'check_out_time': active_attendance.check_out_time.isoformat(),
            'check_out_time_formatted': check_out_local.strftime('%H:%M'),
            'duration_minutes': active_attendance.duration_minutes,
            'duration_display': active_attendance.duration_display,
        }, status=200)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def api_report(request):
    """
    API endpoint for attendance reports
    POST /api/attendance/report
    
    Query parameters:
    - period: 'daily' or 'monthly' (required)
    - month: month number (1-12) for monthly reports
    - year: year number for monthly reports
    """
    try:
        # Get user profile
        try:
            user_profile = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'User profile not found. Please contact administrator.'
            }, status=400)
        
        # Only teachers and librarians can generate reports
        if not (user_profile.is_teacher() or user_profile.is_librarian()):
            return JsonResponse({
                'status': 'error',
                'message': 'Only teachers and librarians can generate reports.'
            }, status=403)
        
        # Parse request data
        try:
            data = json.loads(request.body) if request.body else request.POST.dict()
        except json.JSONDecodeError:
            data = request.POST.dict()
        
        period = data.get('period', 'daily').lower()
        
        if period not in ['daily', 'monthly']:
            return JsonResponse({
                'status': 'error',
                'message': "Period must be 'daily' or 'monthly'."
            }, status=400)
        
        # Build query for completed visits only
        base_query = Attendance.objects.filter(
            status__in=['checked_out', 'auto_checked_out']
        ).prefetch_related('user', 'activities')
        
        if period == 'daily':
            # Daily report - today only
            today = timezone.now().date()
            records = base_query.filter(check_in_time__date=today)
            period_label = today.strftime('%Y-%m-%d')
        else:  # monthly
            # Monthly report
            month = int(data.get('month', timezone.now().month))
            year = int(data.get('year', timezone.now().year))
            
            records = base_query.filter(
                check_in_time__month=month,
                check_in_time__year=year
            )
            period_label = f"{year}-{month:02d}"
        
        # Calculate statistics
        total_visits = records.count()
        unique_visitors = records.values('user').distinct().count()
        
        # Calculate average duration (excluding None values)
        avg_duration = records.aggregate(avg=Avg('duration_minutes'))['avg'] or 0
        
        # Get daily breakdown for monthly reports
        daily_data = {}
        if period == 'monthly':
            daily_records = records.values('check_in_time__date').annotate(
                count=Count('id'),
                avg_duration=Avg('duration_minutes')
            ).order_by('check_in_time__date')
            
            daily_data = {
                str(item['check_in_time__date']): {
                    'visits': item['count'],
                    'avg_duration': int(item['avg_duration']) if item['avg_duration'] else 0
                }
                for item in daily_records
            }
        
        # Get top activities
        activity_data = {}
        for record in records:
            for activity in record.activities.all():
                if activity.name not in activity_data:
                    activity_data[activity.name] = {'emoji': activity.emoji, 'count': 0}
                activity_data[activity.name]['count'] += 1
        
        top_activities = sorted(
            activity_data.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:10]
        
        # Get top students
        student_visits = records.values('user__first_name', 'user__last_name').annotate(
            visit_count=Count('id'),
            total_duration=Avg('duration_minutes')
        ).order_by('-visit_count')[:10]
        
        return JsonResponse({
            'status': 'success',
            'period': period,
            'period_label': period_label,
            'summary': {
                'total_visits': total_visits,
                'unique_visitors': unique_visitors,
                'avg_duration_minutes': int(avg_duration),
                'avg_duration_display': f"{int(avg_duration // 60)}h {int(avg_duration % 60)}m" if avg_duration >= 60 else f"{int(avg_duration)}m"
            },
            'daily_breakdown': daily_data if period == 'monthly' else None,
            'top_activities': [
                {
                    'name': name,
                    'emoji': data['emoji'],
                    'count': data['count']
                }
                for name, data in top_activities
            ],
            'top_students': [
                {
                    'name': f"{item['user__first_name']} {item['user__last_name']}",
                    'visits': item['visit_count'],
                    'avg_duration': int(item['total_duration']) if item['total_duration'] else 0
                }
                for item in student_visits
            ]
        }, status=200)
        
    except ValueError as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Invalid parameter: {str(e)}'
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)
