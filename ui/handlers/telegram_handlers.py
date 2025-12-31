"""
Telegram Event Handlers - معالجات أحداث Telegram
Contains handlers for Telegram notifications and settings.
"""

from typing import Optional, Callable
from PySide6.QtWidgets import QMessageBox
from core import TelegramNotifier, log_info, log_error


class TelegramHandlers:
    """
    معالجات أحداث Telegram
    Handles Telegram-related events and actions.
    """
    
    def __init__(self, parent=None):
        self.parent = parent
        self._notifier: Optional[TelegramNotifier] = None
    
    def test_telegram_connection(self, bot_token: str, chat_id: str) -> bool:
        """
        اختبار اتصال Telegram
        Test Telegram connection with given credentials.
        """
        try:
            notifier = TelegramNotifier(bot_token, chat_id)
            result = notifier.send_message("🔔 اختبار الاتصال - Test Connection")
            if result:
                QMessageBox.information(
                    self.parent, 
                    "نجاح", 
                    "✅ تم إرسال رسالة الاختبار بنجاح!"
                )
                return True
            else:
                QMessageBox.warning(
                    self.parent,
                    "فشل",
                    "❌ فشل إرسال رسالة الاختبار"
                )
                return False
        except Exception as e:
            log_error(f"Telegram test failed: {e}")
            QMessageBox.critical(
                self.parent,
                "خطأ",
                f"❌ خطأ في الاتصال: {str(e)}"
            )
            return False
    
    def send_notification(self, message: str, silent: bool = False) -> bool:
        """
        إرسال إشعار Telegram
        Send Telegram notification.
        """
        if not self._notifier:
            return False
        try:
            return self._notifier.send_message(message, silent=silent)
        except Exception as e:
            log_error(f"Failed to send Telegram notification: {e}")
            return False
    
    def send_success_notification(self, page_name: str, video_name: str):
        """إرسال إشعار نجاح الرفع"""
        message = f"✅ تم رفع الفيديو بنجاح!\n📄 الصفحة: {page_name}\n🎬 الفيديو: {video_name}"
        self.send_notification(message)
    
    def send_error_notification(self, page_name: str, error: str):
        """إرسال إشعار خطأ"""
        message = f"❌ فشل رفع الفيديو\n📄 الصفحة: {page_name}\n⚠️ الخطأ: {error}"
        self.send_notification(message)
    
    def setup_notifier(self, bot_token: str, chat_id: str):
        """إعداد مُرسل الإشعارات"""
        if bot_token and chat_id:
            self._notifier = TelegramNotifier(bot_token, chat_id)
        else:
            self._notifier = None
    
    def is_enabled(self) -> bool:
        """التحقق من تفعيل الإشعارات"""
        return self._notifier is not None
