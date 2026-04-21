"""
Perpusnas → Open Library → Google Books
"""

import re
import logging
import requests

logger  = logging.getLogger(__name__)
TIMEOUT = 6

# ─── Category cleaner ────────────────────────────────────────────────────────

_JUNK_RE = re.compile(
    r'nyt:|bestseller|http|\d{4}-\d{2}-\d{2}|=',
    re.IGNORECASE
)
_JUNK_WORDS = {
    'and','or','the','a','an','of','in','on','at','to','for',
    'with','by','from','as','is','was','form','new','old',
    'nyt','times','york','general','comic','strips',
}

def _clean_categories(raw_list: list, max_items: int = 4) -> str | None:
    """
    Terima list string kategori mentah → string bersih dipisah koma.
    - Buang entri dengan pola junk (nyt:..., tanggal ISO, URL, dll)
    - Buang entri terlalu pendek (≤ 3 karakter)
    - Buang entri yang seluruhnya stop-word
    - Title-case & deduplicate
    """
    seen   = set()
    result = []

    for item in raw_list:
        if not item:
            continue
        item = str(item).strip()

        if _JUNK_RE.search(item):
            continue
        if len(item) <= 3:
            continue

        # Cek apakah semua kata adalah stop-word / digit
        words = re.sub(r'[^a-zA-Z\s]', '', item).lower().split()
        if not words or all(w in _JUNK_WORDS or w.isdigit() for w in words):
            continue

        normalized = item.title()
        key = normalized.lower()
        if key in seen:
            continue

        seen.add(key)
        result.append(normalized)
        if len(result) >= max_items:
            break

    return ', '.join(result) if result else None


# ─── 1. PERPUSNAS ────────────────────────────────────────────────────────────

PERPUSNAS_URL = "https://isbn.perpusnas.go.id/Account/GetBuku"

def fetch_perpusnas(isbn: str) -> dict:
    try:
        r = requests.get(
            PERPUSNAS_URL,
            params={"offset": 0, "limits": 1, "kd1": "ISBN", "kd2": isbn},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=TIMEOUT,
        )
        data = r.json()
        rows = data.get("rows", [])
        if not rows:
            return {}

        book = rows[0]

        year = book.get("Tahun", "")
        if year and str(year).startswith("/Date("):
            try:
                import datetime
                ms   = int(re.search(r'\d+', str(year)).group())
                year = str(datetime.datetime.fromtimestamp(ms / 1000).year)
            except Exception:
                year = None
        else:
            year = str(year).strip()[:4] if year else None

        publisher = book.get("Penerbit", "").strip() or None
        seri      = book.get("Seri", "").strip() or None
        category  = _clean_categories([seri]) if seri else None

        return {
            "title":        book.get("Judul", "").strip() or None,
            "author":       book.get("Pengarang", "").strip() or None,
            "cover_url":    None,
            "publisher":    publisher,
            "publish_year": year,
            "category":     category,
            "synopsis":     None,
        }
    except Exception as e:
        logger.warning(f"Perpusnas fetch failed for ISBN {isbn}: {e}")
        return {}


# ─── 2. OPEN LIBRARY ─────────────────────────────────────────────────────────

OPEN_LIBRARY_URL = "https://openlibrary.org/api/books"

def fetch_open_library(isbn: str) -> dict:
    try:
        r = requests.get(
            OPEN_LIBRARY_URL,
            params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            timeout=TIMEOUT,
        )
        data = r.json()
        book = data.get(f"ISBN:{isbn}", {})
        if not book:
            return {}

        covers    = book.get("cover", {})
        cover_url = covers.get("large") or covers.get("medium") or covers.get("small")

        publishers = book.get("publishers", [])
        publisher  = publishers[0].get("name") if publishers else None

        # Subjects OL: bisa list string atau list dict {"name": "..."}
        # Satu subject bisa berisi beberapa genre: "Humor, form, comic strips"
        # → split per koma dulu, BARU masuk cleaner
        subjects_raw  = book.get("subjects", [])
        subjects_flat = []
        for s in subjects_raw:
            name = s.get("name", s) if isinstance(s, dict) else s
            for part in str(name).split(","):
                subjects_flat.append(part.strip())

        category = _clean_categories(subjects_flat)

        desc = book.get("description")
        if isinstance(desc, dict):
            desc = desc.get("value")

        authors     = book.get("authors", [])
        author      = ", ".join([a.get("name") for a in authors]) if authors else None

        return {
            "title":        book.get("title"),
            "author":       author,
            "cover_url":    cover_url,
            "publisher":    publisher,
            "publish_year": book.get("publish_date"),
            "category":     category,
            "synopsis":     desc,
        }
    except Exception as e:
        logger.warning(f"Open Library fetch failed for ISBN {isbn}: {e}")
        return {}


# ─── 3. GOOGLE BOOKS ─────────────────────────────────────────────────────────

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"

def fetch_google_books(isbn: str) -> dict:
    try:
        r    = requests.get(GOOGLE_BOOKS_URL, params={"q": f"isbn:{isbn}"}, timeout=TIMEOUT)
        data = r.json()
        items = data.get("items")
        if not items:
            return {}
        info = items[0].get("volumeInfo", {})

        imgs  = info.get("imageLinks", {})
        cover = (
                imgs.get("large") or imgs.get("medium")
                or imgs.get("thumbnail") or imgs.get("smallThumbnail")
        )
        if cover:
            cover = cover.replace("http://", "https://")

        # Google Books: "Fiction / Humor" → split per "/"
        cats_flat = []
        for c in info.get("categories", []):
            for part in str(c).split("/"):
                cats_flat.append(part.strip())

        category = _clean_categories(cats_flat)

        year = info.get("publishedDate", "")
        year = year[:4] if year else None

        authors = info.get("authors", [])
        author  = ", ".join(authors) if authors else None

        return {
            "title":        info.get("title"),
            "author":       author,
            "cover_url":    cover,
            "publisher":    info.get("publisher"),
            "publish_year": year,
            "category":     category,
            "synopsis":     info.get("description"),
        }
    except Exception as e:
        logger.warning(f"Google Books fetch failed for ISBN {isbn}: {e}")
        return {}


# ─── MAIN ENRICH ─────────────────────────────────────────────────────────────

def enrich_book_from_isbn(isbn: str) -> dict:
    """Perpusnas → Open Library → Google Books. Field dari sumber pertama yang punya nilai."""
    perpus = fetch_perpusnas(isbn)
    ol     = fetch_open_library(isbn)
    gb     = fetch_google_books(isbn)

    result = {}
    for field in ("title", "author", "cover_url", "publisher", "publish_year", "category", "synopsis"):
        result[field] = perpus.get(field) or ol.get(field) or gb.get(field)

    return result


# ─── SEARCH BY TITLE ─────────────────────────────────────────────────────────

def search_perpusnas_by_title(title: str, limit: int = 5) -> list:
    try:
        r = requests.get(
            PERPUSNAS_URL,
            params={"offset": 0, "limits": limit, "kd1": "judul", "kd2": title},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=TIMEOUT,
        )
        data = r.json()
        return [
            {
                "judul":    row.get("Judul", ""),
                "penulis":  row.get("Pengarang", ""),
                "penerbit": row.get("Penerbit", ""),
                "tahun":    str(row.get("Tahun", ""))[:4],
                "isbn":     row.get("ISBN", ""),
            }
            for row in data.get("rows", [])
        ]
    except Exception as e:
        logger.warning(f"Perpusnas title search failed: {e}")
        return []