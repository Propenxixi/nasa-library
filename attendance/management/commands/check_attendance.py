from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.models import Attendance


class Command(BaseCommand):
    help = 'Check current attendance records'

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Get all records for today
        records = Attendance.objects.filter(
            check_in_time__date=today
        ).order_by('-check_in_time')
        
        self.stdout.write(f'\n📊 Attendance Records for {today}')
        self.stdout.write('=' * 60)
        
        if not records.exists():
            self.stdout.write(self.style.WARNING('❌ No attendance records found for today'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Found {records.count()} records\n'))
            
            for record in records:
                self.stdout.write(
                    f'  {record.user.first_name} {record.user.last_name}'
                    f' | Status: {record.status}'
                    f' | Time: {record.check_in_time.strftime("%H:%M")}'
                )
        
        # Check total records in database
        total = Attendance.objects.count()
        self.stdout.write(f'\nTotal records in database: {total}')
