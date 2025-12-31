"""
واجهة المستخدم
User Interface module
"""

# تأخير استيراد MainWindow لتجنب circular import مع المجدولات
# Delay MainWindow import to avoid circular import with schedulers
# from .main_window import MainWindow
from .scheduler_ui import SchedulerUI
from .signals import UiSignals

from .widgets import (
    NoScrollComboBox,
    NoScrollSpinBox,
    NoScrollDoubleSpinBox,
    NoScrollSlider,
)

from .dialogs import (
    HashtagManagerDialog,
)

from .helpers import (
    create_fallback_icon,
    load_app_icon,
    get_icon,
    create_icon_button,
    create_icon_action,
    ICONS,
    ICON_COLORS,
    HAS_QTAWESOME,
)

def __getattr__(name):
    """Lazy loading for MainWindow to avoid circular import"""
    if name == 'MainWindow':
        try:
            from .main_window import MainWindow
            # Cache the import in module globals to avoid repeated imports
            globals()['MainWindow'] = MainWindow
            return MainWindow
        except ImportError as e:
            # Log import error and re-raise with context
            import sys
            print(f"Failed to import MainWindow: {e}", file=sys.stderr)
            raise
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    'MainWindow',  # سيتم تحميله عند الطلب - Will be loaded on demand
    'SchedulerUI',
    'UiSignals',
    'NoScrollComboBox',
    'NoScrollSpinBox',
    'NoScrollDoubleSpinBox',
    'NoScrollSlider',
    'HashtagManagerDialog',
    'create_fallback_icon',
    'load_app_icon',
    'get_icon',
    'create_icon_button',
    'create_icon_action',
    'ICONS',
    'ICON_COLORS',
    'HAS_QTAWESOME',
]
