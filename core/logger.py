"""
وحدة التسجيل الموحد - Unified Logger Module

هذه الوحدة تحتوي على نظام تسجيل موحد للتطبيق.
تدعم مستويات مختلفة من التسجيل (DEBUG, INFO, WARNING, ERROR, CRITICAL)
وتقوم بتنظيف السجلات القديمة تلقائياً.
"""

import os
import sys
import logging
import threading
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from typing import Optional, Callable


# ==================== ثوابت التسجيل ====================

# الحد الأقصى لحجم ملف السجل (5 ميجابايت)
MAX_LOG_FILE_SIZE = 5 * 1024 * 1024

# عدد ملفات السجل الاحتياطية
BACKUP_LOG_COUNT = 3

# عدد الأيام للاحتفاظ بالسجلات القديمة
LOG_RETENTION_DAYS = 7

# اسم مجلد التطبيق
APP_DATA_FOLDER = "Page management"

# تنسيق رسائل السجل
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# تنسيق رسائل السجل العربية
LOG_FORMAT_AR = '%(asctime)s | %(levelname)-8s | %(message)s'


# ==================== رموز مستويات التسجيل العربية ====================

LEVEL_ICONS = {
    'DEBUG': '🔍',
    'INFO': 'ℹ️',
    'WARNING': '⚠️',
    'ERROR': '❌',
    'CRITICAL': '🚨'
}


class ArabicFormatter(logging.Formatter):
    """
    منسق مخصص للرسائل العربية مع رموز إيموجي.
    """
    
    def format(self, record):
        # إضافة رمز المستوى
        icon = LEVEL_ICONS.get(record.levelname, '')
        record.levelname = f"{icon} {record.levelname}"
        return super().format(record)


def _get_logs_directory() -> Path:
    """
    الحصول على مسار مجلد السجلات.
    
    العائد:
        مسار المجلد في AppData/Roaming (ويندوز) أو ~/.config (لينكس/ماك)
    """
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            logs_dir = Path(appdata) / APP_DATA_FOLDER / 'logs'
        else:
            logs_dir = Path.home() / '.config' / APP_DATA_FOLDER / 'logs'
    else:
        logs_dir = Path.home() / '.config' / APP_DATA_FOLDER / 'logs'
    
    # إنشاء المجلد إذا لم يكن موجوداً
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def cleanup_old_logs(days: int = LOG_RETENTION_DAYS) -> int:
    """
    تنظيف ملفات السجلات القديمة.
    
    المعاملات:
        days: عدد الأيام للاحتفاظ بالسجلات (الافتراضي 7 أيام)
    
    العائد:
        عدد الملفات التي تم حذفها
    """
    try:
        logs_dir = _get_logs_directory()
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for log_file in logs_dir.glob('*.log*'):
            try:
                # التحقق من تاريخ التعديل
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_mtime < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
            except (OSError, PermissionError):
                # تجاهل الملفات التي لا يمكن حذفها
                pass
        
        return deleted_count
    except Exception:
        return 0


