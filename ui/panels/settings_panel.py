"""
لوحة الإعدادات - Settings Panel
واجهة الإعدادات المتقدمة للتطبيق

Settings panel for advanced application configuration
"""

from typing import Optional, Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox
)


class SettingsPanel(QWidget):
    """
    لوحة الإعدادات المتقدمة
    Advanced settings panel widget
    
    Signals:
        settings_changed: Signal() - Emitted when settings are modified
        test_telegram: Signal() - Request to test Telegram connection
        show_telegram_help: Signal() - Request to show Telegram help
        check_updates: Signal() - Request to check for updates
        run_updates: Signal() - Request to run updates
        save_settings: Signal() - Request to save settings
    """
    
    # Signals
    settings_changed = Signal()
    test_telegram = Signal()
    show_telegram_help = Signal()
    check_updates = Signal()
    run_updates = Signal()
    save_settings = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None,
                 create_icon_button: Optional[Callable] = None,
                 get_icon: Optional[Callable] = None,
                 HAS_QTAWESOME: bool = False,
                 ICONS: Optional[dict] = None,
                 ICON_COLORS: Optional[dict] = None):
        """
        Initialize the settings panel.
        
        Args:
            parent: Parent widget
            create_icon_button: Function to create icon buttons
            get_icon: Function to get icons
            HAS_QTAWESOME: Whether qtawesome is available
            ICONS: Icon definitions dictionary
            ICON_COLORS: Icon color definitions dictionary
        """
        super().__init__(parent)
        
        # Store dependencies
        self._create_icon_button = create_icon_button or self._create_default_button
        self._get_icon = get_icon
        self._HAS_QTAWESOME = HAS_QTAWESOME
        self._ICONS = ICONS or {}
        self._ICON_COLORS = ICON_COLORS or {}
        
        # Initialize widgets (will be created in _setup_ui)
        self.validate_videos_checkbox = None
        self.internet_check_checkbox = None
        self.telegram_enabled_checkbox = None
        self.telegram_notify_success_checkbox = None
        self.telegram_notify_errors_checkbox = None
        self.telegram_bot_token_input = None
        self.telegram_chat_id_input = None
        self.telegram_test_btn = None
        self.telegram_status_label = None
        self.updates_table = None
        self.update_status_label = None
        self.check_updates_btn = None
        self.update_all_btn = None
        
        self._setup_ui()
    
    def _create_default_button(self, text: str, icon_key: str = None, **kwargs) -> QPushButton:
        """Create a default button without icons."""
        return QPushButton(text)
    
    def _setup_ui(self):
        """إعداد واجهة المستخدم - Setup user interface"""
        layout = QVBoxLayout(self)
        
        # Video validation group
        self._build_validation_group(layout)
        
        # Internet check group
        self._build_internet_check_group(layout)
        
        # Telegram notifications group
        self._build_telegram_group(layout)
        
        # Updates group
        self._build_updates_group(layout)
        
        # Save button
        save_btn = self._create_icon_button('حفظ الإعدادات', 'save')
        save_btn.clicked.connect(self.save_settings.emit)
        layout.addWidget(save_btn)
        
        layout.addStretch()
    
    def _build_validation_group(self, parent_layout: QVBoxLayout):
        """بناء مجموعة التحقق من الفيديو - Build video validation group"""
        validation_group = QGroupBox('التحقق من صحة الفيديو')
        if self._HAS_QTAWESOME:
            validation_group.setTitle('')
        validation_form = QFormLayout()
        
        # Title with icon
        if self._HAS_QTAWESOME and self._get_icon:
            val_title_row = QHBoxLayout()
            val_icon_label = QLabel()
            val_icon_label.setPixmap(
                self._get_icon(self._ICONS.get('warning'), 
                             self._ICON_COLORS.get('warning')).pixmap(16, 16)
            )
            val_title_row.addWidget(val_icon_label)
            val_title_row.addWidget(QLabel('التحقق من صحة الفيديو'))
            val_title_row.addStretch()
            validation_form.addRow(val_title_row)
        
        self.validate_videos_checkbox = QCheckBox('التحقق من الفيديوهات قبل الرفع')
        self.validate_videos_checkbox.setToolTip('فحص ملفات الفيديو للتأكد من صلاحيتها قبل محاولة الرفع')
        self.validate_videos_checkbox.stateChanged.connect(self.settings_changed.emit)
        validation_form.addRow(self.validate_videos_checkbox)
        
        validation_group.setLayout(validation_form)
        parent_layout.addWidget(validation_group)
    
    def _build_internet_check_group(self, parent_layout: QVBoxLayout):
        """بناء مجموعة فحص الاتصال - Build internet check group"""
        internet_group = QGroupBox('فحص الاتصال بالإنترنت')
        if self._HAS_QTAWESOME:
            internet_group.setTitle('')
        internet_form = QFormLayout()
        
        # Title with icon
        if self._HAS_QTAWESOME and self._get_icon:
            net_title_row = QHBoxLayout()
            net_icon_label = QLabel()
            net_icon_label.setPixmap(
                self._get_icon(self._ICONS.get('network'),
                             self._ICON_COLORS.get('network')).pixmap(16, 16)
            )
            net_title_row.addWidget(net_icon_label)
            net_title_row.addWidget(QLabel('فحص الاتصال بالإنترنت'))
            net_title_row.addStretch()
            internet_form.addRow(net_title_row)
        
        self.internet_check_checkbox = QCheckBox('فحص الاتصال قبل كل عملية رفع')
        if self._HAS_QTAWESOME and self._get_icon:
            self.internet_check_checkbox.setIcon(
                self._get_icon(self._ICONS.get('network'),
                             self._ICON_COLORS.get('network'))
            )
        self.internet_check_checkbox.setToolTip(
            'عند تفعيل هذا الخيار، سيتحقق البرنامج من الاتصال بالإنترنت قبل كل رفع.\n'
            'إذا انقطع الاتصال، سيدخل في وضع الغفوة ويعيد المحاولة كل دقيقة حتى يعود الاتصال.'
        )
        self.internet_check_checkbox.stateChanged.connect(self.settings_changed.emit)
        internet_form.addRow(self.internet_check_checkbox)
        
        internet_group.setLayout(internet_form)
        parent_layout.addWidget(internet_group)
    
    def _build_telegram_group(self, parent_layout: QVBoxLayout):
        """بناء مجموعة Telegram - Build Telegram group"""
        telegram_group = QGroupBox('إشعارات Telegram')
        if self._HAS_QTAWESOME:
            telegram_group.setTitle('')
        telegram_layout = QVBoxLayout()
        
        # Title with icon
        if self._HAS_QTAWESOME and self._get_icon:
            tg_title_row = QHBoxLayout()
            tg_icon_label = QLabel()
            tg_icon_label.setPixmap(
                self._get_icon(self._ICONS.get('telegram'),
                             self._ICON_COLORS.get('telegram')).pixmap(16, 16)
            )
            tg_title_row.addWidget(tg_icon_label)
            tg_title_row.addWidget(QLabel('إشعارات Telegram Bot'))
            tg_title_row.addStretch()
            telegram_layout.addLayout(tg_title_row)
        
        # Enable notifications checkbox
        self.telegram_enabled_checkbox = QCheckBox('تفعيل إشعارات Telegram')
        self.telegram_enabled_checkbox.setToolTip('إرسال إشعارات عند نجاح أو فشل رفع الفيديو عبر Telegram Bot')
        self.telegram_enabled_checkbox.stateChanged.connect(self.settings_changed.emit)
        telegram_layout.addWidget(self.telegram_enabled_checkbox)
        
        # Notification options
        notify_options_layout = QVBoxLayout()
        notify_options_layout.setContentsMargins(20, 5, 0, 5)
        
        self.telegram_notify_success_checkbox = QCheckBox('إرسال إشعارات نجاح الرفع ✅')
        self.telegram_notify_success_checkbox.setToolTip('إرسال إشعار عند نجاح رفع فيديو أو ستوري أو ريلز')
        self.telegram_notify_success_checkbox.stateChanged.connect(self.settings_changed.emit)
        notify_options_layout.addWidget(self.telegram_notify_success_checkbox)
        
        self.telegram_notify_errors_checkbox = QCheckBox('إرسال إشعارات الأخطاء والفشل ❌')
        self.telegram_notify_errors_checkbox.setToolTip('إرسال إشعار عند فشل الرفع أو حدوث أي خطأ في البرنامج')
        self.telegram_notify_errors_checkbox.stateChanged.connect(self.settings_changed.emit)
        notify_options_layout.addWidget(self.telegram_notify_errors_checkbox)
        
        telegram_layout.addLayout(notify_options_layout)
        
        # Settings form
        telegram_form = QFormLayout()
        
        self.telegram_bot_token_input = QLineEdit()
        self.telegram_bot_token_input.setPlaceholderText('أدخل توكن البوت من @BotFather')
        self.telegram_bot_token_input.setEchoMode(QLineEdit.Password)
        self.telegram_bot_token_input.textChanged.connect(self.settings_changed.emit)
        telegram_form.addRow('توكن البوت:', self.telegram_bot_token_input)
        
        self.telegram_chat_id_input = QLineEdit()
        self.telegram_chat_id_input.setPlaceholderText('معرّف المحادثة أو القناة (مثل: -1001234567890)')
        self.telegram_chat_id_input.textChanged.connect(self.settings_changed.emit)
        telegram_form.addRow('معرّف المحادثة:', self.telegram_chat_id_input)
        
        telegram_layout.addLayout(telegram_form)
        
        # Buttons
        telegram_buttons_row = QHBoxLayout()
        
        self.telegram_test_btn = self._create_icon_button('اختبار الاتصال', 'telegram')
        self.telegram_test_btn.clicked.connect(self.test_telegram.emit)
        telegram_buttons_row.addWidget(self.telegram_test_btn)
        
        telegram_help_btn = self._create_icon_button('كيفية الإعداد؟', 'info')
        telegram_help_btn.clicked.connect(self.show_telegram_help.emit)
        telegram_buttons_row.addWidget(telegram_help_btn)
        
        telegram_layout.addLayout(telegram_buttons_row)
        
        # Status label
        self.telegram_status_label = QLabel('')
        self.telegram_status_label.setAlignment(Qt.AlignCenter)
        self.telegram_status_label.setWordWrap(True)
        telegram_layout.addWidget(self.telegram_status_label)
        
        telegram_group.setLayout(telegram_layout)
        parent_layout.addWidget(telegram_group)
    
    def _build_updates_group(self, parent_layout: QVBoxLayout):
        """بناء مجموعة التحديثات - Build updates group"""
        from core.constants import COUNTDOWN_COLOR_GREEN
        
        updates_group = QGroupBox('تحديث المكتبات')
        if self._HAS_QTAWESOME:
            updates_group.setTitle('')
        updates_layout = QVBoxLayout()
        
        # Title with icon
        if self._HAS_QTAWESOME and self._get_icon:
            updates_title_row = QHBoxLayout()
            updates_icon_label = QLabel()
            updates_icon_label.setPixmap(
                self._get_icon(self._ICONS.get('update'),
                             self._ICON_COLORS.get('update')).pixmap(16, 16)
            )
            updates_title_row.addWidget(updates_icon_label)
            updates_title_row.addWidget(QLabel('تحديث المكتبات'))
            updates_title_row.addStretch()
            updates_layout.addLayout(updates_title_row)
        
        # Updates table
        self.updates_table = QTableWidget()
        self.updates_table.setColumnCount(4)
        self.updates_table.setHorizontalHeaderLabels(['المكتبة', 'الحالي', 'المتاح', 'الحالة'])
        self.updates_table.horizontalHeader().setStretchLastSection(True)
        self.updates_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.updates_table.setMaximumHeight(150)
        updates_layout.addWidget(self.updates_table)
        
        # Status label
        self.update_status_label = QLabel('اضغط على "البحث عن تحديثات" للتحقق')
        self.update_status_label.setAlignment(Qt.AlignCenter)
        updates_layout.addWidget(self.update_status_label)
        
        # Buttons
        update_buttons_row = QHBoxLayout()
        
        self.check_updates_btn = self._create_icon_button('البحث عن تحديثات', 'search')
        self.check_updates_btn.clicked.connect(self.check_updates.emit)
        update_buttons_row.addWidget(self.check_updates_btn)
        
        self.update_all_btn = self._create_icon_button('تحديث الكل', 'update', color=COUNTDOWN_COLOR_GREEN)
        self.update_all_btn.clicked.connect(self.run_updates.emit)
        self.update_all_btn.setVisible(False)
        self.update_all_btn.setStyleSheet(
            f'background-color: {COUNTDOWN_COLOR_GREEN}; color: white; font-weight: bold;'
        )
        update_buttons_row.addWidget(self.update_all_btn)
        
        updates_layout.addLayout(update_buttons_row)
        updates_group.setLayout(updates_layout)
        parent_layout.addWidget(updates_group)
    
    # ==================== Data Access Methods ====================
    
    def get_settings(self) -> dict:
        """
        الحصول على الإعدادات الحالية - Get current settings
        
        Returns:
            dict: Dictionary containing all settings
        """
        return {
            'validate_videos': self.validate_videos_checkbox.isChecked(),
            'internet_check_enabled': self.internet_check_checkbox.isChecked(),
            'telegram_enabled': self.telegram_enabled_checkbox.isChecked(),
            'telegram_notify_success': self.telegram_notify_success_checkbox.isChecked(),
            'telegram_notify_errors': self.telegram_notify_errors_checkbox.isChecked(),
            'telegram_bot_token': self.telegram_bot_token_input.text().strip(),
            'telegram_chat_id': self.telegram_chat_id_input.text().strip(),
        }
    
    def set_settings(self, settings: dict):
        """
        تعيين الإعدادات - Set settings
        
        Args:
            settings: Dictionary containing settings to apply
        """
        if 'validate_videos' in settings:
            self.validate_videos_checkbox.setChecked(settings['validate_videos'])
        if 'internet_check_enabled' in settings:
            self.internet_check_checkbox.setChecked(settings['internet_check_enabled'])
        if 'telegram_enabled' in settings:
            self.telegram_enabled_checkbox.setChecked(settings['telegram_enabled'])
        if 'telegram_notify_success' in settings:
            self.telegram_notify_success_checkbox.setChecked(settings['telegram_notify_success'])
        if 'telegram_notify_errors' in settings:
            self.telegram_notify_errors_checkbox.setChecked(settings['telegram_notify_errors'])
        if 'telegram_bot_token' in settings:
            self.telegram_bot_token_input.setText(settings['telegram_bot_token'])
        if 'telegram_chat_id' in settings:
            self.telegram_chat_id_input.setText(settings['telegram_chat_id'])
    
    def update_telegram_status(self, success: bool, message: str):
        """
        تحديث حالة Telegram - Update Telegram status
        
        Args:
            success: Whether the test was successful
            message: Status message to display
        """
        if success:
            self.telegram_status_label.setText(f'✅ {message}')
            self.telegram_status_label.setStyleSheet('color: #4CAF50;')
        else:
            self.telegram_status_label.setText(f'❌ {message}')
            self.telegram_status_label.setStyleSheet('color: #F44336;')
