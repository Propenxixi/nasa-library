import json
from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q

from .models import UserPreference
from book.models import Book
from book_loan.models import Loan as BookLoan


# Category mapping: Indonesian -> English (for matching user preferences with book categories)
CATEGORY_TRANSLATION = {
    # Indonesian: English
    'fiksi': ['fiction', 'novel', 'fictional'],
    'non-fiksi': ['non-fiction', 'nonfiction', 'reference'],
    'nonfiksi': ['non-fiction', 'nonfiction', 'reference'],
    'sains': ['science', 'sciences', 'scientific'],
    'sejarah': ['history', 'historical'],
    'matematika': ['mathematics', 'math', 'algebra', 'geometry', 'calculus'],
    'bahasa': ['language', 'languages', 'linguistics'],
    'seni': ['art', 'arts', 'design'],
    'teknologi': ['technology', 'tech', 'computers', 'computer science', 'programming'],
    'agama': ['religion', 'religious', 'spirituality', 'christianity', 'islam', 'buddhism'],
    'olah raga': ['sports', 'sport'],
    'olahraga': ['sports', 'sport'],
    'biografi': ['biography', 'biographies', 'memoir'],
    'puisi': ['poetry', 'poems'],
    'cerita anak': ['children', 'juvenile', 'kids', 'young adult'],
    'komik': ['comics', 'graphic novel', 'comic strips', 'manga'],
    'psikologi': ['psychology', 'psychological'],
    'ekonomi': ['economics', 'business', 'finance'],
    'politik': ['politics', 'political'],
    'geografi': ['geography', 'geographic'],
    'filosofi': ['philosophy', 'philosophical'],
    'kesehatan': ['health', 'medical', 'medicine', 'wellness'],
}


def _get_english_categories(indonesian_cat: str) -> list:
    """Convert Indonesian category to English equivalents for matching"""
    cat_lower = indonesian_cat.lower().strip()
    return CATEGORY_TRANSLATION.get(cat_lower, [cat_lower])


def _build_category_filter(categories: list) -> Q:
    """Build a comprehensive Q filter for category matching with flexible logic"""
    from django.db.models import Q
    
    category_filter = Q()
    
    for cat in categories:
        cat_lower = cat.lower().strip()
        
        # 1. Exact match (case-insensitive)
        category_filter |= Q(category__icontains=cat)
        category_filter |= Q(category__icontains=cat_lower)
        
        # 2. English equivalents from translation
        english_cats = _get_english_categories(cat)
        for eng_cat in english_cats:
            category_filter |= Q(category__icontains=eng_cat)
        
        # 3. Also match individual words from the category
        # Split by space and match each word
        cat_words = cat_lower.split()
        for word in cat_words:
            if len(word) > 2:  # Only words with 3+ characters
                category_filter |= Q(category__icontains=word)
    
    return category_filter


# Default book categories - will be dynamically loaded from database
DEFAULT_CATEGORIES = []


def get_default_categories():
    """Get default categories dynamically from database books"""
    # Consolidated Indonesian book categories - removing redundant categories
    # Categories are organized by main topics to avoid confusion
    return [
        # Fiksi & Non-Fiksi
        'Fiksi', 
        'Non-Fiksi', 
        'Novel',
        'Komik',
        
        # Sains & Teknologi
        'Sains', 
        'Teknologi', 
        'Matematika',
        
        # Sejarah & Geografi
        'Sejarah', 
        'Geografi',
        
        # Seni & Kreativitas
        'Seni', 
        'Bahasa',
        'Sastra',
        
        # Agama & Kepercayaan
        'Agama',
        'Filosofi',
        
        # Kesehatan & Kesejahteraan
        'Kesehatan', 
        'Olahraga',
        
        # Ekonomi & Bisnis
        'Ekonomi',
        
        # Pendidikan
        'Pendidikan', 
        'Pelajaran',
        
        # Biografi & Memoar
        'Biografi',
        
        # Psikologi & Pengembangan Diri
        'Psikologi', 
        'Motivasi',
        
        # Politik & Sosial
        'Politik',
        'Sosial',
        
        # Sastra
        'Puisi',
        
        # Buku Anak
        'Buku Anak',
    ]


