from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User

from .models import AuditLog
from .forms import UserCreateForm, UserUpdateForm


def _is_librarian(user):
    """Superuser is always treated as librarian."""
    if user.is_superuser:
        return True
    return hasattr(user, "profile") and user.profile.is_librarian()


def _require_librarian(user):
    if not user.is_authenticated or not _is_librarian(user):
        raise PermissionDenied


def _log(actor, action, target=None, before=None, after=None, notes=""):
    AuditLog.objects.create(actor=actor, action=action, target_user=target,
                            before_value=before, after_value=after, notes=notes)


def _snapshot(user):
    p = user.profile if hasattr(user, "profile") else None
    return {"id": user.pk, "username": user.username,
            "name": f"{user.first_name} {user.last_name}".strip(),
            "role": p.role if p else "", "is_active": user.is_active}


@login_required
def user_list(request):
    _require_librarian(request.user)
    qs        = User.objects.select_related("profile").all()
    search    = request.GET.get("search", "").strip()
    role      = request.GET.get("role", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    if search:
        qs = qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(username__icontains=search))
    if role:
        qs = qs.filter(profile__role=role)
    if is_active == "true":
        qs = qs.filter(is_active=True)
    elif is_active == "false":
        qs = qs.filter(is_active=False)

    _log(request.user, "SEARCH", notes=f"search={search}, role={role}, is_active={is_active}")
    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "user/user_list.html", {"page_obj": page_obj})


@login_required
def user_create(request):
    _require_librarian(request.user)
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save(created_by=request.user)
            _log(request.user, "CREATE", target=user, after=_snapshot(user))
            messages.success(request, "User successfully added.")
            return redirect("user:user_list")
        messages.error(request, "Invalid data. Please check the form.")
    else:
        form = UserCreateForm()
    return render(request, "user/user_form.html", {"form": form, "action": "Add"})


@login_required
def user_update(request, user_id):
    _require_librarian(request.user)
    user_obj = get_object_or_404(User, pk=user_id)
    before   = _snapshot(user_obj)
    if request.method == "POST":
        form = UserUpdateForm(request.POST, user_instance=user_obj)
        if form.is_valid():
            updated = form.save(user_obj)
            _log(request.user, "UPDATE", target=updated, before=before, after=_snapshot(updated))
            messages.success(request, "User data successfully updated.")
            return redirect("user:user_list")
        messages.error(request, "Invalid data. Please check the form.")
    else:
        form = UserUpdateForm(user_instance=user_obj)
    return render(request, "user/user_form.html", {"form": form, "action": "Edit", "user_obj": user_obj})


@login_required
@require_POST
def user_deactivate(request, user_id):
    _require_librarian(request.user)
    user_obj = get_object_or_404(User, pk=user_id)
    if user_obj == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("user:user_list")
    before = _snapshot(user_obj)
    user_obj.is_active = False
    user_obj.save()
    _log(request.user, "DELETE", target=user_obj, before=before, after=_snapshot(user_obj))
    messages.success(request, f"User '{user_obj.first_name} {user_obj.last_name}' has been deactivated.")
    return redirect("user:user_list")