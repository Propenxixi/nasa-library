from django.core.management.base import BaseCommand
from django.db import transaction

from book.models import Book
from book.services import enrich_book_from_isbn


class Command(BaseCommand):
    help = 'Fetch categories from API for all books that do not have category'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Simulate without saving to database',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of books to process',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        # Get books without category (null or empty)
        books_without_cat = Book.objects.filter(
            category__isnull=True
        ) | Book.objects.filter(category='')
        
        # Remove duplicates and apply limit
        books_without_cat = books_without_cat.distinct()
        if limit:
            books_without_cat = books_without_cat[:limit]
        
        total_to_process = books_without_cat.count()
        
        self.stdout.write(self.style.WARNING(
            f'\n⚠️  {"(DRY RUN) " if dry_run else ""}Found {total_to_process} books without category'
        ))
        
        if not total_to_process:
            self.stdout.write(self.style.SUCCESS('\n✅ All books already have categories!'))
            return

        success_count = 0
        failed_count = 0
        skipped_count = 0

        for book in books_without_cat:
            if not book.isbn:
                self.stdout.write(f'  ⏭️  Skipping "{book.title[:40]}" - no ISBN')
                skipped_count += 1
                continue

            self.stdout.write(f'  🔄 Fetching category for: {book.title[:40]} (ISBN: {book.isbn})')
            
            try:
                enriched = enrich_book_from_isbn(book.isbn)
                category = enriched.get('category')
                
                if category:
                    if not dry_run:
                        book.category = category
                        # Also save other enriched fields if empty
                        if not book.cover_url and enriched.get('cover_url'):
                            book.cover_url = enriched['cover_url']
                        if not book.publisher and enriched.get('publisher'):
                            book.publisher = enriched['publisher']
                        if not book.publish_year and enriched.get('publish_year'):
                            book.publish_year = enriched['publish_year']
                        if not book.synopsis and enriched.get('synopsis'):
                            book.synopsis = enriched['synopsis']
                        book.save()
                    
                    self.stdout.write(self.style.SUCCESS(f'     ✅ Category: {category}'))
                    success_count += 1
                else:
                    self.stdout.write(self.style.WARNING(f'     ⚠️  No category found from API'))
                    failed_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'     ❌ Error: {str(e)}'))
                failed_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ {"(dry run) " if dry_run else ""}Completed!'
        ))
        self.stdout.write(f'   - Success: {success_count}')
        self.stdout.write(f'   - Failed/No category: {failed_count}')
        self.stdout.write(f'   - Skipped (no ISBN): {skipped_count}')
