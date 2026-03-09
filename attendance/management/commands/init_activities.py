from django.core.management.base import BaseCommand
from attendance.models import AttendanceActivity


class Command(BaseCommand):
    help = 'Initialize default attendance activities'

    def handle(self, *args, **options):
        activities_data = [
            {'name': 'Reading Books', 'emoji': '📚', 'description': 'Reading books in the library'},
            {'name': 'Doing Homework', 'emoji': '📝', 'description': 'Studying or completing school assignments'},
            {'name': 'Borrowing Books', 'emoji': '🤝', 'description': 'Borrowing books to take home'},
            {'name': 'Research', 'emoji': '🔍', 'description': 'Researching for projects or assignments'},
            {'name': 'Group Study', 'emoji': '👥', 'description': 'Studying with classmates'},
            {'name': 'Reading Magazines', 'emoji': '📰', 'description': 'Reading magazines or newspapers'},
            {'name': 'Computer Work', 'emoji': '💻', 'description': 'Using library computers'},
            {'name': 'Quiet Time', 'emoji': '🤫', 'description': 'Taking a break in a quiet environment'},
        ]

        count = 0
        for i, activity_data in enumerate(activities_data, 1):
            activity, created = AttendanceActivity.objects.get_or_create(
                name=activity_data['name'],
                defaults={
                    'emoji': activity_data['emoji'],
                    'description': activity_data['description'],
                    'order': i,
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created: {activity.emoji} {activity.name}')
                )
                count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Already exists: {activity.emoji} {activity.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully initialized {count} new attendance activities!')
        )
