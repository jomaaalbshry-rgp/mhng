"""
نافذة إدارة قوالب الجداول - Schedule Templates Dialog
Dialog window for managing schedule templates
"""

from datetime import datetime

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QLineEdit,
    QTimeEdit, QCheckBox, QDialogButtonBox, QMessageBox
)

# استيراد من services
from services import (
    get_all_templates, save_template, 
    delete_template, set_default_template
)
# استيراد ALL_WEEKDAYS_STR مباشرة (غير مصدر من services/__init__.py)
from services.data_access import ALL_WEEKDAYS_STR

# استيراد من ui.widgets
from ui.widgets import NoScrollSpinBox


class ScheduleTemplatesDialog(QDialog):
    """نافذة إدارة قوالب الجداول الذكية."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('📋 قوالب الجداول')
        self.setMinimumSize(650, 550)
        self._templates = []
        self._editing_template_id = None
        self._times_list = []  # قائمة الأوقات المضافة
        self._build_ui()
        self._load_templates()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # قسم القوالب المحفوظة
        templates_group = QGroupBox('📋 القوالب المحفوظة')
        templates_layout = QVBoxLayout()

        # قائمة القوالب
        self.templates_list = QListWidget()
        self.templates_list.setMinimumHeight(150)
        self.templates_list.setStyleSheet('''
            QListWidget::item {
                padding: 8px;
                margin: 2px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        ''')
        self.templates_list.itemDoubleClicked.connect(self._edit_template)
        templates_layout.addWidget(self.templates_list)

        # أزرار التحكم
        btns_row = QHBoxLayout()

        edit_btn = QPushButton('✏️ تعديل')
        edit_btn.clicked.connect(self._edit_template)
        btns_row.addWidget(edit_btn)

        delete_btn = QPushButton('🗑️ حذف')
        delete_btn.clicked.connect(self._delete_template)
        btns_row.addWidget(delete_btn)

        set_default_btn = QPushButton('⭐ تعيين كافتراضي')
        set_default_btn.clicked.connect(self._set_as_default)
        btns_row.addWidget(set_default_btn)

        btns_row.addStretch()
        templates_layout.addLayout(btns_row)

        templates_group.setLayout(templates_layout)
        layout.addWidget(templates_group)

        # قسم إضافة/تعديل قالب
        edit_group = QGroupBox('➕ إضافة/تعديل قالب')
        edit_form = QFormLayout()

        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText('مثال: جدول صباحي')
        edit_form.addRow('اسم القالب:', self.template_name_input)

        # قائمة الأوقات
        times_row = QHBoxLayout()
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat('hh:mm AP')
        self.time_edit.setTime(QTime.fromString('08:00', 'HH:mm'))
        times_row.addWidget(self.time_edit)

        add_time_btn = QPushButton('➕ إضافة وقت')
        add_time_btn.clicked.connect(self._add_time)
        times_row.addWidget(add_time_btn)

        times_row.addStretch()
        edit_form.addRow('الأوقات:', times_row)

        # عرض الأوقات المضافة
        self.times_display = QLabel('لم تتم إضافة أوقات')
        self.times_display.setStyleSheet('color: #7f8c8d; padding: 5px;')
        edit_form.addRow('', self.times_display)

        # زر مسح الأوقات
        clear_times_btn = QPushButton('🗑️ مسح الأوقات')
        clear_times_btn.clicked.connect(self._clear_times)
        edit_form.addRow('', clear_times_btn)

        # أيام الأسبوع
        days_row = QHBoxLayout()
        self.day_checkboxes = []
        days_names = ['السبت', 'الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
        for i, day_name in enumerate(days_names):
            cb = QCheckBox(day_name)
            cb.setChecked(True)
            self.day_checkboxes.append(cb)
            days_row.addWidget(cb)
        days_row.addStretch()
        edit_form.addRow('الأيام:', days_row)

        # التوزيع العشوائي
        self.random_offset_spin = NoScrollSpinBox()
        self.random_offset_spin.setRange(0, 60)
        self.random_offset_spin.setValue(15)
        self.random_offset_spin.setSuffix(' دقيقة')
        edit_form.addRow('توزيع عشوائي (±):', self.random_offset_spin)

        # أزرار الحفظ
        save_btns_row = QHBoxLayout()
        save_btn = QPushButton('💾 حفظ القالب')
        save_btn.clicked.connect(self._save_template)
        save_btns_row.addWidget(save_btn)

        new_btn = QPushButton('🆕 قالب جديد')
        new_btn.clicked.connect(self._new_template)
        save_btns_row.addWidget(new_btn)

        save_btns_row.addStretch()
        edit_form.addRow('', save_btns_row)

        edit_group.setLayout(edit_form)
        layout.addWidget(edit_group)

        # أزرار الحوار
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_templates(self):
        """تحميل القوالب من قاعدة البيانات."""
        self._templates = get_all_templates()
        self._refresh_list()

    def _refresh_list(self):
        """تحديث قائمة القوالب."""
        self.templates_list.clear()

        for template in self._templates:
            name = template['name']
            times = template['times']
            is_default = template['is_default']

            # عرض الأوقات
            times_str = ', '.join(times) if times else 'بدون أوقات'
            if len(times_str) > 40:
                times_str = times_str[:37] + '...'

            icon = '⭐' if is_default else '📋'
            text = f'{icon} {name} │ {times_str}'

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, template)
            self.templates_list.addItem(item)

    def _add_time(self):
        """إضافة وقت جديد."""
        time_str = self.time_edit.time().toString('HH:mm')
        if time_str not in self._times_list:
            self._times_list.append(time_str)
            self._times_list.sort()
            self._update_times_display()

    def _clear_times(self):
        """مسح جميع الأوقات."""
        self._times_list = []
        self._update_times_display()

    def _update_times_display(self):
        """تحديث عرض الأوقات."""
        if self._times_list:
            # تحويل الأوقات لنظام 12 ساعة
            formatted_times = []
            for t in self._times_list:
                try:
                    formatted = datetime.strptime(t, '%H:%M').strftime('%I:%M %p')
                    formatted_times.append(formatted)
                except Exception:
                    formatted_times.append(t)
            self.times_display.setText('⏰ ' + ', '.join(formatted_times))
            self.times_display.setStyleSheet('color: #27ae60; padding: 5px; font-weight: bold;')
        else:
            self.times_display.setText('لم تتم إضافة أوقات')
            self.times_display.setStyleSheet('color: #7f8c8d; padding: 5px;')

    def _new_template(self):
        """إعداد نموذج قالب جديد."""
        self._editing_template_id = None
        self.template_name_input.clear()
        self._times_list = []
        self._update_times_display()
        for cb in self.day_checkboxes:
            cb.setChecked(True)
        self.random_offset_spin.setValue(15)

    def _edit_template(self):
        """تعديل القالب المحدد."""
        items = self.templates_list.selectedItems()
        if not items:
            QMessageBox.warning(self, 'خطأ', 'اختر قالباً للتعديل')
            return

        template = items[0].data(Qt.UserRole)
        self._editing_template_id = template['id']
        self.template_name_input.setText(template['name'])
        self._times_list = list(template['times'])
        self._update_times_display()

        # تحديث أيام الأسبوع - التعامل مع كلا الصيغتين (نصية أو رقمية)
        days = template.get('days', ALL_WEEKDAYS_STR)
        for i, cb in enumerate(self.day_checkboxes):
            day_str = ALL_WEEKDAYS_STR[i]  # صيغة نصية مثل "sat", "sun"
            # التحقق من وجود اليوم سواء بصيغة نصية أو رقمية
            cb.setChecked(day_str in days or i in days)

        self.random_offset_spin.setValue(template.get('random_offset', 15))

    def _delete_template(self):
        """حذف القالب المحدد."""
        items = self.templates_list.selectedItems()
        if not items:
            QMessageBox.warning(self, 'خطأ', 'اختر قالباً للحذف')
            return

        template = items[0].data(Qt.UserRole)

        if template['is_default']:
            QMessageBox.warning(self, 'خطأ', 'لا يمكن حذف القالب الافتراضي')
            return

        reply = QMessageBox.question(
            self, 'تأكيد الحذف',
            f'هل تريد حذف قالب "{template["name"]}"؟',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if delete_template(template['id']):
                self._load_templates()
                self._new_template()
            else:
                QMessageBox.warning(self, 'خطأ', 'فشل حذف القالب')

    def _set_as_default(self):
        """تعيين القالب المحدد كافتراضي."""
        items = self.templates_list.selectedItems()
        if not items:
            QMessageBox.warning(self, 'خطأ', 'اختر قالباً لتعيينه كافتراضي')
            return

        template = items[0].data(Qt.UserRole)
        if set_default_template(template['id']):
            self._load_templates()
            QMessageBox.information(self, 'نجاح', f'تم تعيين "{template["name"]}" كقالب افتراضي')
        else:
            QMessageBox.warning(self, 'خطأ', 'فشل تعيين القالب كافتراضي')

    def _save_template(self):
        """حفظ القالب الحالي."""
        name = self.template_name_input.text().strip()

        if not name:
            QMessageBox.warning(self, 'خطأ', 'أدخل اسم القالب')
            return

        if not self._times_list:
            QMessageBox.warning(self, 'خطأ', 'أضف وقتاً واحداً على الأقل')
            return

        # جمع الأيام المحددة - تحويل الفهارس إلى صيغة نصية
        # ترتيب الأيام: 0=sat, 1=sun, 2=mon, 3=tue, 4=wed, 5=thu, 6=fri
        day_indices = [i for i, cb in enumerate(self.day_checkboxes) if cb.isChecked()]
        days = [ALL_WEEKDAYS_STR[i] for i in day_indices]
        if not days:
            QMessageBox.warning(self, 'خطأ', 'اختر يوماً واحداً على الأقل')
            return

        random_offset = self.random_offset_spin.value()

        success, error_type = save_template(name, self._times_list, days, random_offset, self._editing_template_id)
        if success:
            self._load_templates()
            self._new_template()
            QMessageBox.information(self, 'نجاح', 'تم حفظ القالب بنجاح')
        else:
            # عرض رسالة خطأ مناسبة حسب نوع الخطأ
            error_messages = {
                'validation_error': 'المدخلات غير صالحة - تأكد من إدخال اسم القالب والأوقات',
                'duplicate_name': 'الاسم مستخدم مسبقاً - اختر اسماً مختلفاً',
                'table_error': 'خطأ في قاعدة البيانات - تعذر إنشاء جدول القوالب',
                'database_error': 'خطأ في قاعدة البيانات - قد يكون هناك عدم توافق في هيكل الجدول. يرجى إعادة تشغيل التطبيق',
                'not_found': 'لم يتم العثور على القالب للتحديث',
                'unexpected_error': 'خطأ غير متوقع - يرجى المحاولة لاحقاً'
            }
            error_msg = error_messages.get(error_type, 'فشل حفظ القالب - يرجى المحاولة لاحقاً')
            QMessageBox.warning(self, 'خطأ', error_msg)
