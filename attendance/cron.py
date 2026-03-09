"""
Cron jobs for attendance system
Handles scheduled tasks like auto check-out at library closing time
"""
from django.utils import timezone
from datetime import timedelta
from .models import Attendance


def auto_checkout_at_closing():
    """
    Automatically check out all students at 3:00 PM (library closing time)
    This function is called by django-crontab every day at 15:00 (3:00 PM)
    """
    try:
        # Get all active attendance records (students still checked in)
        active_records = Attendance.objects.filter(
            status='checked_in',
            check_in_time__date=timezone.now().date()
        )
        
        # Count before update
        count = active_records.count()
        
        if count > 0:
            now = timezone.now()
            
            # Update all active records with check-out time
            for record in active_records:
                record.check_out_time = now
                record.status = 'checked_out'
                record.save()
            
            # Log the action
            print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Auto check-out completed: {count} students checked out")
            with open('/tmp/attendance_cron.log', 'a') as log_file:
                log_file.write(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Auto check-out: {count} students\n")
        else:
            print(f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] No active students to check out")
            
    except Exception as e:
        error_msg = f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] Error during auto check-out: {str(e)}\n"
        print(error_msg)
        with open('/tmp/attendance_cron.log', 'a') as log_file:
            log_file.write(error_msg)
