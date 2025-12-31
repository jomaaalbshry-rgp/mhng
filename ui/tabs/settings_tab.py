"""
Settings Tab - تبويب الإعدادات
Contains all settings UI elements and their layout.
"""

import threading
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)

from core import (
    TelegramNotifier,
    check_for_updates, get_installed_versions,
    UPDATE_PACKAGES
)
from ui.helpers import (
    create_icon_button, get_icon,
    ICONS, ICON_COLORS, HAS_QTAWESOME
)


# Color constants for update status
COUNTDOWN_COLOR_GREEN = '#27ae60'   # أخضر
COUNTDOWN_COLOR_YELLOW = '#f39c12'  # أصفر


class SettingsTab(QWidget):
    """
    تبويب الإعدادات
    Settings tab widget containing all application settings.
    """
    
    # Signals
    settings_changed = Signal()
    log_message = Signal(str)
    telegram_test_result = Signal(bool, str)
    update_check_finished = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Settings values
        self.validate_videos = True
        self.internet_check_enabled = True
        self.telegram_enabled = False
        self.telegram_bot_token = ''
        self.telegram_chat_id = ''
        self.telegram_notify_success = True
        self.telegram_notify_errors = True
        
        # Update tracking
        self._available_updates = []
        self._update_check_result = {}
        
        # Telegram notifier reference (will be set from parent)
        self.telegram_notifier = None
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """بناء واجهة الإعدادات"""
        layout = QVBoxLayout(self)
        
        # مجموعة التحقق من الفيديو
        validation_group = self._build_validation_settings()
        layout.addWidget(validation_group)
        
        # مجموعة فحص الاتصال بالإنترنت
        internet_group = self._build_internet_settings()
        layout.addWidget(internet_group)
        
        # مجموعة إشعارات Telegram
        telegram_group = self._build_telegram_settings()
        layout.addWidget(telegram_group)
        
        # مجموعة تحديث المكتبات
        updates_group = self._build_updates_settings()
        layout.addWidget(updates_group)
        
        # زر حفظ الإعدادات
        save_settings_btn = create_icon_button('حفظ الإعدادات', 'save')
        save_settings_btn.clicked.connect(self._on_save_clicked)
        layout.addWidget(save_settings_btn)
        
        layout.addStretch()
    
    def _build_validation_settings(self) -> QGroupBox:
        """بناء مجموعة التحقق من صحة الفيديو"""
        validation_group = QGroupBox('التحقق من صحة الفيديو')
        if HAS_QTAWESOME:
            validation_group.setTitle('')
        validation_form = QFormLayout()
        
        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            val_title_row = QHBoxLayout()
            val_icon_label = QLabel()
            val_icon_label.setPixmap(get_icon(ICONS['warning'], ICON_COLORS.get('warning')).pixmap(16, 16))
            val_title_row.addWidget(val_icon_label)
            val_title_row.addWidget(QLabel('التحقق من صحة الفيديو'))
            val_title_row.addStretch()
            validation_form.addRow(val_title_row)
        
        self.validate_videos_checkbox = QCheckBox('التحقق من الفيديوهات قبل الرفع')
        self.validate_videos_checkbox.setChecked(self.validate_videos)
        self.validate_videos_checkbox.setToolTip('فحص ملفات الفيديو للتأكد من صلاحيتها قبل محاولة الرفع')
        validation_form.addRow(self.validate_videos_checkbox)
        
        validation_group.setLayout(validation_form)
        return validation_group
    
    def _build_internet_settings(self) -> QGroupBox:
        """بناء مجموعة فحص الاتصال بالإنترنت"""
        internet_group = QGroupBox('فحص الاتصال بالإنترنت')
        if HAS_QTAWESOME:
            internet_group.setTitle('')
        internet_form = QFormLayout()
        
        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            net_title_row = QHBoxLayout()
            net_icon_label = QLabel()
            net_icon_label.setPixmap(get_icon(ICONS['network'], ICON_COLORS.get('network')).pixmap(16, 16))
            net_title_row.addWidget(net_icon_label)
            net_title_row.addWidget(QLabel('فحص الاتصال بالإنترنت'))
            net_title_row.addStretch()
            internet_form.addRow(net_title_row)
        
        self.internet_check_checkbox = QCheckBox('فحص الاتصال قبل كل عملية رفع')
        if HAS_QTAWESOME:
            self.internet_check_checkbox.setIcon(get_icon(ICONS['network'], ICON_COLORS.get('network')))
        self.internet_check_checkbox.setChecked(self.internet_check_enabled)
        self.internet_check_checkbox.setToolTip('عند تفعيل هذا الخيار، سيتحقق البرنامج من الاتصال بالإنترنت قبل كل رفع.\nإذا انقطع الاتصال، سيدخل في وضع الغفوة ويعيد المحاولة كل دقيقة حتى يعود الاتصال.')
        internet_form.addRow(self.internet_check_checkbox)
        
        internet_group.setLayout(internet_form)
        return internet_group
    
    def _build_telegram_settings(self) -> QGroupBox:
        """بناء مجموعة إشعارات Telegram"""
        telegram_group = QGroupBox('إشعارات Telegram')
        if HAS_QTAWESOME:
            telegram_group.setTitle('')
        telegram_layout = QVBoxLayout()
        
        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            tg_title_row = QHBoxLayout()
            tg_icon_label = QLabel()
            tg_icon_label.setPixmap(get_icon(ICONS['telegram'], ICON_COLORS.get('telegram')).pixmap(16, 16))
            tg_title_row.addWidget(tg_icon_label)
            tg_title_row.addWidget(QLabel('إشعارات Telegram Bot'))
            tg_title_row.addStretch()
            telegram_layout.addLayout(tg_title_row)
        
        # تفعيل الإشعارات
        self.telegram_enabled_checkbox = QCheckBox('تفعيل إشعارات Telegram')
        self.telegram_enabled_checkbox.setChecked(self.telegram_enabled)
        self.telegram_enabled_checkbox.setToolTip('إرسال إشعارات عند نجاح أو فشل رفع الفيديو عبر Telegram Bot')
        telegram_layout.addWidget(self.telegram_enabled_checkbox)
        
        # خيارات أنواع الإشعارات
        notify_options_layout = QVBoxLayout()
        notify_options_layout.setContentsMargins(20, 5, 0, 5)  # إزاحة للداخل
        
        # خيار إرسال إشعارات النجاح
        self.telegram_notify_success_checkbox = QCheckBox('إرسال إشعارات نجاح الرفع ✅')
        self.telegram_notify_success_checkbox.setChecked(self.telegram_notify_success)
        self.telegram_notify_success_checkbox.setToolTip('إرسال إشعار عند نجاح رفع فيديو أو ستوري أو ريلز')
        notify_options_layout.addWidget(self.telegram_notify_success_checkbox)
        
        # خيار إرسال إشعارات الأخطاء
        self.telegram_notify_errors_checkbox = QCheckBox('إرسال إشعارات الأخطاء والفشل ❌')
        self.telegram_notify_errors_checkbox.setChecked(self.telegram_notify_errors)
        self.telegram_notify_errors_checkbox.setToolTip('إرسال إشعار عند فشل الرفع أو حدوث أي خطأ في البرنامج')
        notify_options_layout.addWidget(self.telegram_notify_errors_checkbox)
        
        telegram_layout.addLayout(notify_options_layout)
        
        # حقول الإعدادات
        telegram_form = QFormLayout()
        
        # توكن البوت
        self.telegram_bot_token_input = QLineEdit()
        self.telegram_bot_token_input.setPlaceholderText('أدخل توكن البوت من @BotFather')
        self.telegram_bot_token_input.setText(self.telegram_bot_token)
        self.telegram_bot_token_input.setEchoMode(QLineEdit.Password)
        telegram_form.addRow('توكن البوت:', self.telegram_bot_token_input)
        
        # معرّف المحادثة
        self.telegram_chat_id_input = QLineEdit()
        self.telegram_chat_id_input.setPlaceholderText('معرّف المحادثة أو القناة (مثل: -1001234567890)')
        self.telegram_chat_id_input.setText(self.telegram_chat_id)
        telegram_form.addRow('معرّف المحادثة:', self.telegram_chat_id_input)
        
        telegram_layout.addLayout(telegram_form)
        
        # صف أزرار Telegram
        telegram_buttons_row = QHBoxLayout()
        
        # زر اختبار الاتصال
        self.telegram_test_btn = create_icon_button('اختبار الاتصال', 'telegram')
        self.telegram_test_btn.clicked.connect(self._test_telegram_connection)
        telegram_buttons_row.addWidget(self.telegram_test_btn)
        
        # تعليمات الحصول على التوكن
        telegram_help_btn = create_icon_button('كيفية الإعداد؟', 'info')
        telegram_help_btn.clicked.connect(self._show_telegram_help)
        telegram_buttons_row.addWidget(telegram_help_btn)
        
        telegram_layout.addLayout(telegram_buttons_row)
        
        # رسالة الحالة
        self.telegram_status_label = QLabel('')
        self.telegram_status_label.setAlignment(Qt.AlignCenter)
        self.telegram_status_label.setWordWrap(True)
        telegram_layout.addWidget(self.telegram_status_label)
        
        telegram_group.setLayout(telegram_layout)
        return telegram_group
    
    def _build_updates_settings(self) -> QGroupBox:
        """بناء مجموعة تحديث المكتبات"""
        updates_group = QGroupBox('تحديث المكتبات')
        if HAS_QTAWESOME:
            updates_group.setTitle('')
        updates_layout = QVBoxLayout()
        
        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            updates_title_row = QHBoxLayout()
            updates_icon_label = QLabel()
            updates_icon_label.setPixmap(get_icon(ICONS['update'], ICON_COLORS.get('update')).pixmap(16, 16))
            updates_title_row.addWidget(updates_icon_label)
            updates_title_row.addWidget(QLabel('تحديث المكتبات'))
            updates_title_row.addStretch()
            updates_layout.addLayout(updates_title_row)
        
        # جدول المكتبات
        self.updates_table = QTableWidget()
        self.updates_table.setColumnCount(4)
        self.updates_table.setHorizontalHeaderLabels(['المكتبة', 'الحالي', 'المتاح', 'الحالة'])
        self.updates_table.horizontalHeader().setStretchLastSection(True)
        self.updates_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.updates_table.setMaximumHeight(150)
        updates_layout.addWidget(self.updates_table)
        
        # رسالة الحالة
        self.update_status_label = QLabel('اضغط على "البحث عن تحديثات" للتحقق')
        self.update_status_label.setAlignment(Qt.AlignCenter)
        updates_layout.addWidget(self.update_status_label)
        
        # أزرار التحديث
        update_buttons_row = QHBoxLayout()
        
        self.check_updates_btn = create_icon_button('البحث عن تحديثات', 'search')
        self.check_updates_btn.clicked.connect(self._check_for_updates)
        update_buttons_row.addWidget(self.check_updates_btn)
        
        self.update_all_btn = create_icon_button('تحديث الكل', 'update', color=COUNTDOWN_COLOR_GREEN)
        self.update_all_btn.clicked.connect(self._on_update_requested)
        self.update_all_btn.setVisible(False)  # يظهر فقط عند وجود تحديثات
        self.update_all_btn.setStyleSheet(f'background-color: {COUNTDOWN_COLOR_GREEN}; color: white; font-weight: bold;')
        update_buttons_row.addWidget(self.update_all_btn)
        
        updates_layout.addLayout(update_buttons_row)
        updates_group.setLayout(updates_layout)
        
        return updates_group
    
    def _connect_signals(self):
        """ربط الإشارات"""
        self.telegram_test_result.connect(self._update_telegram_test_result)
        self.update_check_finished.connect(self._finish_update_check)
    
    def _on_save_clicked(self):
        """معالج نقر زر الحفظ"""
        self.validate_videos = self.validate_videos_checkbox.isChecked()
        self.internet_check_enabled = self.internet_check_checkbox.isChecked()
        self.telegram_enabled = self.telegram_enabled_checkbox.isChecked()
        self.telegram_bot_token = self.telegram_bot_token_input.text().strip()
        self.telegram_chat_id = self.telegram_chat_id_input.text().strip()
        self.telegram_notify_success = self.telegram_notify_success_checkbox.isChecked()
        self.telegram_notify_errors = self.telegram_notify_errors_checkbox.isChecked()
        
        # إرسال إشارة التغيير
        self.settings_changed.emit()
        self.log_message.emit('تم حفظ الإعدادات المتقدمة.')
    
    def _test_telegram_connection(self):
        """اختبار الاتصال بـ Telegram Bot."""
        bot_token = self.telegram_bot_token_input.text().strip()
        chat_id = self.telegram_chat_id_input.text().strip()
        
        if not bot_token or not chat_id:
            self.telegram_status_label.setText('❌ يرجى إدخال توكن البوت ومعرّف المحادثة')
            self.telegram_status_label.setStyleSheet('color: #F44336;')
            return
        
        self.telegram_test_btn.setEnabled(False)
        self.telegram_test_btn.setText('جاري الاختبار...')
        self.telegram_status_label.setText('⏳ جاري اختبار الاتصال...')
        self.telegram_status_label.setStyleSheet('')
        
        def test_worker():
            # إنشاء مثيل مؤقت للاختبار
            test_notifier = TelegramNotifier(bot_token, chat_id, enabled=True)
            success, message = test_notifier.test_connection()
            
            # استخدام Signal لضمان تحديث الواجهة من الخيط الرئيسي
            self.telegram_test_result.emit(success, message)
        
        threading.Thread(target=test_worker, daemon=True).start()
    
    def _update_telegram_test_result(self, success: bool, message: str):
        """تحديث نتيجة اختبار Telegram."""
        self.telegram_test_btn.setEnabled(True)
        self.telegram_test_btn.setText('اختبار الاتصال')
        if HAS_QTAWESOME:
            self.telegram_test_btn.setIcon(get_icon(ICONS['telegram'], ICON_COLORS.get('telegram')))
        
        if success:
            self.telegram_status_label.setText(f'✅ {message}')
            self.telegram_status_label.setStyleSheet('color: #4CAF50;')
            # Update settings after successful test
            self.telegram_bot_token = self.telegram_bot_token_input.text().strip()
            self.telegram_chat_id = self.telegram_chat_id_input.text().strip()
            self.telegram_enabled = self.telegram_enabled_checkbox.isChecked()
            self.telegram_notify_success = self.telegram_notify_success_checkbox.isChecked()
            self.telegram_notify_errors = self.telegram_notify_errors_checkbox.isChecked()
            # إرسال إشارة التغيير
            self.settings_changed.emit()
            self.log_message.emit('✅ تم حفظ إعدادات Telegram بنجاح بعد اختبار الاتصال')
        else:
            self.telegram_status_label.setText(f'❌ {message}')
            self.telegram_status_label.setStyleSheet('color: #F44336;')
            # إظهار نافذة منبثقة عند فشل الاتصال
            QMessageBox.warning(
                self,
                'فشل الاتصال بـ Telegram',
                f'لم يتم الاتصال بالبوت:\n\n{message}\n\n'
                'تأكد من:\n'
                '• صحة التوكن\n'
                '• صحة معرّف المحادثة\n'
                '• اتصالك بالإنترنت'
            )
    
    def _show_telegram_help(self):
        """عرض تعليمات إعداد Telegram Bot."""
        help_text = '''
<h3>كيفية إعداد إشعارات Telegram Bot</h3>

<h4>1. إنشاء بوت جديد:</h4>
<ol>
<li>افتح تطبيق Telegram وابحث عن <b>@BotFather</b></li>
<li>أرسل الأمر <code>/newbot</code></li>
<li>اختر اسماً للبوت (مثل: My Upload Notifier)</li>
<li>اختر username للبوت (يجب أن ينتهي بـ bot)</li>
<li>ستحصل على <b>توكن البوت</b> - انسخه</li>
</ol>

<h4>2. الحصول على معرّف المحادثة (Chat ID):</h4>
<p><b>للمحادثة الشخصية:</b></p>
<ol>
<li>ابحث عن <b>@userinfobot</b> في Telegram</li>
<li>اضغط Start</li>
<li>سيظهر لك الـ <b>Id</b> الخاص بك</li>
</ol>

<p><b>للمجموعة أو القناة:</b></p>
<ol>
<li>أضف البوت للمجموعة/القناة كمشرف</li>
<li>أرسل رسالة في المجموعة</li>
<li>افتح الرابط: <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code></li>
<li>ابحث عن "chat":{"id": وانسخ الرقم (يبدأ عادة بـ -100)</li>
</ol>

<h4>3. ملاحظات:</h4>
<ul>
<li>تأكد من بدء محادثة مع البوت أولاً (اضغط /start)</li>
<li>معرّف القنوات يبدأ عادة بـ <code>-100</code></li>
<li>يمكن استخدام @username بدلاً من الـ ID للقنوات العامة</li>
</ul>
'''
        QMessageBox.information(self, 'تعليمات Telegram Bot', help_text)
    
    def _check_for_updates(self):
        """التحقق من وجود تحديثات للمكتبات."""
        self.check_updates_btn.setEnabled(False)
        self.check_updates_btn.setText('جاري البحث...')
        self.update_status_label.setText('جاري التحقق من التحديثات...')
        self.updates_table.setRowCount(0)
        self.update_all_btn.setVisible(False)
        self._available_updates = []
        
        # استخدام متغير للتخزين المؤقت
        self._update_check_result = {'installed': {}, 'updates': [], 'error': None}
        
        def check_worker():
            try:
                self.log_message.emit('🔍 جاري التحقق من التحديثات...')
                
                # الحصول على الإصدارات المثبتة
                installed = get_installed_versions()
                self._update_check_result['installed'] = installed
                
                # الحصول على التحديثات المتاحة
                updates = check_for_updates(None)  # بدون log لتجنب مشاكل الخيوط
                self._update_check_result['updates'] = updates
                
                self.log_message.emit(f'✅ تم التحقق - وُجدت {len(updates)} تحديثات')
                
            except Exception as e:
                self._update_check_result['error'] = str(e)
                self.log_message.emit(f'❌ خطأ في التحقق: {e}')
            finally:
                # استخدام Signal لضمان تحديث الواجهة من الخيط الرئيسي
                self.update_check_finished.emit()
        
        threading.Thread(target=check_worker, daemon=True).start()
    
    def _finish_update_check(self):
        """إنهاء عملية التحقق من التحديثات وتحديث الواجهة."""
        try:
            result = getattr(self, '_update_check_result', {})
            
            if result.get('error'):
                self._handle_update_check_error(result['error'])
                return
            
            installed = result.get('installed', {})
            updates = result.get('updates', [])
            
            self._populate_updates_table(installed, updates)
            
        except Exception as e:
            self._handle_update_check_error(str(e))
    
    def _handle_update_check_error(self, error_msg: str):
        """معالجة خطأ التحقق من التحديثات."""
        self.check_updates_btn.setEnabled(True)
        self.check_updates_btn.setText('البحث عن تحديثات')
        if HAS_QTAWESOME:
            self.check_updates_btn.setIcon(get_icon(ICONS.get('search', 'fa5s.search'), ICON_COLORS.get('search')))
        self.update_status_label.setText(f'❌ خطأ في التحقق: {error_msg[:80]}')
        self.log_message.emit(f'❌ فشل التحقق من التحديثات: {error_msg}')
        
        # إظهار نافذة منبثقة للخطأ مع تفاصيل الخطأ
        error_detail = error_msg[:200] if len(error_msg) > 200 else error_msg
        QMessageBox.warning(
            self,
            '❌ خطأ في التحقق',
            f'تعذر التحقق من التحديثات.\nتأكد من اتصالك بالإنترنت.\n\nتفاصيل الخطأ:\n{error_detail}',
            QMessageBox.Ok
        )
    
    def _populate_updates_table(self, installed: dict, updates: list):
        """ملء جدول التحديثات بالبيانات."""
        try:
            # إنشاء قاموس التحديثات المتاحة
            updates_dict = {pkg[0].lower(): (pkg[1], pkg[2]) for pkg in updates}
            self._available_updates = [pkg[0] for pkg in updates]
            
            # ملء الجدول
            self.updates_table.setRowCount(len(UPDATE_PACKAGES))
            
            for row, pkg_name in enumerate(UPDATE_PACKAGES):
                # اسم المكتبة
                self.updates_table.setItem(row, 0, QTableWidgetItem(pkg_name))
                
                # الإصدار الحالي
                current_version = installed.get(pkg_name, 'غير مثبت')
                # البحث بغض النظر عن حالة الأحرف
                for key, value in installed.items():
                    if key.lower() == pkg_name.lower():
                        current_version = value
                        break
                self.updates_table.setItem(row, 1, QTableWidgetItem(current_version))
                
                # الإصدار المتاح والحالة
                if pkg_name.lower() in updates_dict:
                    _, latest_version = updates_dict[pkg_name.lower()]
                    self.updates_table.setItem(row, 2, QTableWidgetItem(latest_version))
                    status_item = QTableWidgetItem('تحديث متاح')
                    status_item.setForeground(QColor(COUNTDOWN_COLOR_YELLOW))  # أصفر/برتقالي
                    self.updates_table.setItem(row, 3, status_item)
                else:
                    self.updates_table.setItem(row, 2, QTableWidgetItem(current_version))
                    status_item = QTableWidgetItem('محدث')
                    status_item.setForeground(QColor(COUNTDOWN_COLOR_GREEN))  # أخضر
                    self.updates_table.setItem(row, 3, status_item)
            
            # تحديث رسالة الحالة وزر التحديث
            if updates:
                self.update_status_label.setText(f'⚠️ يوجد {len(updates)} تحديثات متاحة')
                self.update_all_btn.setVisible(True)
            else:
                self.update_status_label.setText('✅ جميع المكتبات محدثة - لا توجد تحديثات متاحة')
                self.update_all_btn.setVisible(False)
                
                # إظهار نافذة منبثقة عند عدم وجود تحديثات
                QMessageBox.information(
                    self,
                    '✅ لا توجد تحديثات',
                    'جميع المكتبات محدثة!\nأنت تستخدم أحدث الإصدارات.',
                    QMessageBox.Ok
                )
        except Exception as e:
            self.update_status_label.setText(f'❌ خطأ: {str(e)[:80]}')
        finally:
            # دائماً إعادة الزر للحالة الطبيعية
            self.check_updates_btn.setEnabled(True)
            self.check_updates_btn.setText('البحث عن تحديثات')
            if HAS_QTAWESOME:
                self.check_updates_btn.setIcon(get_icon(ICONS.get('search', 'fa5s.search'), ICON_COLORS.get('search')))
    
    def _on_update_requested(self):
        """Signal that updates are requested - parent will handle the actual update"""
        # This signal will be connected by the parent to trigger the actual update process
        pass
    
    # Getters and setters for settings values
    def get_settings(self) -> dict:
        """الحصول على جميع قيم الإعدادات"""
        return {
            'validate_videos': self.validate_videos,
            'internet_check_enabled': self.internet_check_enabled,
            'telegram_enabled': self.telegram_enabled,
            'telegram_bot_token': self.telegram_bot_token,
            'telegram_chat_id': self.telegram_chat_id,
            'telegram_notify_success': self.telegram_notify_success,
            'telegram_notify_errors': self.telegram_notify_errors,
        }
    
    def set_settings(self, settings: dict):
        """تعيين قيم الإعدادات"""
        self.validate_videos = settings.get('validate_videos', True)
        self.internet_check_enabled = settings.get('internet_check_enabled', True)
        self.telegram_enabled = settings.get('telegram_enabled', False)
        self.telegram_bot_token = settings.get('telegram_bot_token', '')
        self.telegram_chat_id = settings.get('telegram_chat_id', '')
        self.telegram_notify_success = settings.get('telegram_notify_success', True)
        self.telegram_notify_errors = settings.get('telegram_notify_errors', True)
        
        # Update UI
        self.validate_videos_checkbox.setChecked(self.validate_videos)
        self.internet_check_checkbox.setChecked(self.internet_check_enabled)
        self.telegram_enabled_checkbox.setChecked(self.telegram_enabled)
        self.telegram_bot_token_input.setText(self.telegram_bot_token)
        self.telegram_chat_id_input.setText(self.telegram_chat_id)
        self.telegram_notify_success_checkbox.setChecked(self.telegram_notify_success)
        self.telegram_notify_errors_checkbox.setChecked(self.telegram_notify_errors)
    
    def get_available_updates(self) -> list:
        """الحصول على قائمة التحديثات المتاحة"""
        return self._available_updates
