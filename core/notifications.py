"""
Notification System for Page Management Application

This module provides notification functionality including:
- TelegramNotifier: Send notifications via Telegram Bot
- NotificationSystem: General notification system for tasks
"""

import requests
from datetime import datetime


class TelegramNotifier:
    """
    نظام إشعارات Telegram Bot.
    يرسل إشعارات عبر بوت تليجرام عند حدوث أحداث مهمة.
    """
    
    # ثوابت التكوين
    API_BASE = 'https://api.telegram.org/bot'
    TIMEOUT = 30  # مهلة الاتصال بالثواني (زيادة من 10 إلى 30 للاتصالات البطيئة)
    
    # أنواع الإشعارات التي يتم إرسالها عبر Telegram
    NOTIFY_TYPES = {
        'upload_success': True,   # نجاح الرفع
        'upload_failed': True,    # فشل الرفع
        'schedule_start': False,  # بدء الجدولة
        'schedule_stop': False,   # إيقاف الجدولة
        'error': True,            # الأخطاء
        'warning': False,         # التحذيرات
    }
    
    def __init__(self, bot_token: str = '', chat_id: str = '', enabled: bool = False,
                 notify_success: bool = True, notify_errors: bool = True):
        """
        تهيئة نظام إشعارات Telegram.
        
        المعاملات:
            bot_token: توكن البوت من @BotFather
            chat_id: معرّف المحادثة أو القناة
            enabled: تفعيل/تعطيل الإشعارات
            notify_success: إرسال إشعارات النجاح
            notify_errors: إرسال إشعارات الأخطاء
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.notify_success = notify_success  # إرسال إشعارات النجاح
        self.notify_errors = notify_errors    # إرسال إشعارات الأخطاء
        self._last_error = None
    
    def is_configured(self) -> bool:
        """التحقق من اكتمال التكوين."""
        return bool(self.bot_token and self.chat_id)
    
    def send_message(self, message: str, parse_mode: str = 'HTML') -> tuple:
        """
        إرسال رسالة عبر Telegram Bot.
        
        المعاملات:
            message: نص الرسالة
            parse_mode: نوع التنسيق (HTML أو Markdown)
        
        العائد:
            (success: bool, error: str or None)
        """
        if not self.enabled:
            return False, 'الإشعارات معطّلة'
        
        if not self.is_configured():
            return False, 'الإعدادات غير مكتملة'
        
        try:
            url = f'{self.API_BASE}{self.bot_token}/sendMessage'
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=self.TIMEOUT)
            result = response.json()
            
            if result.get('ok'):
                self._last_error = None
                return True, None
            else:
                error_msg = result.get('description', 'خطأ غير معروف')
                self._last_error = error_msg
                return False, error_msg
                
        except requests.exceptions.Timeout:
            self._last_error = f'انتهت مهلة الاتصال ({self.TIMEOUT} ثانية) - تأكد من اتصالك بالإنترنت وحاول مرة أخرى'
            return False, self._last_error
        except requests.exceptions.ConnectionError:
            self._last_error = 'فشل الاتصال بخوادم Telegram - تأكد من:\n• اتصالك بالإنترنت\n• عدم وجود جدار ناري يمنع الاتصال'
            return False, self._last_error
        except requests.exceptions.RequestException as e:
            self._last_error = f'خطأ في الاتصال: {str(e)}'
            return False, self._last_error
        except Exception as e:
            self._last_error = f'خطأ: {str(e)}'
            return False, self._last_error
    
    def send_upload_notification(self, status: str, page_name: str, file_name: str, 
                                  video_url: str = None, error_msg: str = None) -> tuple:
        """
        إرسال إشعار رفع فيديو.
        
        المعاملات:
            status: حالة الرفع ('success' أو 'failed')
            page_name: اسم الصفحة
            file_name: اسم الملف
            video_url: رابط الفيديو (للرفع الناجح)
            error_msg: رسالة الخطأ (للرفع الفاشل)
        """
        # التحقق من إعدادات الإشعارات
        if status == 'success' and not self.notify_success:
            return False, 'إشعارات النجاح معطّلة'
        if status != 'success' and not self.notify_errors:
            return False, 'إشعارات الأخطاء معطّلة'
        
        if status == 'success':
            emoji = '✅'
            title = 'تم رفع فيديو بنجاح'
            details = f'🔗 <a href="{video_url}">مشاهدة الفيديو</a>' if video_url else ''
        else:
            emoji = '❌'
            title = 'فشل رفع الفيديو'
            details = f'⚠️ السبب: {error_msg}' if error_msg else ''
        
        message = f'''
{emoji} <b>{title}</b>

📄 <b>الملف:</b> {file_name}
📱 <b>الصفحة:</b> {page_name}
{details}
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
'''.strip()
        
        return self.send_message(message)
    
    def send_schedule_notification(self, action: str, job_name: str, next_run: str = None) -> tuple:
        """
        إرسال إشعار جدولة.
        
        المعاملات:
            action: نوع الإجراء ('start' أو 'stop')
            job_name: اسم المهمة
            next_run: وقت الرفع القادم
        """
        if action == 'start':
            emoji = '▶️'
            title = 'تم تفعيل الجدولة'
            details = f'⏰ الرفع القادم: {next_run}' if next_run else ''
        else:
            emoji = '⏸️'
            title = 'تم إيقاف الجدولة'
            details = ''
        
        message = f'''
{emoji} <b>{title}</b>

📱 <b>المهمة:</b> {job_name}
{details}
'''.strip()
        
        return self.send_message(message)
    
    def send_error_notification(self, error_type: str, message: str, job_name: str = None) -> tuple:
        """
        إرسال إشعار خطأ.
        
        المعاملات:
            error_type: نوع الخطأ
            message: رسالة الخطأ
            job_name: اسم المهمة (اختياري)
        """
        # التحقق من إعدادات إشعارات الأخطاء
        if not self.notify_errors:
            return False, 'إشعارات الأخطاء معطّلة'
        
        job_info = f'\n📱 <b>المهمة:</b> {job_name}' if job_name else ''
        
        msg = f'''
🚨 <b>تنبيه: {error_type}</b>
{job_info}
⚠️ {message}
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
'''.strip()
        
        return self.send_message(msg)
    
    def test_connection(self) -> tuple:
        """
        اختبار الاتصال بالبوت.
        
        العائد:
            (success: bool, message: str)
        """
        if not self.is_configured():
            return False, 'يرجى إدخال توكن البوت ومعرّف المحادثة'
        
        # التحقق من صيغة التوكن (يجب أن يحتوي على :)
        if ':' not in self.bot_token:
            return False, 'صيغة التوكن غير صحيحة - التوكن يجب أن يكون بالشكل: 123456789:ABCdefGHI...'
        
        # التحقق من صيغة Chat ID
        # يمكن أن يكون: رقماً موجباً (محادثة شخصية)، رقماً سالباً (مجموعة)، أو @username (قناة عامة)
        chat_id_stripped = self.chat_id.strip()
        if chat_id_stripped.startswith('@'):
            # التحقق من صيغة @username
            # Telegram usernames: 5-32 characters, alphanumeric + underscores, cannot end with underscore
            username = chat_id_stripped[1:]
            if not username or len(username) < 5:
                return False, 'معرّف القناة غير صالح - يجب أن يكون بالشكل: @channel_name (5 أحرف على الأقل)'
            # Telegram يسمح بالأحرف والأرقام والشرطة السفلية فقط
            if not all(c.isalnum() or c == '_' for c in username):
                return False, 'معرّف القناة غير صالح - يجب أن يحتوي على أحرف وأرقام وشرطة سفلية فقط'
        else:
            # التحقق من أنه رقم (موجب أو سالب)
            chat_id_clean = chat_id_stripped.lstrip('-')
            if not chat_id_clean.isdigit():
                return False, 'معرّف المحادثة غير صالح - يجب أن يكون رقماً (مثال: -1001234567890) أو @username للقنوات'
        
        test_message = f'''
🔔 <b>اختبار إشعارات Telegram</b>

✅ تم الاتصال بنجاح!
📱 <b>التطبيق:</b> Page Management
⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

سيتم إرسال إشعارات حسب اختيارك:
• إشعارات النجاح ✅
• إشعارات الأخطاء ❌
'''.strip()
        
        # تفعيل مؤقت للاختبار
        was_enabled = self.enabled
        self.enabled = True
        
        success, error = self.send_message(test_message)
        
        # إعادة الحالة السابقة
        self.enabled = was_enabled
        
        if success:
            return True, 'تم إرسال رسالة الاختبار بنجاح!'
        else:
            # تحسين رسائل الخطأ بناءً على نوع الخطأ
            if error:
                error_lower = error.lower()
                # التحقق من وصف الخطأ بدلاً من رموز HTTP فقط
                if 'unauthorized' in error_lower:
                    return False, 'التوكن غير صالح - تأكد من نسخ التوكن بشكل صحيح من @BotFather'
                elif 'chat not found' in error_lower:
                    return False, 'معرّف المحادثة غير صالح - تأكد من إدخال المعرّف بشكل صحيح'
                elif 'forbidden' in error_lower or 'bot was blocked' in error_lower:
                    return False, 'البوت لا يملك صلاحية الإرسال - تأكد من بدء محادثة مع البوت أو إضافته للمجموعة'
                elif 'not enough rights' in error_lower:
                    return False, 'البوت لا يملك صلاحيات كافية في المجموعة/القناة'
            return False, f'فشل الإرسال: {error}'


class NotificationSystem:
    """نظام إشعارات للمهام."""
    
    # أنواع الإشعارات
    INFO = 'ℹ️'
    SUCCESS = '✅'
    WARNING = '⚠️'
    ERROR = '❌'
    UPLOAD = '📤'
    SCHEDULE = '📅'
    FOLDER = '📁'
    WATERMARK = '🎨'
    NETWORK = '📶'
    WORKING_HOURS = '⏰'
    
    @staticmethod
    def notify(log_fn, level, message, job_name=None):
        """إرسال إشعار."""
        if log_fn is None:
            return
        prefix = f'[{job_name}] ' if job_name else ''
        log_fn(f'{level} {prefix}{message}')


__all__ = [
    'TelegramNotifier',
    'NotificationSystem',
]
