def user_roles(request):
    """Superuser is always treated as librarian."""
    if not request.user.is_authenticated:
        return {"is_librarian": False}
    if request.user.is_superuser:
        return {"is_librarian": True}
    is_librarian = (
            hasattr(request.user, "profile") and
            request.user.profile.is_librarian()
    )
    return {"is_librarian": is_librarian}