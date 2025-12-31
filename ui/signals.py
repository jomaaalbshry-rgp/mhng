"""
UI Signals Module
Module for UI signal definitions

Moved from ui/main_window.py as part of refactoring to extract reusable components.
"""

from PySide6.QtCore import QObject, Signal


class UiSignals(QObject):
    """
    إشارات واجهة المستخدم
    UI Signals for communication between threads and UI
    
    استخدام الإشارات لضمان التحديث الآمن للواجهة من الخيوط الأخرى
    Use signals to ensure safe UI updates from other threads
    """
    log_signal = Signal(str)                    # رسالة سجل - Log message
    progress_signal = Signal(int, str)          # تحديث التقدم - Progress update (percent, status)
    clear_progress_signal = Signal()            # مسح التقدم - Clear progress
    job_enabled_changed = Signal(str, bool)     # تغيير حالة التفعيل - Job enabled state changed (page_id, enabled)
    # إشارات لاختبار Telegram والتحديثات - لضمان تحديث الواجهة من الخيط الرئيسي
    telegram_test_result = Signal(bool, str)    # نتيجة اختبار Telegram - Telegram test result (success, message)
    update_check_finished = Signal()            # إشارة لإنهاء التحقق من التحديثات - Update check finished signal


__all__ = ['UiSignals']
