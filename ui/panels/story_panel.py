"""
لوحة الستوري - Story Panel
تحتوي على واجهة إدارة رفع الستوري
Contains the interface for managing story uploads
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QLabel, QCheckBox, QGroupBox, QFormLayout, QHBoxLayout, QVBoxLayout
)

from controllers.story_controller import (
    DEFAULT_STORIES_PER_SCHEDULE, DEFAULT_RANDOM_DELAY_MIN, DEFAULT_RANDOM_DELAY_MAX
)
from ui.widgets import NoScrollSpinBox
from ui.helpers import get_icon, ICONS, ICON_COLORS, HAS_QTAWESOME


class StoryPanel(QWidget):
    """
    لوحة إعدادات الستوري
    Story settings panel containing all story-specific UI elements
    """
    
    # Signals للتواصل مع MainWindow
    settings_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """إنشاء واجهة المستخدم لإعدادات الستوري"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # عدد الستوريات لكل جدولة
        self.stories_per_schedule_row = QHBoxLayout()
        self.stories_per_schedule_label = QLabel('📱 عدد الستوريات لكل جدولة:')
        self.stories_per_schedule_spin = NoScrollSpinBox()
        self.stories_per_schedule_spin.setRange(1, 50)
        self.stories_per_schedule_spin.setValue(DEFAULT_STORIES_PER_SCHEDULE)
        self.stories_per_schedule_spin.setToolTip(
            'عدد الفيديوهات/الصور التي سيتم نشرها في كل دورة جدولة للستوري'
        )
        self.stories_per_schedule_row.addWidget(self.stories_per_schedule_label)
        self.stories_per_schedule_row.addWidget(self.stories_per_schedule_spin)
        
        stories_widget = QWidget()
        stories_widget.setLayout(self.stories_per_schedule_row)
        layout.addWidget(stories_widget)
        
        # مجموعة التأخير بين الستوريات (حماية من الحظر)
        story_delay_group = QGroupBox('حماية من الحظر (Rate Limiting)')
        if HAS_QTAWESOME:
            story_delay_group.setTitle('')
        story_delay_layout = QFormLayout()
        
        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            story_title_row = QHBoxLayout()
            story_icon_label = QLabel()
            story_icon_label.setPixmap(
                get_icon(ICONS['shield'], ICON_COLORS.get('shield')).pixmap(16, 16)
            )
            story_title_row.addWidget(story_icon_label)
            story_title_row.addWidget(QLabel('حماية من الحظر (Rate Limiting)'))
            story_title_row.addStretch()
            story_delay_layout.addRow(story_title_row)
        
        # تفعيل الحماية من الحظر
        self.story_anti_ban_checkbox = QCheckBox('تفعيل التأخير بين الستوريات')
        self.story_anti_ban_checkbox.setChecked(True)
        self.story_anti_ban_checkbox.setToolTip(
            'تفعيل التأخير بين رفع كل ستوري لتجنب الحظر من فيسبوك'
        )
        story_delay_layout.addRow(self.story_anti_ban_checkbox)
        
        # التأخير العشوائي
        random_delay_row = QHBoxLayout()
        random_delay_row.addWidget(QLabel('التأخير العشوائي:'))
        random_delay_row.addWidget(QLabel('من:'))
        
        self.story_random_delay_min_spin = NoScrollSpinBox()
        self.story_random_delay_min_spin.setRange(5, 300)
        self.story_random_delay_min_spin.setValue(DEFAULT_RANDOM_DELAY_MIN)
        self.story_random_delay_min_spin.setSuffix(' ثانية')
        self.story_random_delay_min_spin.setToolTip('الحد الأدنى للتأخير بين رفع الستوريات')
        random_delay_row.addWidget(self.story_random_delay_min_spin)
        
        random_delay_row.addWidget(QLabel('إلى:'))
        
        self.story_random_delay_max_spin = NoScrollSpinBox()
        self.story_random_delay_max_spin.setRange(30, 600)
        self.story_random_delay_max_spin.setValue(DEFAULT_RANDOM_DELAY_MAX)
        self.story_random_delay_max_spin.setSuffix(' ثانية')
        self.story_random_delay_max_spin.setToolTip('الحد الأقصى للتأخير بين رفع الستوريات')
        random_delay_row.addWidget(self.story_random_delay_max_spin)
        
        story_delay_layout.addRow(random_delay_row)
        story_delay_group.setLayout(story_delay_layout)
        layout.addWidget(story_delay_group)
        
        layout.addStretch()
    
    def get_stories_per_schedule(self) -> int:
        """الحصول على عدد الستوريات لكل جدولة"""
        return self.stories_per_schedule_spin.value()
    
    def set_stories_per_schedule(self, value: int):
        """تعيين عدد الستوريات لكل جدولة"""
        self.stories_per_schedule_spin.setValue(value)
    
    def get_anti_ban_enabled(self) -> bool:
        """الحصول على حالة تفعيل الحماية من الحظر"""
        return self.story_anti_ban_checkbox.isChecked()
    
    def set_anti_ban_enabled(self, enabled: bool):
        """تعيين حالة تفعيل الحماية من الحظر"""
        self.story_anti_ban_checkbox.setChecked(enabled)
    
    def get_random_delay_min(self) -> int:
        """الحصول على الحد الأدنى للتأخير العشوائي"""
        return self.story_random_delay_min_spin.value()
    
    def set_random_delay_min(self, value: int):
        """تعيين الحد الأدنى للتأخير العشوائي"""
        self.story_random_delay_min_spin.setValue(value)
    
    def get_random_delay_max(self) -> int:
        """الحصول على الحد الأقصى للتأخير العشوائي"""
        return self.story_random_delay_max_spin.value()
    
    def set_random_delay_max(self, value: int):
        """تعيين الحد الأقصى للتأخير العشوائي"""
        self.story_random_delay_max_spin.setValue(value)
    
    def reset_to_defaults(self):
        """إعادة تعيين جميع القيم إلى الافتراضية"""
        self.stories_per_schedule_spin.setValue(DEFAULT_STORIES_PER_SCHEDULE)
        self.story_anti_ban_checkbox.setChecked(True)
        self.story_random_delay_min_spin.setValue(DEFAULT_RANDOM_DELAY_MIN)
        self.story_random_delay_max_spin.setValue(DEFAULT_RANDOM_DELAY_MAX)
    
    def get_settings(self) -> dict:
        """الحصول على جميع الإعدادات كقاموس"""
        return {
            'stories_per_schedule': self.get_stories_per_schedule(),
            'anti_ban_enabled': self.get_anti_ban_enabled(),
            'random_delay_min': self.get_random_delay_min(),
            'random_delay_max': self.get_random_delay_max()
        }
    
    def set_settings(self, settings: dict):
        """تعيين جميع الإعدادات من قاموس"""
        if 'stories_per_schedule' in settings:
            self.set_stories_per_schedule(settings['stories_per_schedule'])
        if 'anti_ban_enabled' in settings:
            self.set_anti_ban_enabled(settings['anti_ban_enabled'])
        if 'random_delay_min' in settings:
            self.set_random_delay_min(settings['random_delay_min'])
        if 'random_delay_max' in settings:
            self.set_random_delay_max(settings['random_delay_max'])
