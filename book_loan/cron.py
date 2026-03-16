"""
Cron jobs for book_loan module
"""
from django.utils import timezone
from datetime import timedelta
from .models import Loan, Notification


def send_due_reminders():
    """
    Send reminder notifications for loans due tomorrow (H+1)
    Runs daily at 7:00 AM
    
    Requirements:
    - Identify transactions with status "Sedang Dipinjam" where due date is tomorrow
    - Create notification with type REMINDER_DUE  
    - Check for duplicates in last 24 hours to prevent duplicate reminders
    - Save to notifications table with: user_id, loan_id, type, message, status
    """
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    # Find all loans due tomorrow with status "sedang_dipinjam"
    due_tomorrow = Loan.objects.filter(
        status='sedang_dipinjam',
        due_date=tomorrow
    ).select_related('user', 'book')
    
    for loan in due_tomorrow:
        # Check if reminder already sent in last 24 hours (24 jam terakhir)
        last_24_hours = timezone.now() - timedelta(hours=24)
        
        existing_reminder = Notification.objects.filter(
            user=loan.user,
            loan=loan,
            notification_type='reminder_due',
            created_at__gte=last_24_hours
        ).exists()
        
        if not existing_reminder:
            # Create reminder notification
            message = f"Reminder: Buku {loan.book.title} harus dikembalikan besok, {loan.due_date.strftime('%d %b %Y')}. Segera kembalikan atau ajukan perpanjangan."
            
            Notification.objects.create(
                user=loan.user,
                notification_type='reminder_due',
                title=f'Reminder: {loan.book.title}',
                message=message,
                loan=loan,
                book=loan.book,
                is_read=False
            )


def handle_overdue_loans():
    """
    Mark loans as overdue if due date has passed
    """
    today = timezone.now().date()
    
    overdue_loans = Loan.objects.filter(
        status='sedang_dipinjam',
        due_date__lt=today,
        is_overdue=False
    )
    
    overdue_loans.update(
        status='terlambat',
        is_overdue=True
    )
