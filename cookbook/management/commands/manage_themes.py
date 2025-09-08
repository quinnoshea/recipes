"""
Management command for theme operations.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from rich.console import Console
from rich.table import Table

from cookbook.helper.theme.loader import get_theme_loader, get_available_themes


class Command(BaseCommand):
    help = 'Manage themes: list, validate, or create'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.console = Console()
        self.theme_loader = get_theme_loader()
    
    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='subcommand', help='Theme operations')
        
        # List themes
        list_parser = subparsers.add_parser('list', help='List all available themes')
        list_parser.add_argument(
            '--json',
            action='store_true',
            help='Output as JSON',
        )
        
        # Validate themes
        validate_parser = subparsers.add_parser('validate', help='Validate theme files')
        validate_parser.add_argument(
            'theme_id',
            nargs='?',
            help='Theme ID to validate (validates all if not specified)',
        )
        
        # Create theme template
        create_parser = subparsers.add_parser('create', help='Create a new theme template')
        create_parser.add_argument('theme_id', help='Theme ID')
        create_parser.add_argument('--name', required=True, help='Theme display name')
        create_parser.add_argument('--type', choices=['light', 'dark'], default='light')
        create_parser.add_argument('--extends', help='Theme to extend from')
        
        # Clear cache
        cache_parser = subparsers.add_parser('clear-cache', help='Clear theme cache')
    
    def handle(self, *args, **options):
        subcommand = options.get('subcommand')
        
        if not subcommand:
            self.print_help('manage.py', 'manage_themes')
            return
        
        if subcommand == 'list':
            self.list_themes(options)
        elif subcommand == 'validate':
            self.validate_themes(options)
        elif subcommand == 'create':
            self.create_theme(options)
        elif subcommand == 'clear-cache':
            self.clear_cache()
    
    def list_themes(self, options):
        """List all available themes."""
        themes = get_available_themes()
        
        if options.get('json'):
            theme_data = {
                tid: theme.to_dict() for tid, theme in themes.items()
            }
            self.stdout.write(json.dumps(theme_data, indent=2))
            return
        
        if not themes:
            self.console.print("[yellow]No themes found[/yellow]")
            return
        
        table = Table(title="Available Themes")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Author")
        table.add_column("Version")
        table.add_column("Colors")
        
        for theme_id, theme in themes.items():
            table.add_row(
                theme_id,
                theme.name,
                theme.type,
                theme.author,
                theme.version,
                str(len(theme.colors))
            )
        
        self.console.print(table)
    
    def validate_themes(self, options):
        """Validate theme files."""
        theme_id = options.get('theme_id')
        
        if theme_id:
            theme = self.theme_loader.get_theme(theme_id)
            if not theme:
                self.console.print(f"[red]Theme '{theme_id}' not found[/red]")
                return
            
            themes = {theme_id: theme}
        else:
            themes = get_available_themes()
        
        all_valid = True
        
        for tid, theme in themes.items():
            # Load raw data for validation
            theme_file = Path(settings.BASE_DIR) / 'cookbook' / 'themes' / f'{tid}.json'
            
            if not theme_file.exists():
                self.console.print(f"[red]✗[/red] {tid}: File not found")
                all_valid = False
                continue
            
            try:
                with open(theme_file, 'r') as f:
                    theme_data = json.load(f)
                
                errors = self.theme_loader.validate_theme(theme_data)
                
                if errors:
                    self.console.print(f"[red]✗[/red] {tid}: {', '.join(errors)}")
                    all_valid = False
                else:
                    self.console.print(f"[green]✓[/green] {tid}: Valid")
                    
            except Exception as e:
                self.console.print(f"[red]✗[/red] {tid}: {str(e)}")
                all_valid = False
        
        if not all_valid:
            raise CommandError("Some themes have validation errors")
    
    def create_theme(self, options):
        """Create a new theme template."""
        theme_id = options['theme_id']
        theme_name = options['name']
        theme_type = options['type']
        extends = options.get('extends')
        
        # Validate ID format
        if not theme_id.replace('-', '').replace('_', '').isalnum():
            raise CommandError("Theme ID must be alphanumeric with hyphens/underscores only")
        
        theme_file = Path(settings.BASE_DIR) / 'cookbook' / 'themes' / f'{theme_id}.json'
        
        if theme_file.exists():
            raise CommandError(f"Theme '{theme_id}' already exists")
        
        # Get base colors from parent theme or use defaults
        if extends:
            parent = self.theme_loader.get_theme(extends)
            if not parent:
                raise CommandError(f"Parent theme '{extends}' not found")
            base_colors = parent.colors.copy()
        else:
            # Default color scheme
            if theme_type == 'dark':
                base_colors = {
                    '--color-primary': '#8b93ff',
                    '--color-secondary': '#ff6b6b',
                    '--color-success': '#51cf66',
                    '--color-info': '#339af0',
                    '--color-warning': '#ffd43b',
                    '--color-error': '#ff6b6b',
                    '--color-background': '#1a1a1a',
                    '--color-surface': '#2d2d2d',
                    '--color-on-primary': '#ffffff',
                    '--color-on-background': '#ffffff',
                    '--color-text-primary': '#ffffff',
                }
            else:
                base_colors = {
                    '--color-primary': '#5e72e4',
                    '--color-secondary': '#f5365c',
                    '--color-success': '#2dce89',
                    '--color-info': '#11cdef',
                    '--color-warning': '#fb6340',
                    '--color-error': '#f5365c',
                    '--color-background': '#f8f9fa',
                    '--color-surface': '#ffffff',
                    '--color-on-primary': '#ffffff',
                    '--color-on-background': '#212529',
                    '--color-text-primary': '#212529',
                }
        
        theme_data = {
            'id': theme_id,
            'name': theme_name,
            'description': f'Custom {theme_type} theme',
            'author': 'Your Name',
            'version': '1.0.0',
            'type': theme_type,
            'colors': base_colors,
            'compatibility': {
                'min_version': '1.5.0',
                'max_version': None,
            },
            'screenshots': [],
        }
        
        if extends:
            theme_data['extends'] = extends
        
        # Create themes directory if it doesn't exist
        theme_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write theme file
        with open(theme_file, 'w') as f:
            json.dump(theme_data, f, indent=2)
        
        self.console.print(f"[green]✓[/green] Created theme template at {theme_file}")
        self.console.print(f"[yellow]Edit the file to customize colors and properties[/yellow]")
    
    def clear_cache(self):
        """Clear theme cache."""
        self.theme_loader.invalidate_cache()
        self.console.print("[green]✓[/green] Theme cache cleared")