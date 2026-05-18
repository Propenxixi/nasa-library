from django.shortcuts import render
from django.utils import timezone
from literacy.models import LiteracyLeaderboard
from book_loan.models import Loan
from django.db.models import Count

def show_mainpage(request):
    now = timezone.now()
    month = now.month
    year = now.year
    
    # 1. Fetch Top Readers (Global School Rank)
    leaderboard_qs = LiteracyLeaderboard.objects.filter(
        month=month, year=year
    ).select_related('student__profile').order_by('-total_score', 'first_activity_at', 'student__first_name')
    
    all_entries = list(leaderboard_qs)
    # Only include those with score > 0
    participating_entries = [e for e in all_entries if e.total_score > 0]
    
    top_readers_data = []
    for entry in participating_entries[:6]:
        profile_url = None
        if hasattr(entry.student, 'profile') and entry.student.profile.profile_picture:
            profile_url = entry.student.profile.profile_picture.url
            
        top_readers_data.append({
            'first_name': entry.student.first_name,
            'last_name': entry.student.last_name,
            'points': entry.total_score,
            'profile_picture_url': profile_url,
        })
        
    context = {
        'top_readers': top_readers_data[:3],
        'next_readers': top_readers_data[3:6],
    }
    
    # 2. Fetch User Statistics (if logged in)
    if request.user.is_authenticated:
        user_rank = None
        for idx, entry in enumerate(participating_entries, 1):
            if entry.student == request.user:
                user_rank = idx
                break
                
        user_entry = next((e for e in participating_entries if e.student == request.user), None)
        
        context.update({
            'user_rank': user_rank,
            'total_students': len(participating_entries),
            'books_read_this_month': user_entry.books_read if user_entry else 0,
            'active_loans': Loan.objects.filter(user=request.user, return_date__isnull=True).exclude(status='ditolak').count(),
        })
        
    return render(request, 'mainpage.html', context)
