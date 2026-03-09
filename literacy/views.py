from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import BookReview, LiteracyPost, LiteracyComment, LiteracyLeaderboard, LiteracyAchievement
from .forms import BookReviewForm, LiteracyPostForm, CommentForm, ReviewVerificationForm
from authentication.models import UserProfile


@login_required
def submit_review_view(request):
    """Student submits a book review"""
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        # Create a default profile for user if doesn't exist
        user_profile = UserProfile.objects.create(user=request.user, role='student')
    
    if not user_profile.is_student():
        messages.error(request, "Only students can submit book reviews.")
        return redirect('literacy:leaderboard')
    
    if request.method == 'POST':
        form = BookReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.student = request.user
            review.save()
            
            messages.success(
                request,
                f"✨ Great job! Your review of '{review.title}' is pending teacher verification."
            )
            return redirect('literacy:my_reviews')
    else:
        form = BookReviewForm()
    
    # Get user stats for gamification
    stats = {
        'reviews_count': BookReview.objects.filter(student=request.user).count(),
        'verified_count': BookReview.objects.filter(
            student=request.user,
            status='verified'
        ).count(),
    }
    
    context = {
        'form': form,
        'user_profile': user_profile,
        'stats': stats,
    }
    
    return render(request, 'submit-review.html', context)


@login_required
def my_reviews_view(request):
    """Student views their review history"""
    try:
        user_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        # Create a default profile for user if doesn't exist
        user_profile = UserProfile.objects.create(user=request.user, role='student')
    
    if not user_profile.is_student():
        return redirect('literacy:leaderboard')
    
    # Get all reviews - use distinct to avoid duplicates
    reviews = BookReview.objects.filter(student=request.user).distinct()
    
    # Filter by status if requested
    status_filter = request.GET.get('status')
    if status_filter in ['pending', 'verified', 'rejected']:
        reviews = reviews.filter(status=status_filter)
    
    # Get all reviews count before filtering for stats
    all_reviews_count = BookReview.objects.filter(student=request.user).count()
    
    # Stats
    stats = {
        'total_reviews': all_reviews_count,
        'pending_reviews': BookReview.objects.filter(student=request.user, status='pending').count(),
        'verified_reviews': BookReview.objects.filter(student=request.user, status='verified').count(),
        'rejected_reviews': BookReview.objects.filter(student=request.user, status='rejected').count(),
    }
    
    context = {
        'reviews': reviews,
        'stats': stats,
        'current_filter': status_filter,
    }
    
    return render(request, 'my-reviews.html', context)


@login_required
def review_detail_view(request, pk):
    """View details of a single review"""
    review = get_object_or_404(BookReview, pk=pk)
    
    # Check permission
    if review.student != request.user:
        return HttpResponseForbidden("You cannot view this review.")
    
    context = {
        'review': review,
    }
    
    return render(request, 'review-detail.html', context)


