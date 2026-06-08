# from django.apps import AppConfig
#
#
# class AttendanceConfig(AppConfig):
#     name = 'attendance'
#
#     def ready(self):
#         """Initialize attendance activities on app ready."""
#         from attendance.models import AttendanceActivity
#
#         activities_data = [
#             {'name': 'Reading Books', 'emoji': '📚', 'description': 'Reading books in the library'},
#             {'name': 'Doing Homework', 'emoji': '📝', 'description': 'Studying or completing school assignments'},
#             {'name': 'Borrowing Books', 'emoji': '🤝', 'description': 'Borrowing books to take home'},
#             {'name': 'Research', 'emoji': '🔍', 'description': 'Researching for projects or assignments'},
#             {'name': 'Group Study', 'emoji': '👥', 'description': 'Studying with classmates'},
#             {'name': 'Reading Magazines', 'emoji': '📰', 'description': 'Reading magazines or newspapers'},
#             {'name': 'Computer Work', 'emoji': '💻', 'description': 'Using library computers'},
#             {'name': 'Quiet Time', 'emoji': '🤫', 'description': 'Taking a break in a quiet environment'},
#         ]
#
#         for i, activity_data in enumerate(activities_data, 1):
#             AttendanceActivity.objects.get_or_create(
#                 name=activity_data['name'],
#                 defaults={
#                     'emoji': activity_data['emoji'],
#                     'description': activity_data['description'],
#                     'order': i,
#                     'is_active': True,
#                 }
#             )
