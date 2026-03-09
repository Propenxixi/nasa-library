import re
from django.core.management.base import BaseCommand

JUNK_RE = re.compile(r'nyt:|bestseller.*\d{4}|=\d{4}', re.IGNORECASE)


class Command(BaseCommand):
    help = 'Reset kategori buku yang masih berisi data mentah dari API'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, *args, **options):
        from book.models import Book

        dirty = Book.objects.exclude(category__isnull=True).exclude(category='')
        count = 0

        for book in dirty:
            if JUNK_RE.search(book.category or ''):
                self.stdout.write(f'  🧹 Reset: {book.title[:50]}')
                self.stdout.write(f'     was: {book.category[:80]}')
                if not options['dry_run']:
                    # Reset semua enriched fields supaya di-fetch ulang
                    book.category     = None
                    book.publisher    = None
                    book.publish_year = None
                    book.synopsis     = None
                    book.save(update_fields=['category', 'publisher', 'publish_year', 'synopsis'])
                count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ {"(dry run) " if options["dry_run"] else ""}Reset {count} buku'
        ))