@login_required
def leaderboard_view(request):
    """Display leaderboard with different scopes"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    # Get scope from request
    scope = request.GET.get('scope', 'school')  # school, class, or grade
    
    # Get leaderboard data
    if scope == 'class' and user_profile.kelas:
        leaderboard = LiteracyLeaderboard.objects.filter(
            scope_value=user_profile.kelas
        ).order_by('-total_score')[:100]
    elif scope == 'grade':
        grade = user_profile.kelas.split()[0] if user_profile.kelas else 'X'
        leaderboard = LiteracyLeaderboard.objects.filter(
            scope_value=grade
        ).order_by('-total_score')[:100]
    else:  # school-wide
        leaderboard = LiteracyLeaderboard.objects.filter(
            scope_value='school'
        ).order_by('-total_score')[:100]
    
    # Add rank
    for idx, entry in enumerate(leaderboard, 1):
        entry.rank = idx
    
    # Get current user's rank
    user_rank = None
    if user_profile.is_student():
        try:
            user_entry = next(
                (e for e in leaderboard if e.student_id == request.user.id),
                None
            )
            if user_entry:
                user_rank = user_entry.rank
        except:
            pass
    
    # Get user's stats
    user_stats = {
        'books_read': BookReview.objects.filter(student=request.user, status='verified').count(),
        'pending_reviews': BookReview.objects.filter(student=request.user, status='pending').count(),
        'total_reviews': BookReview.objects.filter(student=request.user).count(),
    }
    
    # Get monthly ambassador
    ambassadors = LiteracyLeaderboard.objects.filter(
        is_monthly_ambassador=True
    ).order_by('scope_value')
    
    context = {
        'leaderboard': leaderboard,
        'scope': scope,
        'user_rank': user_rank,
        'user_stats': user_stats,
        'user_profile': user_profile,
        'ambassadors': ambassadors,
    }
    
    return render(request, 'leaderboard.html', context)


@login_required
def teacher_verify_reviews_view(request):
    """Teacher dashboard for verifying book reviews"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    if not user_profile.is_teacher():
        messages.error(request, "Only teachers can verify reviews.")
        return redirect('literacy:leaderboard')
    
    # Get pending reviews from teacher's class
    pending_reviews = BookReview.objects.filter(
        status='pending',
        student__profile__kelas=user_profile.kelas
    ).order_by('-created_at')
    
    # Stats
    stats = {
        'pending_count': pending_reviews.count(),
        'verified_today': BookReview.objects.filter(
            status='verified',
            verified_by=request.user,
            verified_at__gte=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count(),
        'total_verified': BookReview.objects.filter(
            status='verified',
            verified_by=request.user
        ).count(),
    }
    
    context = {
        'pending_reviews': pending_reviews,
        'stats': stats,
        'user_profile': user_profile,
    }
    
    return render(request, 'teacher-verify-reviews.html', context)


@login_required
def verify_review_view(request, pk):
    """Verify or reject a single review"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    if not user_profile.is_teacher():
        return HttpResponseForbidden("Only teachers can verify reviews.")
    
    review = get_object_or_404(BookReview, pk=pk, status='pending')
    
    # Check if teacher has permission
    if review.student.profile.kelas != user_profile.kelas:
        return HttpResponseForbidden("You can only verify reviews from your own class.")
    
    if request.method == 'POST':
        form = ReviewVerificationForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            
            if action == 'verify':
                review.verify(request.user)
                messages.success(request, f"✅ Review of '{review.title}' has been verified!")
            else:
                reason = form.cleaned_data.get('rejection_reason', 'No reason provided')
                review.reject(request.user, reason)
                messages.info(request, f"❌ Review of '{review.title}' has been rejected.")
            
            return redirect('literacy:teacher_verify_reviews')
    else:
        form = ReviewVerificationForm()
    
    context = {
        'review': review,
        'form': form,
    }
    
    return render(request, 'verify-review.html', context)


@login_required
def forum_view(request):
    """Forum listing - all literacy posts"""
    posts = LiteracyPost.objects.all().prefetch_related('comments', 'likes')
    
    # Filter by search if provided
    search_query = request.GET.get('q')
    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query)
        )
    
    # Pagination / sorting
    sort_by = request.GET.get('sort', 'recent')
    if sort_by == 'popular':
        posts = posts.annotate(like_count=Count('likes')).order_by('-like_count', '-created_at')
    else:
        posts = posts.order_by('-created_at')
    
    # Add engagement data for each post
    for post in posts:
        post.like_count = post.likes.count()
        post.comment_count = post.comments.count()
        post.user_liked = request.user in post.likes.all() if request.user.is_authenticated else False
    
    context = {
        'posts': posts,
        'search_query': search_query or '',
        'sort_by': sort_by,
    }
    
    return render(request, 'forum.html', context)


@login_required
def create_post_view(request):
    """Create a new literacy post"""
    if request.method == 'POST':
        form = LiteracyPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.student = request.user
            post.save()
            
            messages.success(request, "✨ Your post has been published! Keep inspiring others!")
            return redirect('literacy:post_detail', pk=post.pk)
    else:
        form = LiteracyPostForm()
        # Filter to user's verified reviews only
        form.fields['book_review'].queryset = BookReview.objects.filter(
            student=request.user,
            status='verified'
        )
    
    context = {
        'form': form,
    }
    
    return render(request, 'create-post.html', context)


@login_required
def post_detail_view(request, pk):
    """View detailed post with comments"""
    post = get_object_or_404(LiteracyPost, pk=pk)
    post.like_count = post.likes.count()
    post.user_liked = request.user in post.likes.all()
    
    if request.method == 'POST':
        if 'comment' in request.POST:
            form = CommentForm(request.POST)
            if form.is_valid():
                comment = form.save(commit=False)
                comment.post = post
                comment.student = request.user
                comment.save()
                messages.success(request, "Comment added!")
                return redirect('literacy:post_detail', pk=pk)
        elif 'like' in request.POST:
            if request.user in post.likes.all():
                post.likes.remove(request.user)
            else:
                post.likes.add(request.user)
            return redirect('literacy:post_detail', pk=pk)
    else:
        form = CommentForm()
    
    comments = post.comments.all()
    
    context = {
        'post': post,
        'form': form,
        'comments': comments,
    }
    
    return render(request, 'post-detail.html', context)


@login_required
def delete_post_view(request, pk):
    """Delete a post (owner only)"""
    post = get_object_or_404(LiteracyPost, pk=pk)
    
    if post.student != request.user:
        return HttpResponseForbidden("You can only delete your own posts.")
    
    if request.method == 'POST':
        post.delete()
        messages.success(request, "Post deleted successfully.")
        return redirect('literacy:forum')
    
    context = {
        'post': post,
    }
    
    return render(request, 'delete-post.html', context)


def calculate_leaderboard_scores():
    """Calculate and update leaderboard scores - run periodically"""
    from authentication.models import UserProfile
    
    # Get all students
    students = UserProfile.objects.filter(role='student')
    
    for student_profile in students:
        student = student_profile.user
        
        # Count verified reviews
        verified_count = BookReview.objects.filter(
            student=student,
            status='verified'
        ).count()
        
        # Calculate consistency score
        last_month = timezone.now() - timedelta(days=30)
        reviews_last_month = BookReview.objects.filter(
            student=student,
            created_at__gte=last_month
        ).count()
        consistency_score = min(reviews_last_month * 10, 100)  # Max 100
        
        # Total score calculation
        total_score = (
            verified_count * 20 +      # 20 points per verified review
            consistency_score          # Consistency points
        )
        
        # Update leaderboard for different scopes
        scopes = [
            ('class', student_profile.kelas),
            ('school', 'school'),
        ]
        
        for scope, scope_value in scopes:
            if scope == 'class' and not scope_value:
                continue
            
            LiteracyLeaderboard.objects.update_or_create(
                student=student,
                scope=scope,
                scope_value=scope_value,
                defaults={
                    'books_read': verified_count,
                    'verified_reviews': verified_count,
                    'consistency_score': consistency_score,
                    'total_score': total_score,
                }
            )


def get_reading_stats(user):
    """Get reading stats for gamification"""
    return {
        'reviews_count': BookReview.objects.filter(student=user).count(),
        'verified_count': BookReview.objects.filter(student=user, status='verified').count(),
        'pending_count': BookReview.objects.filter(student=user, status='pending').count(),
    }