# Category normalization mapping - maps variations to standardized names
CATEGORY_NORMALIZATION = {
    # Agama variations
    'agama & spiritualitas': 'Agama',
    'religion': 'Agama',
    'religion & spirituality': 'Agama',
    'religius': 'Agama',
    
    # Sejarah variations
    'sejarah & biografi': 'Sejarah',
    'history': 'Sejarah',
    'sejarah dan biografi': 'Sejarah',
    
    # Ekonomi variations
    'ekonomi & bisnis': 'Ekonomi',
    'economics': 'Ekonomi',
    'business': 'Ekonomi',
    'bisnis': 'Ekonomi',
    
    # Geografi variations
    'geografi & lingkungan': 'Geografi',
    'geography': 'Geografi',
    'lingkungan': 'Geografi',
    
    # Kesehatan variations
    'kesehatan & kesehatan': 'Kesehatan',
    'kesehatan & olah raga': 'Olahraga',
    'kesehatan & olahraga': 'Olahraga',
    'health': 'Kesehatan',
    
    # Olahraga variations
    'olah raga': 'Olahraga',
    'sports': 'Olahraga',
    
    # Sains variations
    'sains & teknologi': 'Sains',
    'science': 'Sains',
    'sains dan teknologi': 'Sains',
    
    # Teknologi variations
    'teknologi informasi': 'Teknologi',
    'technology': 'Teknologi',
    
    # Seni variations
    'seni & kreativitas': 'Seni',
    'art': 'Seni',
    'seni dan kreativitas': 'Seni',
    
    # Sastra variations
    'sastra & bahasa': 'Sastra',
    'sastra': 'Sastra',
    'literature': 'Sastra',
    
    # Bahasa variations
    'bahasa & linguistik': 'Bahasa',
    'language': 'Bahasa',
    'languages': 'Bahasa',
    
    # Pendidikan variations
    'pendidikan & akademik': 'Pendidikan',
    'pendidikan': 'Pendidikan',
    'education': 'Pendidikan',
    'akademik': 'Pendidikan',
    
    # Psikologi variations
    'psikologi & perkembangan': 'Psikologi',
    'psikologi': 'Psikologi',
    'psychology': 'Psikologi',
    
    # Motivasi variations
    'motivasi & pengembangan diri': 'Motivasi',
    'motivasi': 'Motivasi',
    'self-help': 'Motivasi',
    'pengembangan diri': 'Motivasi',
    
    # Politik variations
    'politik & pemerintahan': 'Politik',
    'politics': 'Politik',
    'government': 'Politik',
    
    # Sosial variations
    'sosial & budaya': 'Sosial',
    'sosial': 'Sosial',
    'social': 'Sosial',
    'budaya': 'Sosial',
    'culture': 'Sosial',
    
    # Biografi variations
    'biografi & memoar': 'Biografi',
    'biografi': 'Biografi',
    'biography': 'Biografi',
    'memoar': 'Biografi',
    'memoir': 'Biografi',
    
    # Fiksi variations
    'fiction': 'Fiksi',
    'fiktif': 'Fiksi',
    
    # Non-Fiksi variations
    'non-fiksi': 'Non-Fiksi',
    'nonfiksi': 'Non-Fiksi',
    'non-fiction': 'Non-Fiksi',
    'nonfiction': 'Non-Fiksi',
    
    # Cerita Anak / Buku Anak variations
    'cerita anak': 'Buku Anak',
    'children': 'Buku Anak',
    'buku anak-anak': 'Buku Anak',
    'buku anak': 'Buku Anak',
    'juvenile': 'Buku Anak',
    'kids': 'Buku Anak',
    'young adult': 'Buku Anak',
}


def _normalize_category(category: str) -> str:
    """Normalize a category name to its standard form"""
    cat_lower = category.lower().strip()
    
    # Check normalization mapping
    if cat_lower in CATEGORY_NORMALIZATION:
        return CATEGORY_NORMALIZATION[cat_lower]
    
    # Return original with proper capitalization
    return category.strip().title()


