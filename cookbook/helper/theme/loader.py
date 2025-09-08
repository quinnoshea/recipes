"""
Dynamic theme loader for Tandoor Recipes.
Loads theme manifests from JSON files and provides them to the application.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from functools import lru_cache

from django.conf import settings
from django.core.cache import cache
from django.utils.functional import SimpleLazyObject

logger = logging.getLogger(__name__)


@dataclass
class Theme:
    """Represents a loaded theme with all its properties."""
    
    id: str
    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    type: str = "light"  # light, dark, auto
    colors: Dict[str, str] = field(default_factory=dict)
    compatibility: Dict[str, Optional[str]] = field(default_factory=dict)
    screenshots: List[str] = field(default_factory=list)
    extends: Optional[str] = None
    
    def get_css_variables(self) -> str:
        """Generate CSS variable declarations from theme colors."""
        css_vars = []
        for key, value in self.colors.items():
            css_vars.append(f"    {key}: {value};")
        return "\n".join(css_vars)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert theme to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'author': self.author,
            'version': self.version,
            'type': self.type,
            'colors': self.colors,
            'compatibility': self.compatibility,
            'screenshots': self.screenshots,
            'extends': self.extends,
        }
    
    def is_dark(self) -> bool:
        """Check if this is a dark theme."""
        return self.type == 'dark'
    
    def is_light(self) -> bool:
        """Check if this is a light theme."""
        return self.type == 'light'


class ThemeLoader:
    """Manages loading and caching of themes from JSON files."""
    
    CACHE_KEY_PREFIX = 'theme:'
    CACHE_TIMEOUT = 3600  # 1 hour
    
    def __init__(self):
        self.themes_dir = Path(settings.BASE_DIR) / 'cookbook' / 'themes'
        self._themes_cache: Optional[Dict[str, Theme]] = None
        
    def _load_theme_from_file(self, filepath: Path) -> Optional[Theme]:
        """Load a single theme from a JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Apply inheritance if extends is specified
            if data.get('extends'):
                parent_theme = self.get_theme(data['extends'])
                if parent_theme:
                    # Merge parent colors with child colors
                    merged_colors = parent_theme.colors.copy()
                    merged_colors.update(data.get('colors', {}))
                    data['colors'] = merged_colors
            
            return Theme(**data)
            
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"Failed to load theme from {filepath}: {e}")
            return None
    
    @lru_cache(maxsize=32)
    def get_all_themes(self) -> Dict[str, Theme]:
        """Get all available themes, with caching."""
        # Check Django cache first
        cache_key = f"{self.CACHE_KEY_PREFIX}all"
        cached_themes = cache.get(cache_key)
        if cached_themes:
            return cached_themes
        
        themes = {}
        
        if not self.themes_dir.exists():
            logger.warning(f"Themes directory does not exist: {self.themes_dir}")
            return themes
        
        for theme_file in self.themes_dir.glob('*.json'):
            theme = self._load_theme_from_file(theme_file)
            if theme:
                themes[theme.id] = theme
        
        # Cache the loaded themes
        cache.set(cache_key, themes, self.CACHE_TIMEOUT)
        
        return themes
    
    def get_theme(self, theme_id: str) -> Optional[Theme]:
        """Get a specific theme by ID."""
        # Check cache first
        cache_key = f"{self.CACHE_KEY_PREFIX}{theme_id}"
        cached_theme = cache.get(cache_key)
        if cached_theme:
            return cached_theme
        
        themes = self.get_all_themes()
        theme = themes.get(theme_id)
        
        if theme:
            cache.set(cache_key, theme, self.CACHE_TIMEOUT)
        
        return theme
    
    def get_theme_choices(self) -> List[tuple]:
        """Get theme choices for form fields."""
        themes = self.get_all_themes()
        choices = []
        
        # Group by theme type
        light_themes = []
        dark_themes = []
        
        for theme in themes.values():
            choice = (theme.id, theme.name)
            if theme.is_dark():
                dark_themes.append(choice)
            else:
                light_themes.append(choice)
        
        # Add grouped choices
        if light_themes:
            choices.append(('Light Themes', light_themes))
        if dark_themes:
            choices.append(('Dark Themes', dark_themes))
        
        return choices or [('tandoor', 'Tandoor Default')]
    
    def get_default_theme(self) -> Theme:
        """Get the default theme (tandoor)."""
        theme = self.get_theme('tandoor')
        if not theme:
            # Fallback to hardcoded default if file is missing
            theme = Theme(
                id='tandoor',
                name='Tandoor Default',
                type='light',
                colors={
                    '--color-primary': '#8b6a4a',
                    '--color-secondary': '#b55e4f',
                    '--color-background': '#f5efea',
                    '--color-surface': '#ffffff',
                    '--color-error': '#a7240e',
                    '--color-on-primary': '#ffffff',
                    '--color-on-background': '#1a1a1a',
                    '--color-text-primary': '#1a1a1a',
                }
            )
        return theme
    
    def invalidate_cache(self, theme_id: Optional[str] = None):
        """Invalidate theme cache."""
        if theme_id:
            cache.delete(f"{self.CACHE_KEY_PREFIX}{theme_id}")
        else:
            # Clear all theme caches
            cache.delete(f"{self.CACHE_KEY_PREFIX}all")
            # Clear the LRU cache
            self.get_all_themes.cache_clear()
    
    def validate_theme(self, theme_data: Dict) -> List[str]:
        """Validate theme data structure."""
        errors = []
        
        # Required fields
        required = ['id', 'name', 'type', 'colors']
        for field in required:
            if field not in theme_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate type
        if theme_data.get('type') not in ['light', 'dark', 'auto']:
            errors.append("Theme type must be 'light', 'dark', or 'auto'")
        
        # Validate colors
        if 'colors' in theme_data:
            required_colors = [
                '--color-primary',
                '--color-background',
                '--color-text-primary',
            ]
            for color in required_colors:
                if color not in theme_data['colors']:
                    errors.append(f"Missing required color: {color}")
        
        return errors


# Global theme loader instance
theme_loader = SimpleLazyObject(lambda: ThemeLoader())


def get_theme_loader() -> ThemeLoader:
    """Get the global theme loader instance."""
    return theme_loader


def get_available_themes() -> Dict[str, Theme]:
    """Get all available themes."""
    return get_theme_loader().get_all_themes()


def get_theme(theme_id: str) -> Optional[Theme]:
    """Get a specific theme by ID."""
    return get_theme_loader().get_theme(theme_id)


def get_theme_css(theme_id: str) -> str:
    """Get CSS variables for a theme."""
    theme = get_theme(theme_id)
    if not theme:
        theme = get_theme_loader().get_default_theme()
    
    return f"""
:root {{
{theme.get_css_variables()}
}}

[data-theme="{theme.id}"] {{
{theme.get_css_variables()}
}}
"""