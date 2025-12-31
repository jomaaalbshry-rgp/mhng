#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نقطة الدخول الرئيسية للتطبيق
Main entry point for the Facebook Video Scheduler application

استخدام:
    python admin.py
"""

import sys
import os

# إضافة المسار الحالي للـ imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui import MainWindow
from ui.helpers import load_app_icon
from core import SingleInstanceManager, SINGLE_INSTANCE_BASE_NAME, APP_TITLE
from services import initialize_database

import ctypes



# محاولة استيراد qdarktheme للثيم الداكن
try:
    import qdarktheme
    HAS_QDARKTHEME = True
except ImportError:
    HAS_QDARKTHEME = False


def _set_windows_app_id(app_id: str = "JOMAA.PageManagement.1") -> bool:
    """
    تعيين Windows AppUserModelID لجعل إشعارات ويندوز تعرض اسم التطبيق الصحيح
    Set Windows AppUserModelID to make Windows notifications show the correct app name
    
    Args:
        app_id: معرّف فريد للتطبيق - Unique application ID
    
    Returns:
        bool: True إذا نجح التعيين، False خلاف ذلك - True if successful, False otherwise
    """
    if sys.platform != 'win32':
        return False
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except (AttributeError, OSError):
        return False


def main():
    """
    تشغيل التطبيق الرئيسي
    Run the main application
    """
    # تعيين Windows AppUserModelID
    _set_windows_app_id("JOMAA.PageManagement.1")
    
    # إنشاء التطبيق
    app = QApplication(sys.argv)
    
    # التحقق من أن نسخة واحدة فقط تعمل
    single_instance = SingleInstanceManager(SINGLE_INSTANCE_BASE_NAME)
    if single_instance.is_already_running():
        single_instance.send_restore_message()
        sys.exit(0)
    
    # إعدادات التطبيق
    app.setApplicationName("Facebook Video Scheduler")
    app.setOrganizationName("Mang")
    app.setApplicationDisplayName(APP_TITLE)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setWindowIcon(load_app_icon())
    
    # تطبيق الثيم الداكن إذا كان متاحاً
    if HAS_QDARKTHEME:
        try:
            app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
        except Exception:
            pass
    
    # تهيئة قاعدة البيانات
    initialize_database()
    
    # إنشاء وعرض النافذة الرئيسية
    window = MainWindow()
    
    # ربط معالج الاستعادة
    if single_instance:
        single_instance.setup_server_handler(window.restore_from_another_instance)
    
    window.show()
    
    # تشغيل حلقة الأحداث
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