@login_required
@csrf_exempt
@require_GET
def get_categories(request):
    """Get all available book categories"""
    # Get unique categories from books in database
    book_categories = set()
    for cat in Book.objects.exclude(category__isnull=True).exclude(category='').values_list('category', flat=True).distinct():
        for c in str(cat).split(','):
            c = c.strip()
            if c:
                # Normalize the category
                normalized = _normalize_category(c)
                book_categories.add(normalized)
    
    # Get default categories (already normalized)
    default_cats = set(get_default_categories())
    
    # Combine and remove duplicates
    all_categories = sorted(list(default_cats | book_categories))
    
    return JsonResponse({'categories': all_categories})


@login_required
@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def preferences_view(request):
    """Handle preferences - GET to retrieve, POST to create, PUT to update"""
    
    if request.method == 'GET':
        return get_preferences(request)
    elif request.method == 'POST':
        return _save_preferences(request)
    elif request.method == 'PUT':
        return _update_preferences(request)


@login_required
@csrf_exempt
@require_GET
def check_preferences(request):
    """Check if user has set their preferences"""
    has_preferences = UserPreference.objects.filter(user=request.user).exists()
    return JsonResponse({'has_preferences': has_preferences})


def _save_preferences(request):
    """Save user reading preferences - POST /api/users/preferences"""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    categories = body.get('categories', [])
    
    # Validate categories
    if not categories:
        return JsonResponse({'error': 'Minimal pilih 1 kategori'}, status=400)
    
    if len(categories) > 5:
        return JsonResponse({'error': 'Maksimal 5 kategori yang dapat dipilih'}, status=400)
    
    # Validate that categories are strings
    if not all(isinstance(c, str) for c in categories):
        return JsonResponse({'error': 'Kategori harus berupa teks'}, status=400)
    
    # Save or update preferences
    preference, created = UserPreference.objects.get_or_create(
        user=request.user,
        defaults={'categories': categories}
    )
    
    if not created:
        preference.categories = categories
        preference.save()
    
    return JsonResponse({
        'message': 'Preferensi berhasil disimpan',
        'preferences': {
            'categories': preference.categories,
            'created_at': preference.created_at.isoformat() if preference.created_at else None,
            'updated_at': preference.updated_at.isoformat() if preference.updated_at else None,
        }
    }, status=201 if created else 200)


@login_required
@require_GET
def get_preferences(request):
    """Get user preferences - GET /api/users/preferences"""
    try:
        preference = UserPreference.objects.get(user=request.user)
        return JsonResponse({
            'categories': preference.categories,
            'created_at': preference.created_at.isoformat() if preference.created_at else None,
            'updated_at': preference.updated_at.isoformat() if preference.updated_at else None,
        })
    except UserPreference.DoesNotExist:
        return JsonResponse({
            'categories': [],
            'created_at': None,
            'updated_at': None,
        })


@login_required
def _update_preferences(request):
    """Update user preferences - PUT /api/users/preferences"""
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    categories = body.get('categories', [])
    
    # Validate categories
    if not categories:
        return JsonResponse({'error': 'Minimal pilih 1 kategori'}, status=400)
    
    if len(categories) > 5:
        return JsonResponse({'error': 'Maksimal 5 kategori yang dapat dipilih'}, status=400)
    
    # Validate that categories are strings
    if not all(isinstance(c, str) for c in categories):
        return JsonResponse({'error': 'Kategori harus berupa teks'}, status=400)
    
    try:
        preference = UserPreference.objects.get(user=request.user)
        preference.categories = categories
        preference.save()
    except UserPreference.DoesNotExist:
        preference = UserPreference.objects.create(user=request.user, categories=categories)
    
    return JsonResponse({
        'message': 'Preferensi berhasil diperbarui',
        'preferences': {
            'categories': preference.categories,
            'created_at': preference.created_at.isoformat() if preference.created_at else None,
            'updated_at': preference.updated_at.isoformat() if preference.updated_at else None,
        }
    })


