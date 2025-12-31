"""
نافذة إدارة التوكينات - Token Management Dialog
Dialog window for managing Facebook app tokens
"""

from functools import partial
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QScrollArea, QWidget, QPushButton, QLabel, QLineEdit, QMessageBox
)

# استيراد من core
from core import (
    TokenExchangeThread, DEFAULT_TOKEN_EXPIRY_SECONDS
)


class TokenManagementDialog(QDialog):
    """
    نافذة إدارة التوكينات - تمكن من إضافة عدة تطبيقات وتحويل التوكينات القصيرة إلى طويلة.
    """

    def __init__(self, parent=None, 
                 get_all_app_tokens_func=None,
                 save_app_token_func=None,
                 delete_app_token_func=None):
        # التحقق من تمرير جميع الدوال المطلوبة قبل التهيئة
        if not get_all_app_tokens_func or not save_app_token_func or not delete_app_token_func:
            raise ValueError("يجب تمرير جميع الدوال المطلوبة: get_all_app_tokens_func, save_app_token_func, delete_app_token_func")
        
        super().__init__(parent)
        self.setWindowTitle('🔑 إدارة التوكينات')
        self.setMinimumSize(700, 500)
        self._apps = []  # قائمة التطبيقات المحلية
        
        # حفظ الدوال الممررة
        self._get_all_app_tokens = get_all_app_tokens_func
        self._save_app_token = save_app_token_func
        self._delete_app_token = delete_app_token_func
        
        self._build_ui()
        self._load_apps()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # تعليمات
        instructions = QLabel(
            '💡 أضف تطبيقاتك من Facebook Developers واحصل على توكينات طويلة (60 يوم)\n'
            '• التوكن القصير يمكن الحصول عليه من Graph API Explorer\n'
            '• اضغط "جلب التوكن الطويل" لتحويله تلقائياً'
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet('color: #7f8c8d; padding: 10px; background: #2d3436; border-radius: 5px;')
        layout.addWidget(instructions)

        # منطقة التمرير للتطبيقات
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # ويدجت يحتوي على جميع التطبيقات
        self.apps_container = QWidget()
        self.apps_layout = QVBoxLayout(self.apps_container)
        self.apps_layout.setSpacing(15)

        scroll_area.setWidget(self.apps_container)
        layout.addWidget(scroll_area)

        # زر إضافة تطبيق جديد
        add_btn_row = QHBoxLayout()
        add_btn = QPushButton('➕ إضافة تطبيق جديد')
        add_btn.setStyleSheet('background: #27ae60; color: white; padding: 10px 20px; font-weight: bold;')
        add_btn.clicked.connect(self._add_new_app)
        add_btn_row.addStretch()
        add_btn_row.addWidget(add_btn)
        add_btn_row.addStretch()
        layout.addLayout(add_btn_row)

        # أزرار الإجراءات
        btns_row = QHBoxLayout()

        save_btn = QPushButton('💾 حفظ الكل')
        save_btn.setStyleSheet('background: #3498db; color: white; padding: 8px 16px;')
        save_btn.clicked.connect(self._save_all)
        btns_row.addWidget(save_btn)

        btns_row.addStretch()

        close_btn = QPushButton('إغلاق')
        close_btn.clicked.connect(self.accept)
        btns_row.addWidget(close_btn)

        layout.addLayout(btns_row)

    def _load_apps(self):
        """تحميل التطبيقات المحفوظة من قاعدة البيانات."""
        apps = self._get_all_app_tokens()

        if not apps:
            # إضافة تطبيق افتراضي فارغ
            self._add_new_app()
        else:
            for app in apps:
                self._add_app_widget(app)

    def _add_new_app(self):
        """إضافة تطبيق جديد فارغ."""
        app_index = len(self._apps) + 1
        app_data = {
            'id': None,
            'app_name': f'APP{app_index}',
            'app_id': '',
            'app_secret': '',
            'short_lived_token': '',
            'long_lived_token': '',
            'token_expires_at': None
        }
        self._add_app_widget(app_data)

    def _add_app_widget(self, app_data: dict):
        """إضافة ويدجت تطبيق جديد."""
        app_widget = QGroupBox(f"📱 {app_data.get('app_name', 'تطبيق جديد')}")
        app_widget.setStyleSheet('''
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3498db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        ''')

        app_layout = QFormLayout()

        # اسم التطبيق
        name_input = QLineEdit()
        name_input.setText(app_data.get('app_name', ''))
        name_input.setPlaceholderText('اسم التطبيق (مثل: APP1)')
        app_layout.addRow('📌 اسم التطبيق:', name_input)

        # معرف التطبيق
        id_input = QLineEdit()
        id_input.setText(app_data.get('app_id', ''))
        id_input.setPlaceholderText('App ID من Facebook Developers')
        app_layout.addRow('🆔 معرف التطبيق:', id_input)

        # كلمة المرور (App Secret)
        secret_input = QLineEdit()
        secret_input.setText(app_data.get('app_secret', ''))
        secret_input.setPlaceholderText('App Secret من Facebook Developers')
        secret_input.setEchoMode(QLineEdit.Password)
        app_layout.addRow('🔒 كلمة المرور:', secret_input)

        # التوكن القصير
        short_token_input = QLineEdit()
        short_token_input.setText(app_data.get('short_lived_token', ''))
        short_token_input.setPlaceholderText('التوكن القصير من Graph API Explorer')
        short_token_input.setEchoMode(QLineEdit.Password)
        app_layout.addRow('⏱️ التوكن القصير:', short_token_input)

        # التوكن الطويل (للقراءة فقط)
        long_token_display = QLineEdit()
        long_token_display.setText(app_data.get('long_lived_token', ''))
        long_token_display.setPlaceholderText('سيظهر هنا بعد جلب التوكن الطويل')
        long_token_display.setReadOnly(True)
        long_token_display.setStyleSheet('background: #2d3436;')
        app_layout.addRow('🔑 التوكن الطويل:', long_token_display)

        # تاريخ انتهاء التوكن
        expires_label = QLabel()
        if app_data.get('token_expires_at'):
            expires_label.setText(f"📅 ينتهي في: {app_data['token_expires_at']}")
            expires_label.setStyleSheet('color: #27ae60;')
        else:
            expires_label.setText('📅 لم يتم جلب التوكن الطويل بعد')
            expires_label.setStyleSheet('color: #7f8c8d;')
        app_layout.addRow('', expires_label)

        # أزرار الإجراءات
        btns_row = QHBoxLayout()

        fetch_btn = QPushButton('🔄 جلب التوكن الطويل')
        fetch_btn.setStyleSheet('background: #9b59b6; color: white; padding: 8px;')
        btns_row.addWidget(fetch_btn)

        # زر حفظ التوكن
        save_token_btn = QPushButton('💾 حفظ التوكن')
        save_token_btn.setStyleSheet('background: #3498db; color: white; padding: 8px;')
        save_token_btn.setToolTip('حفظ هذا التطبيق والتوكن في قاعدة البيانات')
        btns_row.addWidget(save_token_btn)

        delete_btn = QPushButton('🗑️ حذف')
        delete_btn.setStyleSheet('background: #e74c3c; color: white; padding: 8px;')
        btns_row.addWidget(delete_btn)

        btns_row.addStretch()
        app_layout.addRow('', btns_row)

        # حالة الجلب
        status_label = QLabel('')
        status_label.setWordWrap(True)
        app_layout.addRow('', status_label)

        app_widget.setLayout(app_layout)
        self.apps_layout.addWidget(app_widget)

        # تخزين المراجع
        app_entry = {
            'widget': app_widget,
            'db_id': app_data.get('id'),
            'name_input': name_input,
            'id_input': id_input,
            'secret_input': secret_input,
            'short_token_input': short_token_input,
            'long_token_display': long_token_display,
            'expires_label': expires_label,
            'status_label': status_label,
            'fetch_btn': fetch_btn,
            'save_token_btn': save_token_btn,
            'delete_btn': delete_btn,
            'token_expires_at': app_data.get('token_expires_at')
        }
        self._apps.append(app_entry)

        # ربط الأحداث باستخدام partial لضمان الربط الصحيح
        fetch_btn.clicked.connect(partial(self._fetch_long_token, app_entry))
        save_token_btn.clicked.connect(partial(self._save_single_app, app_entry))
        delete_btn.clicked.connect(partial(self._delete_app, app_entry))
        name_input.textChanged.connect(lambda text: app_widget.setTitle(f"📱 {text}"))

    def _fetch_long_token(self, app_entry: dict):
        """جلب التوكن الطويل لتطبيق معين باستخدام QThread."""
        app_id = app_entry['id_input'].text().strip()
        app_secret = app_entry['secret_input'].text().strip()
        short_token = app_entry['short_token_input'].text().strip()

        if not app_id or not app_secret or not short_token:
            app_entry['status_label'].setText('❌ يرجى ملء جميع الحقول')
            app_entry['status_label'].setStyleSheet('color: #e74c3c;')
            return

        app_entry['status_label'].setText('⏳ جاري جلب التوكن الطويل...')
        app_entry['status_label'].setStyleSheet('color: #f39c12;')
        app_entry['fetch_btn'].setEnabled(False)

        # التحقق من عدم وجود Thread يعمل بالفعل
        existing_thread = app_entry.get('_active_thread')
        if existing_thread and existing_thread.isRunning():
            app_entry['status_label'].setText('⚠️ عملية جلب التوكن قيد التنفيذ بالفعل')
            app_entry['status_label'].setStyleSheet('color: #f39c12;')
            app_entry['fetch_btn'].setEnabled(True)
            return

        # إنشاء Thread منفصل لجلب التوكن
        thread = TokenExchangeThread(app_id, app_secret, short_token)

        # ربط إشارة النجاح
        def on_exchange_success(data):
            long_token = data.get('access_token', '')
            expires_in = data.get('expires_in', DEFAULT_TOKEN_EXPIRY_SECONDS)
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            expires_at_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
            self._update_fetch_result(app_entry, True, long_token, expires_at_str)

        # ربط إشارة الخطأ
        def on_exchange_error(error_msg):
            self._update_fetch_result(app_entry, False, f'❌ {error_msg}', None)

        # دالة تنظيف تُستدعى عند انتهاء الـ Thread فعلياً
        def on_thread_finished():
            # تنظيف مرجع الـ Thread بعد انتهائه
            active_thread = app_entry.pop('_active_thread', None)
            if active_thread:
                active_thread.wait()  # التأكد من الانتهاء الكامل
            # إزالة الـ Thread من قائمة الـ threads النشطة
            self._cleanup_finished_token_threads()

        thread.token_received.connect(on_exchange_success)
        thread.error.connect(on_exchange_error)
        # ربط إشارة QThread.finished الحقيقية لتنظيف المرجع بأمان
        thread.finished.connect(on_thread_finished)

        # حفظ مرجع للـ Thread لمنع garbage collection
        app_entry['_active_thread'] = thread

        # إضافة الـ Thread لقائمة الـ threads النشطة للتنظيف عند الإغلاق
        if not hasattr(self, '_active_token_threads'):
            self._active_token_threads = []
        self._active_token_threads.append(thread)

        # بدء الـ Thread
        thread.start()

    def _cleanup_finished_token_threads(self):
        """إزالة الـ threads المنتهية من قائمة الـ threads النشطة."""
        if hasattr(self, '_active_token_threads'):
            self._active_token_threads = [t for t in self._active_token_threads if t.isRunning()]

    def _update_fetch_result(self, app_entry: dict, success: bool,
                              result: str, expires_at: str):
        """تحديث نتيجة جلب التوكن وحفظه تلقائياً."""
        app_entry['fetch_btn'].setEnabled(True)

        if success:
            # تحديث الواجهة بالتوكن الطويل
            app_entry['long_token_display'].setText(result)
            app_entry['expires_label'].setText(f"📅 ينتهي في: {expires_at}")
            app_entry['expires_label'].setStyleSheet('color: #27ae60;')
            app_entry['token_expires_at'] = expires_at

            # حفظ التوكن الطويل تلقائياً في قاعدة البيانات
            app_name = app_entry['name_input'].text().strip()
            app_id_value = app_entry['id_input'].text().strip()

            if app_name and app_id_value:
                save_success, new_id = self._save_app_token(
                    app_name=app_name,
                    app_id=app_id_value,
                    app_secret=app_entry['secret_input'].text().strip(),
                    short_lived_token=app_entry['short_token_input'].text().strip(),
                    long_lived_token=result,
                    token_expires_at=expires_at,
                    token_id=app_entry.get('db_id')
                )

                if save_success:
                    # تحديث معرف قاعدة البيانات إذا كان هذا إدراج جديد
                    if new_id is not None and not app_entry.get('db_id'):
                        app_entry['db_id'] = new_id

                    app_entry['status_label'].setText('✅ تم جلب وحفظ التوكن الطويل بنجاح!')
                    app_entry['status_label'].setStyleSheet('color: #27ae60;')
                else:
                    app_entry['status_label'].setText('✅ تم جلب التوكن - ⚠️ فشل الحفظ التلقائي')
                    app_entry['status_label'].setStyleSheet('color: #f39c12;')
            else:
                app_entry['status_label'].setText('✅ تم جلب التوكن - ⚠️ أكمل بيانات التطبيق للحفظ')
                app_entry['status_label'].setStyleSheet('color: #f39c12;')
        else:
            # اختصار رسائل الخطأ الطويلة (لتجنب عرض بيانات حساسة)
            error_msg = result
            if len(error_msg) > 150:
                error_msg = error_msg[:147] + '...'
            app_entry['status_label'].setText(error_msg)
            app_entry['status_label'].setStyleSheet('color: #e74c3c;')

    def _save_single_app(self, app_entry: dict):
        """حفظ تطبيق واحد."""
        app_name = app_entry['name_input'].text().strip()
        app_id_value = app_entry['id_input'].text().strip()

        if not app_name or not app_id_value:
            app_entry['status_label'].setText('❌ يرجى ملء اسم التطبيق ومعرف التطبيق')
            app_entry['status_label'].setStyleSheet('color: #e74c3c;')
            return

        save_success, new_id = self._save_app_token(
            app_name=app_name,
            app_id=app_id_value,
            app_secret=app_entry['secret_input'].text().strip(),
            short_lived_token=app_entry['short_token_input'].text().strip(),
            long_lived_token=app_entry['long_token_display'].text().strip(),
            token_expires_at=app_entry.get('token_expires_at'),
            token_id=app_entry.get('db_id')
        )

        if save_success:
            # تحديث معرف قاعدة البيانات إذا كان هذا إدراج جديد
            if new_id is not None and not app_entry.get('db_id'):
                app_entry['db_id'] = new_id

            app_entry['status_label'].setText('✅ تم حفظ التطبيق بنجاح!')
            app_entry['status_label'].setStyleSheet('color: #27ae60;')
        else:
            app_entry['status_label'].setText('❌ فشل حفظ التطبيق')
            app_entry['status_label'].setStyleSheet('color: #e74c3c;')

    def _delete_app(self, app_entry: dict):
        """حذف تطبيق."""
        reply = QMessageBox.question(
            self, 'تأكيد الحذف',
            'هل أنت متأكد من حذف هذا التطبيق؟',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # حذف من قاعدة البيانات إذا كان محفوظاً
        if app_entry.get('db_id'):
            self._delete_app_token(app_entry['db_id'])

        # إزالة من الواجهة
        app_entry['widget'].deleteLater()
        self._apps.remove(app_entry)

    def _save_all(self):
        """حفظ جميع التطبيقات."""
        saved_count = 0

        for app_entry in self._apps:
            app_name = app_entry['name_input'].text().strip()
            app_id_value = app_entry['id_input'].text().strip()

            if not app_name or not app_id_value:
                continue

            save_success, new_id = self._save_app_token(
                app_name=app_name,
                app_id=app_id_value,
                app_secret=app_entry['secret_input'].text().strip(),
                short_lived_token=app_entry['short_token_input'].text().strip(),
                long_lived_token=app_entry['long_token_display'].text().strip(),
                token_expires_at=app_entry.get('token_expires_at'),
                token_id=app_entry.get('db_id')
            )

            if save_success:
                # تحديث معرف قاعدة البيانات إذا كان هذا إدراج جديد
                if new_id is not None and not app_entry.get('db_id'):
                    app_entry['db_id'] = new_id
                saved_count += 1

        if saved_count > 0:
            QMessageBox.information(self, 'نجاح', f'تم حفظ {saved_count} تطبيق بنجاح')
        else:
            QMessageBox.warning(self, 'تحذير', 'لم يتم حفظ أي تطبيق - تأكد من ملء الحقول')
