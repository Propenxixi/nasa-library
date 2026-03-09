from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from authentication.models import UserProfile


class Command(BaseCommand):
    help = 'Check all user roles'

    def handle(self, *args, **options):
        self.stdout.write('\n👥 All Users and Roles:')
        self.stdout.write('=' * 70)
        
        users = User.objects.all()
        
        if not users.exists():
            self.stdout.write(self.style.WARNING('No users found'))
            return
        
        for user in users:
            try:
                profile = UserProfile.objects.get(user=user)
                role = profile.get_role_display()
                self.stdout.write(
                    f'  {user.username:20} | {user.first_name:15} {user.last_name:15} | Role: {role}'
                )
            except UserProfile.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'  {user.username:20} | NO PROFILE!')
                )
        
        self.stdout.write(f'\nTotal users: {users.count()}')
        
        # Check which users can access dashboard
        self.stdout.write('\n📊 Users who can access dashboard (teacher/librarian):')
        self.stdout.write('-' * 70)
        
        dashboard_users = []
        for user in users:
            try:
                profile = UserProfile.objects.get(user=user)
                if profile.is_teacher() or profile.is_librarian():
                    dashboard_users.append(user)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {user.username} ({profile.get_role_display()})'))
            except UserProfile.DoesNotExist:
                pass
        
        if not dashboard_users:
            self.stdout.write(self.style.WARNING('  ❌ No teacher/librarian users found!'))
