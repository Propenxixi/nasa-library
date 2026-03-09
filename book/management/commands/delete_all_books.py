from django.core.management.base import BaseCommand
from django.db import transaction

from book.models import Book


class Command(BaseCommand):
    help = 'Delete all books from database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show how many books would be deleted without actually deleting',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        # Count books first
        book_count = Book.objects.count()
        
        self.stdout.write(self.style.WARNING(
            f'\n⚠️  Found {book_count} books in database'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'🟡 DRY RUN: Would delete {book_count} books'
            ))
            return

        if not force:
            confirm = input('❓ Are you sure you want to DELETE all books? Type "yes" to confirm: ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('❌ Cancelled.'))
                return

        with transaction.atomic():
            deleted_count = Book.objects.all().delete()[0]

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Successfully deleted {deleted_count} books from database'
        ))