class UnifiedLogger:
    """
    فئة المسجل الموحد للتطبيق.
    
    توفر هذه الفئة واجهة موحدة للتسجيل مع دعم:
    - مستويات متعددة (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - التسجيل في ملف مع التدوير التلقائي
    - التسجيل في وحدة التحكم
    - التنظيف التلقائي للسجلات القديمة
    - دعم الرسائل العربية
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """تطبيق نمط Singleton للحصول على مثيل واحد فقط."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, 
                 name: str = 'PageManagement',
                 level: int = logging.INFO,
                 enable_console: bool = True,
                 enable_file: bool = True,
                 log_callback: Optional[Callable[[str], None]] = None):
        """
        تهيئة المسجل.
        
        المعاملات:
            name: اسم المسجل
            level: مستوى التسجيل الافتراضي
            enable_console: تفعيل التسجيل في وحدة التحكم
            enable_file: تفعيل التسجيل في ملف
            log_callback: دالة استدعاء للتسجيل (اختياري)
        """
        # تجنب إعادة التهيئة
        if self._initialized:
            return
        
        self._initialized = True
        self._name = name
        self._level = level
        self._log_callback = log_callback
        self._callback_lock = threading.Lock()
        
        # إنشاء المسجل
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        self._logger.handlers.clear()  # إزالة أي معالجات سابقة
        
        # المنسق العربي
        formatter = ArabicFormatter(LOG_FORMAT_AR, LOG_DATE_FORMAT)
        
        # معالج وحدة التحكم
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)
        
        # معالج الملف مع التدوير
        if enable_file:
            try:
                logs_dir = _get_logs_directory()
                log_file = logs_dir / f'{name.lower()}.log'
                
                file_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=MAX_LOG_FILE_SIZE,
                    backupCount=BACKUP_LOG_COUNT,
                    encoding='utf-8'
                )
                file_handler.setLevel(level)
                file_handler.setFormatter(formatter)
                self._logger.addHandler(file_handler)
            except Exception as e:
                # في حالة فشل إنشاء معالج الملف، نستمر بدونه
                if enable_console:
                    self._logger.warning(f'فشل إنشاء ملف السجل: {e}')
        
        # تنظيف السجلات القديمة عند البدء
        try:
            deleted = cleanup_old_logs()
            if deleted > 0:
                self._logger.debug(f'تم حذف {deleted} ملفات سجل قديمة')
        except Exception:
            pass
    
    def set_callback(self, callback: Optional[Callable[[str], None]]):
        """
        تعيين دالة استدعاء للتسجيل.
        
        المعاملات:
            callback: دالة تستقبل رسالة السجل كنص
        """
        with self._callback_lock:
            self._log_callback = callback
    
    def set_level(self, level: int):
        """
        تغيير مستوى التسجيل.
        
        المعاملات:
            level: مستوى التسجيل الجديد (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self._level = level
        self._logger.setLevel(level)
        for handler in self._logger.handlers:
            handler.setLevel(level)
    
    def _notify_callback(self, message: str):
        """إرسال الرسالة لدالة الاستدعاء إن وجدت."""
        with self._callback_lock:
            if self._log_callback:
                try:
                    self._log_callback(message)
                except Exception:
                    pass  # تجاهل أخطاء الاستدعاء
    
    def debug(self, message: str, extra_info: str = None):
        """
        تسجيل رسالة تصحيح (DEBUG).
        
        المعاملات:
            message: نص الرسالة
            extra_info: معلومات إضافية (اختياري)
        """
        full_message = f'{message} | {extra_info}' if extra_info else message
        self._logger.debug(full_message)
        self._notify_callback(f'🔍 {message}')
    
    def info(self, message: str, extra_info: str = None):
        """
        تسجيل رسالة معلومات (INFO).
        
        المعاملات:
            message: نص الرسالة
            extra_info: معلومات إضافية (اختياري)
        """
        full_message = f'{message} | {extra_info}' if extra_info else message
        self._logger.info(full_message)
        self._notify_callback(f'ℹ️ {message}')
    
    def warning(self, message: str, extra_info: str = None):
        """
        تسجيل رسالة تحذير (WARNING).
        
        المعاملات:
            message: نص الرسالة
            extra_info: معلومات إضافية (اختياري)
        """
        full_message = f'{message} | {extra_info}' if extra_info else message
        self._logger.warning(full_message)
        self._notify_callback(f'⚠️ {message}')
    
    def error(self, message: str, extra_info: str = None, exc_info: bool = False):
        """
        تسجيل رسالة خطأ (ERROR).
        
        المعاملات:
            message: نص الرسالة
            extra_info: معلومات إضافية (اختياري)
            exc_info: تضمين معلومات الاستثناء (افتراضي False)
        """
        full_message = f'{message} | {extra_info}' if extra_info else message
        self._logger.error(full_message, exc_info=exc_info)
        self._notify_callback(f'❌ {message}')
    
    def critical(self, message: str, extra_info: str = None, exc_info: bool = True):
        """
        تسجيل رسالة حرجة (CRITICAL).
        
        المعاملات:
            message: نص الرسالة
            extra_info: معلومات إضافية (اختياري)
            exc_info: تضمين معلومات الاستثناء (افتراضي True)
        """
        full_message = f'{message} | {extra_info}' if extra_info else message
        self._logger.critical(full_message, exc_info=exc_info)
        self._notify_callback(f'🚨 {message}')
    
    def exception(self, message: str, extra_info: str = None):
        """
        تسجيل استثناء مع معلومات التتبع الكاملة.
        
        المعاملات:
            message: نص الرسالة
            extra_info: معلومات إضافية (اختياري)
        """
        full_message = f'{message} | {extra_info}' if extra_info else message
        self._logger.exception(full_message)
        self._notify_callback(f'❌ {message}')
    
    def upload_start(self, file_name: str, file_size: int, upload_type: str = 'فيديو'):
        """
        تسجيل بدء عملية الرفع.
        
        المعاملات:
            file_name: اسم الملف
            file_size: حجم الملف بالبايت
            upload_type: نوع المحتوى (فيديو، ريلز، ستوري)
        """
        size_mb = file_size / (1024 * 1024)
        message = f'بدء رفع {upload_type}: {file_name} ({size_mb:.2f} ميجابايت)'
        self.info(message)
    
    def upload_progress(self, file_name: str, progress: float, speed_mbps: float = None):
        """
        تسجيل تقدم عملية الرفع.
        
        المعاملات:
            file_name: اسم الملف
            progress: نسبة التقدم (0-100)
            speed_mbps: سرعة الرفع بالميجابت في الثانية (اختياري)
        """
        if speed_mbps:
            message = f'تقدم الرفع: {file_name} - {progress:.1f}% ({speed_mbps:.2f} Mbps)'
        else:
            message = f'تقدم الرفع: {file_name} - {progress:.1f}%'
        self.debug(message)
    
    def upload_success(self, file_name: str, video_id: str = None, page_name: str = None):
        """
        تسجيل نجاح عملية الرفع.
        
        المعاملات:
            file_name: اسم الملف
            video_id: معرف الفيديو على فيسبوك (اختياري)
            page_name: اسم الصفحة (اختياري)
        """
        extra = []
        if video_id:
            extra.append(f'video_id: {video_id}')
        if page_name:
            extra.append(f'الصفحة: {page_name}')
        
        extra_str = ' | '.join(extra) if extra else None
        message = f'تم رفع الملف بنجاح: {file_name}'
        self.info(message, extra_str)
    
    def upload_failed(self, file_name: str, error: str, retry_count: int = 0):
        """
        تسجيل فشل عملية الرفع.
        
        المعاملات:
            file_name: اسم الملف
            error: رسالة الخطأ
            retry_count: عدد المحاولات (اختياري)
        """
        if retry_count > 0:
            message = f'فشل رفع الملف: {file_name} - المحاولة {retry_count}'
        else:
            message = f'فشل رفع الملف: {file_name}'
        self.error(message, f'الخطأ: {error}')
    
    def api_request(self, endpoint: str, method: str = 'POST', status_code: int = None):
        """
        تسجيل طلب API.
        
        المعاملات:
            endpoint: نقطة النهاية
            method: طريقة HTTP
            status_code: رمز الحالة (اختياري)
        """
        if status_code:
            message = f'طلب API: {method} {endpoint} - الحالة: {status_code}'
        else:
            message = f'طلب API: {method} {endpoint}'
        self.debug(message)
    
    def rate_limit_hit(self, wait_seconds: int, endpoint: str = None):
        """
        تسجيل الوصول لحد معدل الطلبات.
        
        المعاملات:
            wait_seconds: وقت الانتظار بالثواني
            endpoint: نقطة النهاية (اختياري)
        """
        message = f'تم الوصول لحد معدل الطلبات - الانتظار {wait_seconds} ثانية'
        if endpoint:
            message += f' ({endpoint})'
        self.warning(message)
    
    def network_error(self, error: str, retry: bool = True):
        """
        تسجيل خطأ شبكة.
        
        المعاملات:
            error: رسالة الخطأ
            retry: هل سيتم إعادة المحاولة
        """
        if retry:
            message = f'خطأ في الشبكة - سيتم إعادة المحاولة: {error}'
            self.warning(message)
        else:
            message = f'خطأ في الشبكة: {error}'
            self.error(message)
    
    def validation_error(self, file_name: str, error: str):
        """
        تسجيل خطأ في التحقق من صحة الملف.
        
        المعاملات:
            file_name: اسم الملف
            error: رسالة الخطأ
        """
        message = f'فشل التحقق من صحة الملف: {file_name}'
        self.warning(message, error)
    
    def get_log_file_path(self) -> Optional[Path]:
        """
        الحصول على مسار ملف السجل الحالي.
        
        العائد:
            مسار ملف السجل أو None إذا لم يكن موجوداً
        """
        try:
            logs_dir = _get_logs_directory()
            log_file = logs_dir / f'{self._name.lower()}.log'
            return log_file if log_file.exists() else None
        except Exception:
            return None


# ==================== دوال مساعدة للوصول السريع ====================

# المثيل الافتراضي
_default_logger: Optional[UnifiedLogger] = None
_logger_init_lock = threading.Lock()


def get_logger(name: str = 'PageManagement') -> UnifiedLogger:
    """
    الحصول على مثيل المسجل.
    
    المعاملات:
        name: اسم المسجل (اختياري)
    
    العائد:
        مثيل المسجل الموحد
    """
    global _default_logger
    
    with _logger_init_lock:
        if _default_logger is None:
            _default_logger = UnifiedLogger(name)
        return _default_logger


def log_debug(message: str, extra_info: str = None):
    """تسجيل رسالة تصحيح سريع."""
    get_logger().debug(message, extra_info)


def log_info(message: str, extra_info: str = None):
    """تسجيل رسالة معلومات سريع."""
    get_logger().info(message, extra_info)


def log_warning(message: str, extra_info: str = None):
    """تسجيل رسالة تحذير سريع."""
    get_logger().warning(message, extra_info)


def log_error(message: str, extra_info: str = None, exc_info: bool = False):
    """تسجيل رسالة خطأ سريع."""
    get_logger().error(message, extra_info, exc_info)


def log_critical(message: str, extra_info: str = None):
    """تسجيل رسالة حرجة سريع."""
    get_logger().critical(message, extra_info)


def log_exception(message: str, extra_info: str = None):
    """تسجيل استثناء سريع."""
    get_logger().exception(message, extra_info)


def _format_error_traceback(error):
    """
    تنسيق معلومات التتبع للخطأ.
    Format traceback information for an error.
    
    المعاملات / Parameters:
        error: الخطأ الذي حدث / The error (Exception or str)
        
    العائد / Returns:
        str: نص التتبع المنسق / Formatted traceback string
    """
    current_exception_info = sys.exc_info()
    has_exception_context = current_exception_info[0] is not None
    
    if has_exception_context:
        # We're in an exception handler, get the full traceback
        return ''.join(traceback.format_exception(*current_exception_info))
    elif isinstance(error, BaseException):
        # Error is an Exception object but we're not in exception context
        # Format the exception type and message
        tb_str = f'{type(error).__name__}: {error}\n'
        if hasattr(error, '__traceback__') and error.__traceback__:
            tb_str += ''.join(traceback.format_tb(error.__traceback__))
        return tb_str
    else:
        # Error is a string or other type
        return str(error)


def log_error_to_file(error, extra_info=None):
    """
    تسجيل الأخطاء في ملف لمنع إغلاق البرنامج.
    Log errors to file to prevent program crash.
    
    المعاملات / Parameters:
        error: الخطأ الذي حدث / The error that occurred (Exception or str)
        extra_info: معلومات إضافية / Additional information (optional)
    """
    try:
        logs_dir = _get_logs_directory()
        log_file = logs_dir / f'error_{datetime.now().strftime("%Y%m%d")}.log'
        
        # Get formatted traceback
        tb_str = _format_error_traceback(error)
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f'\n{"=" * 80}\n')
            f.write(f'[{timestamp}] Error Log\n')
            if extra_info:
                f.write(f'Context: {extra_info}\n')
            f.write(f'Error: {error}\n')
            f.write(f'Traceback:\n{tb_str}\n')
            f.write(f'{"=" * 80}\n')
    except Exception as log_err:
        # If logging fails, print to stderr to avoid silent failures
        print(f'Failed to log error to file: {log_err}', file=sys.stderr)


# ==================== رموز الخطأ ====================

class ErrorCodes:
    """
    رموز الأخطاء الموحدة للتطبيق.
    
    تستخدم هذه الرموز لتوحيد رسائل الخطأ وتسهيل التشخيص.
    """
    
    # أخطاء الشبكة (1xxx)
    NETWORK_CONNECTION_FAILED = 1001
    NETWORK_TIMEOUT = 1002
    NETWORK_SSL_ERROR = 1003
    
    # أخطاء API (2xxx)
    API_RATE_LIMIT = 2001
    API_INVALID_TOKEN = 2002
    API_PERMISSION_DENIED = 2003
    API_INVALID_RESPONSE = 2004
    API_SERVER_ERROR = 2005
    
    # أخطاء الملفات (3xxx)
    FILE_NOT_FOUND = 3001
    FILE_TOO_LARGE = 3002
    FILE_INVALID_FORMAT = 3003
    FILE_DURATION_EXCEEDED = 3004
    FILE_CORRUPTED = 3005
    FILE_PERMISSION_DENIED = 3006
    
    # أخطاء الرفع (4xxx)
    UPLOAD_FAILED = 4001
    UPLOAD_INTERRUPTED = 4002
    UPLOAD_SESSION_EXPIRED = 4003
    UPLOAD_VALIDATION_FAILED = 4004
    
    # أخطاء النظام (5xxx)
    DISK_SPACE_LOW = 5001
    MEMORY_ERROR = 5002
    THREAD_ERROR = 5003
    
    # رسائل الأخطاء العربية
    MESSAGES = {
        NETWORK_CONNECTION_FAILED: 'فشل الاتصال بالشبكة',
        NETWORK_TIMEOUT: 'انتهت مهلة الاتصال',
        NETWORK_SSL_ERROR: 'خطأ في شهادة SSL',
        
        API_RATE_LIMIT: 'تم تجاوز حد معدل الطلبات - يرجى الانتظار',
        API_INVALID_TOKEN: 'التوكن غير صالح أو منتهي الصلاحية',
        API_PERMISSION_DENIED: 'صلاحيات غير كافية للقيام بهذه العملية',
        API_INVALID_RESPONSE: 'استجابة غير صالحة من الخادم',
        API_SERVER_ERROR: 'خطأ في خادم فيسبوك',
        
        FILE_NOT_FOUND: 'الملف غير موجود',
        FILE_TOO_LARGE: 'حجم الملف يتجاوز الحد المسموح',
        FILE_INVALID_FORMAT: 'صيغة الملف غير مدعومة',
        FILE_DURATION_EXCEEDED: 'مدة الفيديو تتجاوز الحد المسموح',
        FILE_CORRUPTED: 'الملف تالف أو غير قابل للقراءة',
        FILE_PERMISSION_DENIED: 'لا توجد صلاحية للوصول للملف',
        
        UPLOAD_FAILED: 'فشلت عملية الرفع',
        UPLOAD_INTERRUPTED: 'تم قطع عملية الرفع',
        UPLOAD_SESSION_EXPIRED: 'انتهت صلاحية جلسة الرفع',
        UPLOAD_VALIDATION_FAILED: 'فشل التحقق من صحة الملف قبل الرفع',
        
        DISK_SPACE_LOW: 'المساحة المتاحة على القرص غير كافية',
        MEMORY_ERROR: 'خطأ في الذاكرة',
        THREAD_ERROR: 'خطأ في إدارة المهام المتزامنة',
    }
    
    @classmethod
    def get_message(cls, code: int) -> str:
        """
        الحصول على رسالة الخطأ بالعربية.
        
        المعاملات:
            code: رمز الخطأ
        
        العائد:
            رسالة الخطأ بالعربية
        """
        return cls.MESSAGES.get(code, f'خطأ غير معروف (رمز: {code})')


class UploadError(Exception):
    """
    استثناء مخصص لأخطاء الرفع.
    
    يحتوي على رمز الخطأ ورسالة مفصلة.
    """
    
    def __init__(self, code: int, message: str = None, details: str = None):
        """
        تهيئة الاستثناء.
        
        المعاملات:
            code: رمز الخطأ من ErrorCodes
            message: رسالة مخصصة (اختياري)
            details: تفاصيل إضافية (اختياري)
        """
        self.code = code
        self.message = message or ErrorCodes.get_message(code)
        self.details = details
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            return f'{self.message} - {self.details}'
        return self.message


class NetworkError(UploadError):
    """استثناء لأخطاء الشبكة."""
    pass


class APIError(UploadError):
    """استثناء لأخطاء API."""
    pass


class FileError(UploadError):
    """استثناء لأخطاء الملفات."""
    pass
