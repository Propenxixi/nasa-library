from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from authentication.models import UserProfile


class Command(BaseCommand):
    help = 'Create or update superuser with librarian role'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='petugas61', help='Superuser username')
        parser.add_argument('--email', type=str, default='admin@nasa.com', help='Superuser email')
        parser.add_argument('--password', type=str, default='akunadmin123', help='Superuser password')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
            }
        )

        user.set_password(password)
        user.save()

        UserProfile.objects.update_or_create(
            user=user,
            defaults={'role': 'librarian'}
        )

        status = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f'✅ Superuser {username} {status} with librarian role'))
