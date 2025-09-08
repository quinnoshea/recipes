"""
Template tags for the new dynamic theme system.
"""

from django import template
from django.utils.safestring import mark_safe

from cookbook.helper.theme.loader import (
    get_available_themes,
    get_theme,
    get_theme_loader,
)

register = template.Library()


@register.simple_tag
def theme_css_variables(theme_id: str = "tandoor"):
    """
    Generate CSS variables for a theme.
    Usage: {% theme_css_variables 'dracula' %}
    """
    theme = get_theme(theme_id)
    if not theme:
        theme = get_theme_loader().get_default_theme()

    css = f"""
<style id="theme-variables">
:root {{
{theme.get_css_variables()}
}}

body[data-theme="{theme.id}"] {{
{theme.get_css_variables()}
}}

/* Theme-specific adjustments */
.theme-{theme.id} {{
{theme.get_css_variables()}
}}
</style>
"""
    return mark_safe(css)


@register.simple_tag
def available_themes():
    """
    Get all available themes.
    Usage: {% available_themes as themes %}
    """
    return get_available_themes()


@register.simple_tag
def theme_info(theme_id: str):
    """
    Get information about a specific theme.
    Usage: {% theme_info 'dracula' as theme %}
    """
    return get_theme(theme_id)


@register.simple_tag
def theme_type_class(theme_id: str):
    """
    Get CSS class based on theme type (light/dark).
    Usage: <body class="{% theme_type_class user.userpreference.theme %}">
    """
    theme = get_theme(theme_id)
    if not theme:
        return "theme-light"

    return f"theme-{theme.type}"


@register.simple_tag(takes_context=True)
def user_theme_css(context):
    """
    Generate CSS variables for the current user's theme.
    Usage: {% user_theme_css %}
    """
    request = context.get("request")

    # Default theme
    theme_id = "tandoor"

    # Get user preference if authenticated
    if request and request.user.is_authenticated:
        try:
            theme_id = request.user.userpreference.theme.lower()
        except:
            pass

    return theme_css_variables(theme_id)


@register.filter
def theme_name(theme_id: str):
    """
    Get the display name of a theme.
    Usage: {{ user.userpreference.theme|theme_name }}
    """
    theme = get_theme(theme_id)
    return theme.name if theme else theme_id.title()
