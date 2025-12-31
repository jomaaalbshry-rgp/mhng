"""
Hashtag Manager Dialog for Page Management Application

This module provides the HashtagManagerDialog class for managing
saved hashtag groups that can be reused across posts.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QTextEdit, QPushButton, QListWidget, 
    QListWidgetItem, QDialogButtonBox, QMessageBox, QComboBox
)


class HashtagManagerDialog(QDialog):
    """
    نافذة مدير الهاشتاجات.
    
    This dialog supports dependency injection for better testability and flexibility.
    If dependencies are not provided, it will use standard Qt widgets as fallback.
    
    Note: The constructor intentionally accepts many parameters for dependency injection.
    This design allows for easy testing and customization. For simpler usage, a factory
    function or builder pattern could be added in the future.
    
    Args:
        parent: Parent widget
        create_icon_button: Function to create buttons with icons (optional)
        get_icon: Function to get icons (optional)
        HAS_QTAWESOME: Whether qtawesome is available (optional)
        ICONS: Icon definitions dictionary (optional)
        ICON_COLORS: Icon color definitions dictionary (optional)
        get_hashtag_groups: Function to retrieve hashtag groups (required)
        save_hashtag_group: Function to save hashtag groups (required)
        delete_hashtag_group: Function to delete hashtag groups (required)
        NoScrollComboBox: Custom ComboBox class (optional, uses QComboBox if not provided)
    """
    
    def __init__(self, parent=None, create_icon_button=None, get_icon=None, 
                 HAS_QTAWESOME=False, ICONS=None, ICON_COLORS=None,
                 get_hashtag_groups=None, save_hashtag_group=None, 
                 delete_hashtag_group=None, NoScrollComboBox=None):
        super().__init__(parent)
        self.setWindowTitle('مدير الهاشتاجات')
        self.setMinimumSize(500, 450)
        self._selected_hashtags = ''
        self._editing_group_name = None  # اسم المجموعة قيد التعديل
        
        # Store injected dependencies with defaults
        self._create_icon_button = create_icon_button or self._create_default_button
        self._get_icon = get_icon
        self._HAS_QTAWESOME = HAS_QTAWESOME
        self._ICONS = ICONS or {}
        self._ICON_COLORS = ICON_COLORS or {}
        self._get_hashtag_groups = get_hashtag_groups
        self._save_hashtag_group = save_hashtag_group
        self._delete_hashtag_group = delete_hashtag_group
        self._NoScrollComboBox = NoScrollComboBox or QComboBox
        
        self._build_ui()
        self._load_groups()
    
    def _create_default_button(self, text: str, icon_key: str = None) -> QPushButton:
        """Create a default button without icons."""
        return QPushButton(text)
    
    def _can_use_icons(self) -> bool:
        """Check if icon support is available."""
        return self._HAS_QTAWESOME and self._get_icon and self._ICONS
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # قسم تعديل مجموعة موجودة
        edit_group = QGroupBox('تعديل مجموعة محفوظة')
        edit_layout = QVBoxLayout()
        
        # ComboBox لاختيار المجموعة
        select_row = QHBoxLayout()
        select_row.addWidget(QLabel('اختر مجموعة:'))
        self.groups_combo = self._NoScrollComboBox()
        self.groups_combo.currentIndexChanged.connect(self._on_combo_selection_changed)
        select_row.addWidget(self.groups_combo, 1)
        
        # زر تحميل للتعديل
        load_btn = self._create_icon_button('تحميل للتعديل', 'refresh')
        load_btn.clicked.connect(self._load_for_edit)
        select_row.addWidget(load_btn)
        
        edit_layout.addLayout(select_row)
        edit_group.setLayout(edit_layout)
        layout.addWidget(edit_group)
        
        # قسم إنشاء/تعديل مجموعة
        self.form_group = QGroupBox('إنشاء مجموعة جديدة')
        new_form = QFormLayout()
        
        self.group_name_input = QLineEdit()
        self.group_name_input.setPlaceholderText('اسم المجموعة (مثلاً: كوميديا)')
        new_form.addRow('الاسم:', self.group_name_input)
        
        self.hashtags_input = QTextEdit()
        self.hashtags_input.setPlaceholderText('أدخل الهاشتاجات مفصولة بمسافة أو سطر جديد\nمثال: #مضحك #كوميديا #ضحك')
        self.hashtags_input.setMaximumHeight(80)
        new_form.addRow('الهاشتاجات:', self.hashtags_input)
        
        # صف أزرار الحفظ والإلغاء
        buttons_row = QHBoxLayout()
        self.save_btn = self._create_icon_button('حفظ المجموعة', 'save')
        self.save_btn.clicked.connect(self._save_group)
        buttons_row.addWidget(self.save_btn)
        
        self.cancel_edit_btn = self._create_icon_button('إلغاء التعديل', 'close')
        self.cancel_edit_btn.clicked.connect(self._cancel_edit)
        self.cancel_edit_btn.setVisible(False)
        buttons_row.addWidget(self.cancel_edit_btn)
        
        new_form.addRow(buttons_row)
        
        self.form_group.setLayout(new_form)
        layout.addWidget(self.form_group)
        
        # قسم المجموعات المحفوظة
        saved_group = QGroupBox('المجموعات المحفوظة')
        saved_layout = QVBoxLayout()
        
        self.groups_list = QListWidget()
        self.groups_list.itemDoubleClicked.connect(self._on_group_selected)
        saved_layout.addWidget(self.groups_list)
        
        btns_row = QHBoxLayout()
        use_btn = self._create_icon_button('استخدام', 'check')
        use_btn.setToolTip('استخدام المجموعة المحددة')
        use_btn.clicked.connect(self._use_selected_group)
        btns_row.addWidget(use_btn)
        
        delete_btn = self._create_icon_button('حذف', 'delete')
        delete_btn.setToolTip('حذف المجموعة المحددة')
        delete_btn.clicked.connect(self._delete_selected_group)
        btns_row.addWidget(delete_btn)
        saved_layout.addLayout(btns_row)
        
        saved_group.setLayout(saved_layout)
        layout.addWidget(saved_group)
        
        # أزرار الحوار
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_groups(self):
        """تحميل المجموعات من قاعدة البيانات."""
        if not self._get_hashtag_groups:
            return
            
        self.groups_list.clear()
        self.groups_combo.clear()
        self.groups_combo.addItem('-- اختر مجموعة --', None)
        
        groups = self._get_hashtag_groups()
        for name, hashtags in groups:
            # إضافة للقائمة
            item = QListWidgetItem(f'{name}: {hashtags[:50]}...' if len(hashtags) > 50 else f'{name}: {hashtags}')
            item.setData(Qt.UserRole, {'name': name, 'hashtags': hashtags})
            self.groups_list.addItem(item)
            
            # إضافة للـ ComboBox
            self.groups_combo.addItem(name, {'name': name, 'hashtags': hashtags})
    
    def _on_combo_selection_changed(self, index):
        """معالج تغيير اختيار ComboBox."""
        # لا نفعل شيء هنا، سيتم التحميل عند الضغط على زر "تحميل للتعديل"
        pass
    
    def _load_for_edit(self):
        """تحميل المجموعة المختارة للتعديل."""
        data = self.groups_combo.currentData()
        if not data:
            QMessageBox.warning(self, 'تنبيه', 'اختر مجموعة من القائمة أولاً')
            return
        
        # تحميل البيانات في حقول الإدخال
        self._editing_group_name = data['name']
        self.group_name_input.setText(data['name'])
        self.group_name_input.setReadOnly(True)  # منع تغيير الاسم في وضع التعديل
        # إضافة مؤشر بصري لحقل الاسم في وضع القراءة فقط
        self.group_name_input.setStyleSheet('background-color: #e8e8e8; color: #666;')
        self.hashtags_input.setText(data['hashtags'])
        
        # تحديث عنوان المجموعة والأزرار
        self.form_group.setTitle(f'تعديل المجموعة: {data["name"]}')
        self.save_btn.setText('حفظ التعديلات')
        if self._can_use_icons():
            self.save_btn.setIcon(self._get_icon(self._ICONS['save'], self._ICON_COLORS.get('save')))
        self.cancel_edit_btn.setVisible(True)
    
    def _cancel_edit(self):
        """إلغاء وضع التعديل والعودة لوضع الإنشاء."""
        self._editing_group_name = None
        self.group_name_input.clear()
        self.group_name_input.setReadOnly(False)
        # إزالة المؤشر البصري
        self.group_name_input.setStyleSheet('')
        self.hashtags_input.clear()
        self.form_group.setTitle('إنشاء مجموعة جديدة')
        self.save_btn.setText('حفظ المجموعة')
        if self._can_use_icons():
            self.save_btn.setIcon(self._get_icon(self._ICONS['save'], self._ICON_COLORS.get('save')))
        self.cancel_edit_btn.setVisible(False)
        self.groups_combo.setCurrentIndex(0)
    
    def _save_group(self):
        """حفظ أو تحديث مجموعة."""
        if not self._save_hashtag_group:
            return
            
        name = self.group_name_input.text().strip()
        hashtags = self.hashtags_input.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, 'خطأ', 'أدخل اسم المجموعة')
            return
        
        if not hashtags:
            QMessageBox.warning(self, 'خطأ', 'أدخل الهاشتاجات')
            return
        
        # حفظ أو تحديث المجموعة
        self._save_hashtag_group(name, hashtags)
        
        # رسالة النجاح
        if self._editing_group_name:
            QMessageBox.information(self, 'تم', f'تم تحديث المجموعة "{name}" بنجاح')
        else:
            QMessageBox.information(self, 'تم', f'تم حفظ المجموعة "{name}" بنجاح')
        
        # إعادة تحميل المجموعات وتنظيف النموذج
        self._load_groups()
        self._cancel_edit()
    
    def _on_group_selected(self, item):
        """معالج النقر المزدوج على مجموعة."""
        data = item.data(Qt.UserRole)
        if data:
            self._selected_hashtags = data['hashtags']
            self.accept()
    
    def _use_selected_group(self):
        """استخدام المجموعة المحددة."""
        items = self.groups_list.selectedItems()
        if not items:
            QMessageBox.warning(self, 'خطأ', 'اختر مجموعة أولاً')
            return
        
        data = items[0].data(Qt.UserRole)
        if data:
            self._selected_hashtags = data['hashtags']
            self.accept()
    
    def _delete_selected_group(self):
        """حذف المجموعة المحددة."""
        if not self._delete_hashtag_group:
            return
            
        items = self.groups_list.selectedItems()
        if not items:
            QMessageBox.warning(self, 'خطأ', 'اختر مجموعة أولاً')
            return
        
        data = items[0].data(Qt.UserRole)
        if data:
            reply = QMessageBox.question(
                self, 'تأكيد الحذف',
                f'هل تريد حذف المجموعة "{data["name"]}"؟',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._delete_hashtag_group(data['name'])
                self._load_groups()
    
    def get_selected_hashtags(self) -> str:
        """الحصول على الهاشتاجات المختارة."""
        return self._selected_hashtags
