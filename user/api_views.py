import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q

from authentication.models import UserProfile
from .models import AuditLog
from .forms import UserCreateForm, UserUpdateForm


def _is_librarian(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return hasattr(user, "profile") and user.profile.is_librarian()


def _serialize_user(user):
    profile = getattr(user, "profile", None)
    return {
        "id":           user.pk,
        "username":     user.username,
        "first_name":   user.first_name,
        "last_name":    user.last_name,
        "email":        user.email,
        "is_active":    user.is_active,
        "is_superuser": user.is_superuser,
        "role":         profile.role if profile else None,
        "nis":          profile.nis if profile else None,
        "kelas":        profile.kelas if profile else None,
        "gender":       profile.gender if profile else None,
    }


def _log(actor, action, target=None, before=None, after=None, notes=""):
    AuditLog.objects.create(
        actor=actor, action=action, target_user=target,
        before_value=before, after_value=after, notes=notes,
    )


def _snapshot(user):
    p = getattr(user, "profile", None)
    return {
        "id":        user.pk,
        "username":  user.username,
        "name":      f"{user.first_name} {user.last_name}".strip(),
        "role":      p.role if p else "",
        "is_active": user.is_active,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_user_list_create(request):

    if request.method == "GET":
        if not _is_librarian(request.user):
            return JsonResponse({"error": "Forbidden"}, status=403)

        qs       = User.objects.select_related("profile").all()
        search   = request.GET.get("search", "").strip()
        status   = request.GET.get("status", "").strip()
        role     = request.GET.get("role", "").strip()
        page_num = request.GET.get("page", 1)

        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search)  |
                Q(username__icontains=search)   |
                Q(profile__nis__icontains=search)
            )
        if status == "ACTIVE":
            qs = qs.filter(is_active=True)
        elif status == "INACTIVE":
            qs = qs.filter(is_active=False)
        if role:
            qs = qs.filter(profile__role=role)

        _log(request.user, "SEARCH",
             notes=f"search={search}, status={status}, role={role}")

        paginator = Paginator(qs, 15)
        page_obj  = paginator.get_page(page_num)

        return JsonResponse({
            "count":        paginator.count,
            "num_pages":    paginator.num_pages,
            "current_page": page_obj.number,
            "results":      [_serialize_user(u) for u in page_obj],
        }, status=200)

    if request.method == "POST":
        if not _is_librarian(request.user):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Request body tidak valid (JSON diperlukan)."}, status=400)

        form = UserCreateForm(body)
        if not form.is_valid():
            if "username" in form.errors:
                return JsonResponse({"error": "Konflik data.", "detail": form.errors}, status=409)
            return JsonResponse({"error": "Data tidak valid.", "detail": form.errors}, status=400)

        user = form.save(created_by=request.user)
        _log(request.user, "CREATE", target=user, after=_snapshot(user))

        return JsonResponse({
            "message": "Pengguna berhasil ditambahkan.",
            "user":    _serialize_user(user),
        }, status=201)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def api_user_detail(request, user_id):

    if not _is_librarian(request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)

    try:
        user_obj = User.objects.select_related("profile").get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": "Pengguna tidak ditemukan."}, status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_user(user_obj), status=200)

    if request.method == "PUT":
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Request body tidak valid (JSON diperlukan)."}, status=400)

        before = _snapshot(user_obj)
        form   = UserUpdateForm(body, user_instance=user_obj)
        if not form.is_valid():
            return JsonResponse({"error": "Data tidak valid.", "detail": form.errors}, status=400)

        updated = form.save(user_obj)
        _log(request.user, "UPDATE",
             target=updated, before=before, after=_snapshot(updated))

        return JsonResponse({
            "message": "Data pengguna berhasil diperbarui.",
            "user":    _serialize_user(updated),
        }, status=200)

    if request.method == "DELETE":
        if user_obj == request.user:
            return JsonResponse({"error": "Tidak dapat menonaktifkan akun sendiri."}, status=403)
        if user_obj.is_superuser:
            return JsonResponse({"error": "Tidak dapat menonaktifkan akun superuser."}, status=403)

        before = _snapshot(user_obj)
        user_obj.is_active = False
        user_obj.save()
        _log(request.user, "DELETE",
             target=user_obj, before=before, after=_snapshot(user_obj))

        return JsonResponse({
            "message": f"Pengguna '{user_obj.first_name} {user_obj.last_name}' berhasil dinonaktifkan.",
        }, status=200)