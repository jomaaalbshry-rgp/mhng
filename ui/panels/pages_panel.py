"""
لوحة إدارة الصفحات - Pages Management Panel
تحتوي على واجهة إدارة صفحات الفيسبوك
Contains the interface for managing Facebook pages
"""

import time
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox
)

from core import FetchPagesThread
from ui.helpers import get_icon, ICONS, ICON_COLORS, HAS_QTAWESOME


class PagesPanel(QWidget):
    """
    لوحة إدارة الصفحات - Pages Management Panel
    تحتوي على واجهة جلب وعرض صفحات الفيسبوك
    """
    
    # Signals للتواصل مع MainWindow
    page_selected = Signal(dict)  # عند اختيار صفحة - يرسل بيانات الصفحة
    pages_refreshed = Signal(list)  # عند تحديث قائمة الصفحات - يرسل قائمة الصفحات
    log_message = Signal(str)  # لإرسال رسائل السجل
    token_management_requested = Signal()  # طلب فتح نافذة إدارة التوكينات
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Cache variables
        self._pages_cache = []
        self._pages_cache_grouped = {}
        self._pages_cache_time = 0
        self._pages_cache_duration = 300  # 5 minutes
        
        # Thread reference
        self._fetch_pages_thread = None
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """إنشاء واجهة المستخدم"""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        
        # أزرار التحكم العلوية
        top_controls = QHBoxLayout()
        
        # زر إدارة التوكينات
        self.manage_tokens_btn = QPushButton('🔑 إدارة التوكينات')
        self.manage_tokens_btn.setStyleSheet('''
            QPushButton {
                background: #9b59b6;
                color: white;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #8e44ad;
            }
        ''')
        top_controls.addWidget(self.manage_tokens_btn)
        
        # زر جلب الصفحات
        self.load_pages_btn = QPushButton('🔄 جلب الصفحات')
        self.load_pages_btn.setStyleSheet('''
            QPushButton {
                background: #3498db;
                color: white;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        ''')
        top_controls.addWidget(self.load_pages_btn)
        
        top_controls.addStretch()
        
        root.addLayout(top_controls)
        
        # فاصل
        separator = QWidget()
        separator.setFixedHeight(2)
        separator.setStyleSheet('background: #bdc3c7;')
        root.addWidget(separator)
        
        # عنوان القائمة
        root.addWidget(QLabel('الصفحات:'))
        
        # شجرة الصفحات - استخدام QTreeWidget لعرض الصفحات بشكل شجري مجمعة حسب التطبيق
        self.pages_tree = QTreeWidget()
        self.pages_tree.setHeaderLabels(['الصفحة / التطبيق', 'معرف الصفحة'])
        self.pages_tree.setColumnCount(2)
        self.pages_tree.setRootIsDecorated(True)
        self.pages_tree.setExpandsOnDoubleClick(True)
        self.pages_tree.setSelectionMode(QTreeWidget.SingleSelection)
        
        # تعيين عرض الأعمدة
        header = self.pages_tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        
        root.addWidget(self.pages_tree)
    
    def _connect_signals(self):
        """ربط الإشارات"""
        self.manage_tokens_btn.clicked.connect(self._on_manage_tokens_clicked)
        self.load_pages_btn.clicked.connect(self.load_pages)
        self.pages_tree.itemSelectionChanged.connect(self._on_page_selection_changed)
    
    def _on_manage_tokens_clicked(self):
        """معالج زر إدارة التوكينات"""
        self.token_management_requested.emit()
    
    def _on_page_selection_changed(self):
        """معالج تغيير اختيار الصفحة"""
        items = self.pages_tree.selectedItems()
        if not items:
            return
        
        # التحقق من أن العنصر المحدد صفحة وليس مجموعة
        page_data = items[0].data(0, Qt.UserRole)
        if not page_data or not isinstance(page_data, dict) or 'id' not in page_data:
            # العنصر المحدد ليس صفحة (قد يكون تطبيق أو عنصر خطأ)
            return
        
        # إرسال بيانات الصفحة المختارة
        self.page_selected.emit(page_data)
    
    def load_pages(self, apps_with_tokens):
        """
        جلب الصفحات باستخدام جميع التطبيقات المحفوظة.
        يتم جمع الصفحات من جميع التطبيقات وعرضها مجمعة حسب التطبيق.
        
        Args:
            apps_with_tokens: قائمة التطبيقات مع التوكينات
        """
        if not apps_with_tokens:
            QMessageBox.warning(
                self,
                'لا توجد توكينات',
                'لم يتم العثور على توكينات طويلة.\n\n'
                'اضغط على "إدارة التوكينات" لجلب توكن طويل.'
            )
            return
        
        # التحقق من الـ Cache
        now = time.time()
        if self._pages_cache and (now - self._pages_cache_time) < self._pages_cache_duration:
            self.log_message.emit('📋 تم استخدام الصفحات من الذاكرة المؤقتة')
            self._display_pages_grouped(self._pages_cache_grouped)
            return
        
        # التحقق من عدم وجود Thread يعمل بالفعل
        if self._fetch_pages_thread and self._fetch_pages_thread.isRunning():
            self.log_message.emit('⚠️ عملية جلب الصفحات قيد التنفيذ بالفعل')
            return
        
        self.log_message.emit(f'🔄 جاري جلب الصفحات من {len(apps_with_tokens)} تطبيق...')
        
        # تعطيل زر الجلب أثناء العملية
        self.load_pages_btn.setEnabled(False)
        self.load_pages_btn.setText('⏳ جاري الجلب...')
        
        # إنشاء Thread لجلب الصفحات
        self._fetch_pages_thread = FetchPagesThread(apps_with_tokens)
        
        # ربط إشارات الـ Thread
        self._fetch_pages_thread.pages_fetched.connect(self._on_fetch_pages_finished)
        self._fetch_pages_thread.error.connect(self._on_fetch_pages_error)
        self._fetch_pages_thread.progress.connect(lambda msg: self.log_message.emit(msg))
        self._fetch_pages_thread.finished.connect(self._cleanup_fetch_pages_thread)
        
        # بدء الـ Thread
        self._fetch_pages_thread.start()
    
    def _cleanup_fetch_pages_thread(self):
        """تنظيف مرجع الـ Thread بعد انتهائه فعلياً."""
        if self._fetch_pages_thread:
            self._fetch_pages_thread.wait()
            self._fetch_pages_thread = None
    
    def _on_fetch_pages_finished(self, result: dict):
        """معالج انتهاء جلب الصفحات بنجاح."""
        # إعادة تفعيل زر الجلب
        self.load_pages_btn.setEnabled(True)
        self.load_pages_btn.setText('🔄 جلب الصفحات')
        
        # تخزين النتيجة في الـ Cache
        self._pages_cache_grouped = result
        self._pages_cache_time = time.time()
        
        # تحويل النتيجة إلى قائمة مسطحة
        all_pages = []
        total_pages = 0
        for app_name, app_data in result.items():
            # التعامل مع الهيكل الجديد: {'my_pages': [...], 'business_managers': [...]}
            if isinstance(app_data, dict) and 'my_pages' in app_data:
                # معالجة الصفحات الشخصية
                for page in app_data.get('my_pages', []):
                    page_copy = dict(page)
                    page_copy['_app_name'] = app_name
                    all_pages.append(page_copy)
                    total_pages += 1
                
                # معالجة صفحات Business Manager
                for bm in app_data.get('business_managers', []):
                    for page in bm.get('pages', []):
                        page_copy = dict(page)
                        page_copy['_app_name'] = app_name
                        page_copy['_bm_name'] = bm.get('bm_name', 'Unknown BM')
                        all_pages.append(page_copy)
                        total_pages += 1
            elif isinstance(app_data, dict) and 'error' in app_data:
                # تجاهل التطبيقات التي بها خطأ
                continue
            elif isinstance(app_data, list):
                # للتوافق مع الهيكل القديم
                for page in app_data:
                    page_copy = dict(page)
                    page_copy['_app_name'] = app_name
                    all_pages.append(page_copy)
                    total_pages += 1
        
        self._pages_cache = all_pages
        
        # عرض الصفحات مجمعة
        self._display_pages_grouped(result)
        
        # إرسال إشارة بالصفحات المحدثة
        self.pages_refreshed.emit(all_pages)
        
        # عرض رسالة النجاح
        self.log_message.emit(f'✅ تم جلب {total_pages} صفحة من {len(result)} تطبيق')
    
    def _on_fetch_pages_error(self, error_msg: str):
        """معالج خطأ جلب الصفحات."""
        # إعادة تفعيل زر الجلب
        self.load_pages_btn.setEnabled(True)
        self.load_pages_btn.setText('🔄 جلب الصفحات')
        
        self.log_message.emit(f'❌ خطأ في جلب الصفحات: {error_msg}')
        QMessageBox.warning(self, 'خطأ', f'فشل جلب الصفحات:\n{error_msg}')
    
    def _display_pages_grouped(self, grouped_result: dict):
        """
        عرض الصفحات مجمعة حسب التطبيق و Business Manager باستخدام QTreeWidget.
        
        الشكل النهائي:
        📁 صفحاتي (5 صفحة)
           ├── Page A
           ├── Page B
           └── Page C
        
        📁 Business Manager: BM 1 (3 صفحة)
           ├── BM Page 1
           └── BM Page 2
        """
        self.pages_tree.clear()
        total_pages = 0
        
        for app_name, app_data in grouped_result.items():
            # التحقق من وجود خطأ
            if isinstance(app_data, dict) and "error" in app_data:
                error_item = QTreeWidgetItem([f"❌ {app_name}: {app_data['error']}", ""])
                error_item.setForeground(0, QColor('#e74c3c'))
                error_item.setData(0, Qt.UserRole, None)
                self.pages_tree.addTopLevelItem(error_item)
                continue
            
            # الحصول على الصفحات الشخصية و Business Managers
            my_pages = app_data.get('my_pages', []) if isinstance(app_data, dict) else app_data
            business_managers = app_data.get('business_managers', []) if isinstance(app_data, dict) else []
            
            # للتوافق مع الإصدار القديم - إذا كانت البيانات قائمة مباشرة
            if isinstance(app_data, list):
                my_pages = app_data
                business_managers = []
            
            # إضافة مجموعة الصفحات الشخصية تحت التطبيق
            if my_pages:
                my_pages_group = QTreeWidgetItem([f"📁 صفحاتي - {app_name} ({len(my_pages)} صفحة)", ""])
                my_pages_group.setExpanded(True)
                my_pages_group.setData(0, Qt.UserRole, None)  # غير قابل للتحديد
                my_pages_group.setData(1, Qt.UserRole, app_name)
                font = my_pages_group.font(0)
                font.setBold(True)
                my_pages_group.setFont(0, font)
                self.pages_tree.addTopLevelItem(my_pages_group)
                
                for page in my_pages:
                    page_name = page.get("name", "بدون اسم")
                    page_id = page.get("id", "")
                    page_item = QTreeWidgetItem([f"📄 {page_name}", page_id])
                    
                    # تخزين بيانات الصفحة بما فيها اسم التطبيق
                    page_data = dict(page)
                    page_data['_app_name'] = app_name
                    page_item.setData(0, Qt.UserRole, page_data)
                    page_item.setData(1, Qt.UserRole, page.get("access_token"))
                    
                    my_pages_group.addChild(page_item)
                    total_pages += 1
            
            # إضافة مجموعات Business Manager
            for bm in business_managers:
                bm_name = bm.get('bm_name', 'Unknown BM')
                bm_pages = bm.get('pages', [])
                
                if bm_pages:
                    bm_group = QTreeWidgetItem([f"📁 Business Manager: {bm_name} ({len(bm_pages)} صفحة)", ""])
                    bm_group.setExpanded(True)
                    bm_group.setData(0, Qt.UserRole, None)  # غير قابل للتحديد
                    bm_group.setData(1, Qt.UserRole, f"{app_name}:{bm_name}")
                    font = bm_group.font(0)
                    font.setBold(True)
                    bm_group.setFont(0, font)
                    self.pages_tree.addTopLevelItem(bm_group)
                    
                    for page in bm_pages:
                        page_name = page.get("name", "بدون اسم")
                        page_id = page.get("id", "")
                        page_item = QTreeWidgetItem([f"📄 {page_name}", page_id])
                        
                        # تخزين بيانات الصفحة بما فيها اسم التطبيق واسم الـ BM
                        page_data = dict(page)
                        page_data['_app_name'] = app_name
                        page_data['_bm_name'] = bm_name
                        page_item.setData(0, Qt.UserRole, page_data)
                        page_item.setData(1, Qt.UserRole, page.get("access_token"))
                        
                        bm_group.addChild(page_item)
                        total_pages += 1
        
        self.log_message.emit(f'✅ تم تحميل {total_pages} صفحة في القائمة.')
    
    def get_selected_page(self):
        """
        الحصول على الصفحة المختارة حالياً.
        
        Returns:
            dict: بيانات الصفحة المختارة أو None
        """
        items = self.pages_tree.selectedItems()
        if not items:
            return None
        
        page_data = items[0].data(0, Qt.UserRole)
        if not page_data or not isinstance(page_data, dict) or 'id' not in page_data:
            return None
        
        return page_data
    
    def find_and_select_page(self, page_id: str, app_name: str = ''):
        """
        البحث عن صفحة واختيارها في الشجرة.
        
        Args:
            page_id: معرف الصفحة
            app_name: اسم التطبيق (اختياري)
        
        Returns:
            bool: True إذا تم العثور على الصفحة واختيارها
        """
        # البحث في جميع عناصر الشجرة
        stack = [self.pages_tree.topLevelItem(i) for i in range(self.pages_tree.topLevelItemCount())]
        
        while stack:
            item = stack.pop()
            if item is None:
                continue
            
            # إضافة العناصر الفرعية للمكدس
            for i in range(item.childCount()):
                stack.append(item.child(i))
            
            # التحقق من البيانات
            page_data = item.data(0, Qt.UserRole)
            if page_data and isinstance(page_data, dict) and page_data.get('id') == page_id:
                # إذا تم توفير اسم التطبيق، يجب أن يتطابق أيضاً
                if app_name:
                    if page_data.get('_app_name') == app_name or page_data.get('app_name') == app_name:
                        self.pages_tree.setCurrentItem(item)
                        return True
                else:
                    # إذا لم يتم توفير اسم تطبيق، اختر أول تطابق
                    self.pages_tree.setCurrentItem(item)
                    return True
        
        return False
    
    def get_pages_cache(self):
        """الحصول على الصفحات المخزنة مؤقتاً."""
        return self._pages_cache.copy() if self._pages_cache else []
    
    def cleanup(self):
        """تنظيف الموارد عند إغلاق اللوحة."""
        if self._fetch_pages_thread and self._fetch_pages_thread.isRunning():
            self._fetch_pages_thread.quit()
            self._fetch_pages_thread.wait(3000)
            if self._fetch_pages_thread.isRunning():
                self._fetch_pages_thread.terminate()
                self._fetch_pages_thread.wait(1000)
