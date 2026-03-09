from django import template

register = template.Library()

@register.filter
def split_comma(value):
    """
    Split string kategori per koma → list.
    Usage di template: {% for cat in book.category|split_comma %}
    """
    if not value:
        return []
    return [c.strip() for c in str(value).split(',') if c.strip()]