@login_required
@csrf_exempt
@require_GET
def get_personalized_recommendations(request):
    """Get personalized book recommendations based on user preferences"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Get user preferences
    try:
        preference = UserPreference.objects.get(user=request.user)
        categories = preference.get_categories_list()
        logger.info(f"User {request.user.username} preferences: {categories}")
    except UserPreference.DoesNotExist:
        categories = []
        logger.info(f"User {request.user.username} has no preferences")
    
    # If no preferences, return popular books
    if not categories:
        logger.info("No categories in preferences, returning popular books")
        popular_books = get_popular_books_internal(limit=10)
        return JsonResponse({
            'recommendations': popular_books,
            'fallback': True,
            'message': 'Atur preferensi minat kamu untuk mendapatkan rekomendasi buku yang lebih personal!'
        })
    
    # Get books already borrowed by user (from book_loan system)
    borrowed_book_ids = BookLoan.objects.filter(
        user=request.user
    ).values_list('book_id', flat=True).distinct()
    
    # Base queryset - exclude borrowed books and inactive books
    books = Book.objects.exclude(
        id__in=borrowed_book_ids
    ).exclude(
        status='tidak_aktif'
    )
    
    # If user has preferences, filter by categories
    # Also include books with no category to ensure we have results
    if categories:
        # Use the comprehensive category filter
        category_filter = _build_category_filter(categories)
        
        # Also include books with no category (null or empty) so we have results
        category_filter |= Q(category__isnull=True) | Q(category='')
        
        logger.info(f"Filtering books with categories: {categories}")
        books = books.filter(category_filter)
        logger.info(f"Books after category filter: {books.count()}")
    
    # Annotate with review statistics and loan count from book_loan
    books = books.annotate(
        avg_rating=Avg('reviews__rating'),
        loan_count=Count('loans')
    ).order_by('-loan_count', '-avg_rating')
    
    # Get top 10
    books = books[:10]
    
    # Build response
    recommendations = []
    for book in books:
        # Calculate average rating from reviews
        reviews = book.reviews.all()
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
        
        # Get loan count from annotated data or calculate
        loan_count = book.loan_count if hasattr(book, 'loan_count') else BookLoan.objects.filter(book=book).count()
        
        recommendations.append({
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'category': book.category,
            'cover_url': book.cover_url,
            'avg_rating': round(avg_rating, 1) if avg_rating else None,
            'loan_count': loan_count,
            'available': book.available_copies > 0,
            'is_available': book.is_available,
        })
    
    logger.info(f"Returning {len(recommendations)} personalized recommendations")
    
    # If no personalized recommendations, return popular books
    if not recommendations:
        # Fallback to popular books
        popular_books = get_popular_books_internal(limit=10)
        return JsonResponse({
            'recommendations': popular_books,
            'fallback': True,
            'message': 'Belum ada rekomendasi untuk kategori pilihanmu. Coba pilih kategori lain!'
        })
    
    return JsonResponse({
        'recommendations': recommendations,
        'fallback': False,
    })


def get_popular_books_internal(limit=10, category=None):
    """Internal function to get popular books based on loan count in last 3 months"""
    three_months_ago = timezone.now() - timedelta(days=90)
    
    # Base queryset
    books = Book.objects.exclude(status='tidak_aktif')
    
    # Filter by category if provided
    if category:
        books = books.filter(category__icontains=category)
    
    # Count loans from book_loan app (the actual loan system)
    # Annotate with loan counts - both recent and total
    books = books.annotate(
        recent_count=Count(
            'loans',
            filter=Q(loans__loan_date__gte=three_months_ago)
        ),
        total_loans=Count('loans')
    ).order_by('-recent_count', '-total_loans', '-title')
    
    books = books[:limit]
    
    # Build response
    result = []
    for book in books:
        reviews = book.reviews.all()
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
        
        # Get recent loan count from annotated data
        recent_loan_count = book.recent_count if hasattr(book, 'recent_count') else 0
        
        result.append({
            'id': book.id,
            'title': book.title,
            'author': book.author,
            'category': book.category,
            'cover_url': book.cover_url,
            'loan_count': recent_loan_count,
            'avg_rating': round(avg_rating, 1) if avg_rating else None,
            'available': book.available_copies > 0,
            'is_available': book.is_available,
        })
    
    return result


@csrf_exempt
@require_GET
def get_popular_recommendations(request):
    """Get popular book recommendations - GET /api/books/recommendations"""
    category = request.GET.get('category', '').strip() or None
    
    # Get popular books
    popular_books = get_popular_books_internal(limit=10, category=category)
    
    return JsonResponse({
        'recommendations': popular_books,
    })
