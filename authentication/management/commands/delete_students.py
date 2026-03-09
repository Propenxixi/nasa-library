from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from authentication.models import UserProfile
from django.db import transaction


class Command(BaseCommand):
    help = 'Delete all students from database (keep staff/librarians)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show how many students would be deleted without actually deleting',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Skip confirmation prompt',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            default=False,
            help='Delete all users including staff/librarians',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        delete_all = options['all']

        # Query students only (not staff/teachers/librarians)
        if delete_all:
            students = UserProfile.objects.all().select_related('user')
            label = 'users'
        else:
            students = UserProfile.objects.filter(role='student').select_related('user')
            label = 'students'

        student_count = students.count()

        self.stdout.write(self.style.WARNING(
            f'\n⚠️  Found {student_count} {label} in database'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'🟡 DRY RUN: Would delete {student_count} {label}'
            ))
            return

        if not force:
            confirm = input(f'❓ Are you sure you want to DELETE all {label}? Type "yes" to confirm: ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('❌ Cancelled.'))
                return

        try:
            with transaction.atomic():
                # Get user IDs to delete
                user_ids = students.values_list('user_id', flat=True)
                deleted_count = User.objects.filter(id__in=user_ids).delete()[0]

            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Successfully deleted {deleted_count} {label}'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Error deleting {label}: {str(e)}'
            ))
            raise
