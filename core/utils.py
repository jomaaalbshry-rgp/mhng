"""
وحدة الأدوات المساعدة - Utils Module

هذه الوحدة تحتوي على دوال مساعدة مشتركة للتطبيق.
تشمل:
- إدارة المسارات والملفات
- التحقق من الاتصال بالإنترنت
- التحقق من صلاحية التوكن
- التحقق من المساحة المتاحة على القرص
- تنظيف الملفات المؤقتة
- التعامل مع Rate Limiting من Facebook
- معالجة Unicode في مسارات الملفات
"""

import os
import sys
import subprocess
import socket
import time
import shutil
import re
import tempfile
import threading
import random
from pathlib import Path
from typing import Optional, Tuple, Callable
from datetime import datetime, timedelta
from functools import wraps

import requests


# ==================== ثوابت ====================

# مجلد التطبيق
APP_DATA_FOLDER = "Page management"

# ثوابت فحص الاتصال بالإنترنت
INTERNET_CHECK_TIMEOUT = 5
INTERNET_CHECK_HOSTS = [
    ('8.8.8.8', 53),        # Google DNS
    ('8.8.4.4', 53),        # Google DNS Secondary
    ('1.1.1.1', 53),        # Cloudflare DNS
    ('208.67.222.222', 53), # OpenDNS
]

# ثوابت Rate Limiting
RATE_LIMIT_INITIAL_WAIT = 60      # الانتظار الأولي بالثواني
RATE_LIMIT_MAX_WAIT = 3600        # الحد الأقصى للانتظار (ساعة)
RATE_LIMIT_BACKOFF_FACTOR = 2     # معامل التضاعف

# ثوابت المساحة
MIN_DISK_SPACE_MB = 100           # الحد الأدنى للمساحة المطلوبة

# أنماط أخطاء Rate Limiting من Facebook
RATE_LIMIT_PATTERNS = [
    r'rate.?limit',
    r'too.?many.?requests?',  # تصحيح: request أو requests
    r'throttl',
    r'quota.?exceeded',
    r'(#4|#17|#32|#613)',  # رموز أخطاء Facebook المتعلقة بـ Rate Limiting
]


def get_resource_path(relative_path: str) -> str:
    """
    الحصول على المسار الصحيح للملفات سواء في التطوير أو بعد التجميع بـ PyInstaller.
    
    Args:
        relative_path: المسار النسبي للملف (مثل 'assets/icon.ico')
    
    Returns:
        المسار الكامل للملف
    """
    if getattr(sys, 'frozen', False):
        # بعد التجميع بـ PyInstaller
        # الملفات تكون في _MEIPASS (مجلد مؤقت) أو بجانب الـ exe
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        # في التطوير - استخدام المجلد الجذر للمشروع (Problem 3 fix)
        # المجلد الجذر هو المجلد الأب لمجلد core
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    full_path = os.path.join(base_path, relative_path)
    
    # إذا لم يوجد الملف، جرب المسار بجانب الـ exe
    if not os.path.exists(full_path) and getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        alt_path = os.path.join(exe_dir, relative_path)
        if os.path.exists(alt_path):
            return alt_path
        
        # جرب أيضاً في مجلد _internal (PyInstaller)
        internal_path = os.path.join(exe_dir, '_internal', relative_path)
        if os.path.exists(internal_path):
            return internal_path
    
    return full_path


def get_subprocess_args() -> dict:
    """
    الحصول على معاملات subprocess لإخفاء النوافذ على Windows.
    
    هذه الدالة تمنع ظهور نوافذ PowerShell/CMD عند تشغيل الأوامر الخارجية
    مثل FFmpeg و FFprobe.
    
    Returns:
        dict يحتوي على معاملات creationflags لـ Windows
        أو dict فارغ لأنظمة أخرى
    """
    if sys.platform == 'win32':
        return {
            'creationflags': subprocess.CREATE_NO_WINDOW
        }
    return {}


def run_subprocess(cmd: list, timeout: int = 60, capture_output: bool = True, 
                   text: bool = False, **extra_kwargs) -> subprocess.CompletedProcess:
    """
    تشغيل subprocess مع إخفاء النافذة على Windows.
    
    Args:
        cmd: قائمة الأمر والمعاملات
        timeout: مهلة التنفيذ بالثواني (افتراضي 60)
        capture_output: التقاط stdout و stderr (افتراضي True)
        text: استخدام وضع النص بدلاً من bytes (افتراضي False)
        **extra_kwargs: معاملات إضافية لـ subprocess.run
    
    Returns:
        subprocess.CompletedProcess - نتيجة تنفيذ الأمر
    """
    subprocess_args = get_subprocess_args()
    
    return subprocess.run(
        cmd,
        capture_output=capture_output,
        timeout=timeout,
        text=text,
        **subprocess_args,
        **extra_kwargs
    )


def create_popen(cmd: list, **extra_kwargs) -> subprocess.Popen:
    """
    إنشاء subprocess.Popen مع إخفاء النافذة على Windows.
    
    Args:
        cmd: قائمة الأمر والمعاملات
        **extra_kwargs: معاملات إضافية لـ subprocess.Popen
    
    Returns:
        subprocess.Popen - عملية subprocess
    """
    subprocess_args = get_subprocess_args()
    
    return subprocess.Popen(
        cmd,
        **subprocess_args,
        **extra_kwargs
    )


# ==================== التحقق من الاتصال بالإنترنت ====================

def check_internet_connection(timeout: int = INTERNET_CHECK_TIMEOUT, 
                              hosts: list = None) -> bool:
    """
    التحقق من الاتصال بالإنترنت عن طريق الاتصال بخوادم موثوقة.
    
    المعاملات:
        timeout: مهلة الاتصال بالثواني (افتراضي 5)
        hosts: قائمة بالمضيفين للتحقق منهم (اختياري)
    
    العائد:
        True إذا كان هناك اتصال بالإنترنت، False خلاف ذلك
    """
    if hosts is None:
        hosts = INTERNET_CHECK_HOSTS
    
    for host, port in hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return True
        except (socket.timeout, socket.error, OSError):
            continue
    
    return False


def wait_for_internet(log_fn: Callable[[str], None] = None, 
                      check_interval: int = 60, 
                      max_attempts: int = 0) -> bool:
    """
    الانتظار حتى يعود الاتصال بالإنترنت (وضع الغفوة).
    
    المعاملات:
        log_fn: دالة للتسجيل
        check_interval: الفاصل الزمني بين المحاولات بالثواني
        max_attempts: الحد الأقصى للمحاولات (0 = بلا حد)
    
    العائد:
        True عند عودة الاتصال، False إذا تم تجاوز الحد الأقصى للمحاولات
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    attempts = 0
    while True:
        if check_internet_connection():
            if attempts > 0:
                _log('✅ عاد الاتصال بالإنترنت - استئناف العمل')
            return True
        
        attempts += 1
        if max_attempts > 0 and attempts >= max_attempts:
            _log(f'⚠️ تم تجاوز الحد الأقصى للمحاولات ({max_attempts})')
            return False
        
        _log(f'📶 لا يوجد اتصال بالإنترنت - المحاولة {attempts} - الانتظار {check_interval} ثانية...')
        time.sleep(check_interval)


# ==================== التحقق من صلاحية التوكن ====================

def validate_token(access_token: str, log_fn: Callable[[str], None] = None) -> Tuple[bool, str]:
    """
    التحقق من صلاحية توكن الوصول لـ Facebook API.
    
    المعاملات:
        access_token: توكن الوصول
        log_fn: دالة للتسجيل (اختياري)
    
    العائد:
        tuple: (صالح: bool, رسالة: str)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    if not access_token or not access_token.strip():
        return False, 'التوكن فارغ'
    
    try:
        # التحقق من التوكن عبر Facebook Graph API
        url = 'https://graph.facebook.com/v17.0/me'
        params = {'access_token': access_token}
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'error' in data:
            error = data['error']
            error_code = error.get('code', 0)
            error_message = error.get('message', 'خطأ غير معروف')
            
            # أخطاء شائعة للتوكن
            if error_code in [190, 102, 100]:
                return False, 'التوكن منتهي الصلاحية أو غير صالح'
            elif error_code == 200:
                return False, 'صلاحيات غير كافية'
            else:
                return False, f'خطأ: {error_message}'
        
        # التوكن صالح
        user_name = data.get('name', 'غير معروف')
        user_id = data.get('id', '')
        _log(f'✅ التوكن صالح - المستخدم: {user_name}')
        return True, f'التوكن صالح - المستخدم: {user_name}'
        
    except requests.exceptions.Timeout:
        return False, 'انتهت مهلة الاتصال'
    except requests.exceptions.ConnectionError:
        return False, 'فشل الاتصال بالخادم'
    except requests.exceptions.RequestException as e:
        return False, f'خطأ في الاتصال: {str(e)}'
    except Exception as e:
        return False, f'خطأ غير متوقع: {str(e)}'


def get_token_expiry(access_token: str) -> Optional[datetime]:
    """
    الحصول على تاريخ انتهاء صلاحية التوكن.
    
    المعاملات:
        access_token: توكن الوصول
    
    العائد:
        تاريخ انتهاء الصلاحية أو None إذا فشل
    """
    try:
        url = 'https://graph.facebook.com/v17.0/debug_token'
        params = {
            'input_token': access_token,
            'access_token': access_token
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if 'data' in data and 'expires_at' in data['data']:
            expires_at = data['data']['expires_at']
            if expires_at == 0:
                return None  # التوكن لا ينتهي (long-lived token)
            return datetime.fromtimestamp(expires_at)
        
        return None
    except Exception:
        return None


# ثوابت التوكن
# ملاحظة: هذه الثوابت معرّفة أيضاً في admin.py للتوافقية
# يمكن استيرادها من هنا عند الحاجة للاستخدام في وحدات أخرى
DEFAULT_TOKEN_EXPIRY_SECONDS = 5184000  # 60 يوم (60 * 24 * 60 * 60)
SECONDS_PER_DAY = 86400  # عدد الثواني في اليوم الواحد


def get_long_lived_token(app_id: str, app_secret: str, short_lived_token: str) -> Tuple[bool, str, str]:
    """
    تحويل التوكن القصير إلى توكن طويل الصلاحية (60 يوم).
    
    هذه الدالة تُستخدم كواجهة برمجية عامة في وحدة utils وتُرجع مدة الصلاحية
    كنص قابل للقراءة (مثل "60 يوم").
    
    للاستخدام في واجهة المستخدم مع تاريخ انتهاء الصلاحية الكامل، راجع
    exchange_token_for_long_lived في admin.py التي تُرجع تاريخ انتهاء
    الصلاحية بتنسيق datetime.
    
    المعاملات:
        app_id: معرف التطبيق
        app_secret: كلمة مرور التطبيق
        short_lived_token: التوكن القصير
    
    العائد:
        tuple: (نجاح: bool, التوكن الطويل أو رسالة الخطأ: str, مدة الصلاحية: str)
              - عند النجاح: (True, التوكن الطويل, "60 يوم")
              - عند الفشل: (False, رسالة الخطأ, "")
    """
    # التحقق من المدخلات
    if not app_id or not app_id.strip():
        return False, 'معرف التطبيق فارغ', ''
    if not app_secret or not app_secret.strip():
        return False, 'كلمة مرور التطبيق فارغة', ''
    if not short_lived_token or not short_lived_token.strip():
        return False, 'التوكن القصير فارغ', ''
    
    try:
        url = 'https://graph.facebook.com/v19.0/oauth/access_token'
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': app_id.strip(),
            'client_secret': app_secret.strip(),
            'fb_exchange_token': short_lived_token.strip()
        }
        
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        
        if 'access_token' in data:
            expires_in_days = data.get('expires_in', DEFAULT_TOKEN_EXPIRY_SECONDS) // SECONDS_PER_DAY
            return True, data['access_token'], f"{expires_in_days} يوم"
        
        error_msg = data.get('error', {}).get('message', 'خطأ غير معروف')
        return False, error_msg, ''
    
    except requests.exceptions.Timeout:
        return False, 'انتهت مهلة الاتصال', ''
    except requests.exceptions.ConnectionError:
        return False, 'فشل الاتصال بالخادم', ''
    except requests.exceptions.RequestException as e:
        return False, f'خطأ في الاتصال: {str(e)}', ''
    except Exception as e:
        return False, f'خطأ غير متوقع: {str(e)}', ''


# ==================== التحقق من المساحة المتاحة على القرص ====================

def get_available_disk_space(path: str = None) -> Tuple[int, int, int]:
    """
    الحصول على المساحة المتاحة على القرص.
    
    المعاملات:
        path: المسار للتحقق منه (افتراضي: المجلد الحالي)
    
    العائد:
        tuple: (الإجمالي بالبايت, المستخدم بالبايت, المتاح بالبايت)
    """
    if path is None:
        path = os.getcwd()
    
    try:
        usage = shutil.disk_usage(path)
        return usage.total, usage.used, usage.free
    except (OSError, PermissionError):
        return 0, 0, 0


def check_disk_space(required_mb: int, path: str = None, 
                     log_fn: Callable[[str], None] = None) -> bool:
    """
    التحقق من توفر مساحة كافية على القرص.
    
    المعاملات:
        required_mb: المساحة المطلوبة بالميجابايت
        path: المسار للتحقق منه (اختياري)
        log_fn: دالة للتسجيل (اختياري)
    
    العائد:
        True إذا كانت المساحة كافية، False خلاف ذلك
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    total, used, free = get_available_disk_space(path)
    free_mb = free / (1024 * 1024)
    
    if free_mb < required_mb:
        _log(f'⚠️ المساحة المتاحة ({free_mb:.1f} MB) أقل من المطلوبة ({required_mb} MB)')
        return False
    
    return True


def get_disk_space_for_file(file_path: str) -> bool:
    """
    التحقق من توفر مساحة كافية لملف معين.
    
    المعاملات:
        file_path: مسار الملف
    
    العائد:
        True إذا كانت المساحة كافية، False خلاف ذلك
    """
    try:
        file_size = os.path.getsize(file_path)
        # نحتاج ضعف حجم الملف على الأقل (للنسخ المؤقت)
        required_mb = (file_size * 2) / (1024 * 1024)
        directory = os.path.dirname(file_path) or os.getcwd()
        return check_disk_space(int(required_mb) + MIN_DISK_SPACE_MB, directory)
    except (OSError, PermissionError):
        return False


# ==================== تنظيف الملفات المؤقتة ====================

def get_temp_directory() -> Path:
    """
    الحصول على مسار مجلد الملفات المؤقتة للتطبيق.
    
    العائد:
        مسار المجلد المؤقت
    """
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            temp_dir = Path(appdata) / APP_DATA_FOLDER / 'temp'
        else:
            temp_dir = Path(tempfile.gettempdir()) / APP_DATA_FOLDER
    else:
        temp_dir = Path.home() / '.cache' / APP_DATA_FOLDER / 'temp'
    
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def cleanup_temp_files(max_age_hours: int = 24, 
                       log_fn: Callable[[str], None] = None) -> int:
    """
    تنظيف الملفات المؤقتة القديمة.
    
    المعاملات:
        max_age_hours: عمر الملفات القصوى بالساعات
        log_fn: دالة للتسجيل (اختياري)
    
    العائد:
        عدد الملفات المحذوفة
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    temp_dir = get_temp_directory()
    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    deleted_count = 0
    freed_space = 0
    
    try:
        for item in temp_dir.rglob('*'):
            if item.is_file():
                try:
                    file_mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        file_size = item.stat().st_size
                        item.unlink()
                        deleted_count += 1
                        freed_space += file_size
                except (OSError, PermissionError):
                    pass
        
        if deleted_count > 0:
            freed_mb = freed_space / (1024 * 1024)
            _log(f'🧹 تم حذف {deleted_count} ملف مؤقت ({freed_mb:.2f} MB)')
        
        return deleted_count
    except Exception:
        return 0


def create_temp_file(suffix: str = '', prefix: str = 'pm_') -> str:
    """
    إنشاء ملف مؤقت في مجلد التطبيق.
    
    المعاملات:
        suffix: لاحقة اسم الملف (مثل .mp4)
        prefix: بادئة اسم الملف
    
    العائد:
        مسار الملف المؤقت
    """
    temp_dir = get_temp_directory()
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=temp_dir)
    os.close(fd)
    return path


# ==================== التعامل مع Rate Limiting ====================

class RateLimiter:
    """
    فئة للتعامل مع Rate Limiting من Facebook API.
    
    تستخدم نمط Exponential Backoff لإعادة المحاولة.
    """
    
    def __init__(self, 
                 initial_wait: int = RATE_LIMIT_INITIAL_WAIT,
                 max_wait: int = RATE_LIMIT_MAX_WAIT,
                 backoff_factor: float = RATE_LIMIT_BACKOFF_FACTOR):
        """
        تهيئة Rate Limiter.
        
        المعاملات:
            initial_wait: وقت الانتظار الأولي بالثواني
            max_wait: الحد الأقصى للانتظار
            backoff_factor: معامل التضاعف
        """
        self._initial_wait = initial_wait
        self._max_wait = max_wait
        self._backoff_factor = backoff_factor
        self._current_wait = initial_wait
        self._last_rate_limit_time = None
        self._lock = threading.Lock()
    
    def is_rate_limited(self, response: dict) -> bool:
        """
        التحقق مما إذا كان الاستجابة تشير إلى Rate Limiting.
        
        المعاملات:
            response: استجابة API
        
        العائد:
            True إذا كان هناك Rate Limiting
        """
        if not isinstance(response, dict):
            return False
        
        error = response.get('error', {})
        if not error:
            return False
        
        # التحقق من رمز الخطأ
        error_code = error.get('code', 0)
        if error_code in [4, 17, 32, 613]:  # رموز Rate Limiting
            return True
        
        # التحقق من نص الخطأ
        error_message = str(error.get('message', '')).lower()
        for pattern in RATE_LIMIT_PATTERNS:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True
        
        return False
    
    def get_wait_time(self, response: dict = None) -> int:
        """
        الحصول على وقت الانتظار المطلوب.
        
        المعاملات:
            response: استجابة API (قد تحتوي على وقت الانتظار)
        
        العائد:
            وقت الانتظار بالثواني
        """
        with self._lock:
            # محاولة استخراج وقت الانتظار من الاستجابة
            if response and isinstance(response, dict):
                error = response.get('error', {})
                # Facebook قد يرسل retry_after في بعض الحالات
                retry_after = error.get('retry_after', 0)
                if retry_after > 0:
                    return min(retry_after, self._max_wait)
            
            # استخدام Exponential Backoff
            wait_time = self._current_wait
            self._current_wait = min(
                self._current_wait * self._backoff_factor,
                self._max_wait
            )
            
            return int(wait_time)
    
    def reset(self):
        """إعادة تعيين وقت الانتظار."""
        with self._lock:
            self._current_wait = self._initial_wait
            self._last_rate_limit_time = None
    
    def record_rate_limit(self):
        """تسجيل حدوث Rate Limiting."""
        with self._lock:
            self._last_rate_limit_time = datetime.now()
    
    def time_since_last_rate_limit(self) -> Optional[timedelta]:
        """
        الوقت منذ آخر Rate Limiting.
        
        العائد:
            timedelta أو None إذا لم يحدث Rate Limiting
        """
        with self._lock:
            if self._last_rate_limit_time:
                return datetime.now() - self._last_rate_limit_time
            return None


def handle_rate_limit(response: dict, 
                      rate_limiter: RateLimiter = None,
                      log_fn: Callable[[str], None] = None) -> int:
    """
    معالجة Rate Limiting وإرجاع وقت الانتظار.
    
    المعاملات:
        response: استجابة API
        rate_limiter: مثيل RateLimiter (اختياري)
        log_fn: دالة للتسجيل (اختياري)
    
    العائد:
        وقت الانتظار بالثواني (0 إذا لم يكن هناك Rate Limiting)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    if rate_limiter is None:
        rate_limiter = RateLimiter()
    
    if not rate_limiter.is_rate_limited(response):
        return 0
    
    rate_limiter.record_rate_limit()
    wait_time = rate_limiter.get_wait_time(response)
    
    _log(f'⚠️ تم الوصول لحد معدل الطلبات - الانتظار {wait_time} ثانية')
    
    return wait_time


# ==================== معالجة Unicode في مسارات الملفات ====================

def normalize_path(path: str) -> str:
    """
    تطبيع مسار الملف للتعامل مع Unicode.
    
    المعاملات:
        path: مسار الملف
    
    العائد:
        المسار المُطبّع
    """
    if not path:
        return path
    
    try:
        # تحويل إلى Path وإعادة إلى نص
        normalized = str(Path(path).resolve())
        return normalized
    except (OSError, ValueError):
        # في حالة فشل التطبيع، نرجع المسار كما هو
        return path


def safe_filename(filename: str, max_length: int = 200) -> str:
    """
    تنظيف اسم الملف لجعله آمناً للنظام.
    
    المعاملات:
        filename: اسم الملف الأصلي
        max_length: الحد الأقصى لطول الاسم
    
    العائد:
        اسم الملف المُنظّف
    """
    if not filename:
        return 'unnamed'
    
    # إزالة الأحرف غير المسموحة
    # على Windows: < > : " / \ | ? *
    # على Unix: / و null character
    invalid_chars = '<>:"/\\|?*\x00'
    
    cleaned = ''.join(c if c not in invalid_chars else '_' for c in filename)
    
    # إزالة المسافات المتكررة
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # قص الطول إذا كان طويلاً جداً
    if len(cleaned) > max_length:
        # الحفاظ على الامتداد
        name, ext = os.path.splitext(cleaned)
        max_name_length = max_length - len(ext)
        cleaned = name[:max_name_length] + ext
    
    return cleaned or 'unnamed'


def ensure_utf8_path(path: str) -> str:
    """
    التأكد من أن المسار مُرمّز بـ UTF-8.
    
    المعاملات:
        path: مسار الملف
    
    العائد:
        المسار المُرمّز بـ UTF-8
    """
    if isinstance(path, bytes):
        try:
            return path.decode('utf-8')
        except UnicodeDecodeError:
            return path.decode('utf-8', errors='replace')
    return path


def validate_file_path(path: str, 
                       must_exist: bool = True,
                       log_fn: Callable[[str], None] = None) -> Tuple[bool, str]:
    """
    التحقق من صحة مسار الملف.
    
    المعاملات:
        path: مسار الملف
        must_exist: هل يجب أن يكون الملف موجوداً
        log_fn: دالة للتسجيل (اختياري)
    
    العائد:
        tuple: (صالح: bool, رسالة: str)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    if not path:
        return False, 'المسار فارغ'
    
    try:
        # تطبيع المسار
        normalized_path = normalize_path(path)
        
        # التحقق من الوجود
        if must_exist and not os.path.exists(normalized_path):
            return False, 'الملف غير موجود'
        
        # التحقق من القراءة
        if must_exist and not os.access(normalized_path, os.R_OK):
            return False, 'لا توجد صلاحية للقراءة'
        
        return True, 'المسار صالح'
        
    except (OSError, ValueError) as e:
        return False, f'خطأ في المسار: {str(e)}'


# ==================== Retry Decorator ====================

# الاستثناءات الافتراضية القابلة لإعادة المحاولة
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.HTTPError,
    OSError,
    IOError,
)


def retry_with_backoff(max_retries: int = 3,
                       initial_delay: float = 1.0,
                       backoff_factor: float = 2.0,
                       max_delay: float = 60.0,
                       exceptions: tuple = None):
    """
    Decorator لإعادة المحاولة مع Exponential Backoff.
    
    المعاملات:
        max_retries: الحد الأقصى لعدد المحاولات
        initial_delay: التأخير الأولي بالثواني
        backoff_factor: معامل التضاعف
        max_delay: الحد الأقصى للتأخير
        exceptions: الاستثناءات التي تستدعي إعادة المحاولة (افتراضي: أخطاء الشبكة والملفات)
    """
    if exceptions is None:
        exceptions = RETRYABLE_EXCEPTIONS
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # الانتظار قبل المحاولة التالية
                        time.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        raise
            
            raise last_exception
        return wrapper
    return decorator


# ==================== دوال مساعدة للتحقق من الملفات ====================

def validate_file_extension(file_path: str, 
                            allowed_extensions: tuple,
                            log_fn: Callable[[str], None] = None) -> Tuple[bool, str]:
    """
    التحقق من امتداد الملف.
    
    المعاملات:
        file_path: مسار الملف
        allowed_extensions: tuple من الامتدادات المسموحة (مثل ('.mp4', '.mov'))
        log_fn: دالة للتسجيل (اختياري)
    
    العائد:
        tuple: (صالح: bool, رسالة: str)
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)
    
    if not file_path:
        return False, 'مسار الملف فارغ'
    
    _, ext = os.path.splitext(file_path)
    ext_lower = ext.lower()
    
    if ext_lower not in allowed_extensions:
        allowed_str = ', '.join(allowed_extensions)
        return False, f'امتداد الملف غير مدعوم. الامتدادات المسموحة: {allowed_str}'
    
    return True, f'الامتداد {ext_lower} مدعوم'


def get_file_info(file_path: str) -> dict:
    """
    الحصول على معلومات الملف.
    
    المعاملات:
        file_path: مسار الملف
    
    العائد:
        dict يحتوي على معلومات الملف
    """
    result = {
        'exists': False,
        'size': 0,
        'size_mb': 0.0,
        'name': '',
        'extension': '',
        'modified_time': None,
        'created_time': None,
        'readable': False,
        'writable': False
    }
    
    try:
        path = Path(file_path)
        
        if not path.exists():
            return result
        
        stat = path.stat()
        
        result['exists'] = True
        result['size'] = stat.st_size
        result['size_mb'] = stat.st_size / (1024 * 1024)
        result['name'] = path.name
        result['extension'] = path.suffix.lower()
        result['modified_time'] = datetime.fromtimestamp(stat.st_mtime)
        result['created_time'] = datetime.fromtimestamp(stat.st_ctime)
        result['readable'] = os.access(file_path, os.R_OK)
        result['writable'] = os.access(file_path, os.W_OK)
        
        return result
    except (OSError, PermissionError):
        return result


# ==================== Smart Upload Scheduler ====================

class SmartUploadScheduler:
    """
    مجدول رفع ذكي يوزع الطلبات على الوقت لتوفير طلبات API.
    
    يتتبع عدد الطلبات في الساعة واليوم ويحدد ما إذا كان يمكن الرفع الآن.
    يساعد في تجنب استنفاد حصة API والحظر من Facebook.
    
    ملاحظة: هذه الفئة آمنة للاستخدام من عدة خيوط (thread-safe).
    جميع العمليات التي تعدل العدادات محمية بقفل (_lock).
    """
    
    def __init__(self, max_per_hour: int = 20, max_per_day: int = 200):
        """
        تهيئة المجدول الذكي.
        
        المعاملات:
            max_per_hour: الحد الأقصى للرفع في الساعة
            max_per_day: الحد الأقصى للرفع في اليوم
        """
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.hourly_count = 0
        self.daily_count = 0
        self.last_hour_reset = time.time()
        self.last_day_reset = time.time()
        # قفل لحماية العدادات من التعديل المتزامن من عدة خيوط
        self._lock = threading.Lock()
    
    def _reset_counters_if_needed(self):
        """إعادة ضبط العدادات إذا انتهت الفترة الزمنية."""
        current_time = time.time()
        
        # إعادة ضبط العداد الساعي كل ساعة
        if current_time - self.last_hour_reset >= 3600:
            self.hourly_count = 0
            self.last_hour_reset = current_time
        
        # إعادة ضبط العداد اليومي كل 24 ساعة
        if current_time - self.last_day_reset >= 86400:
            self.daily_count = 0
            self.last_day_reset = current_time
    
    def can_upload(self) -> tuple:
        """
        التحقق إذا كان يمكن الرفع الآن.
        
        العائد:
            tuple: (يمكن الرفع: bool, رسالة: str أو None)
        """
        with self._lock:
            self._reset_counters_if_needed()
            
            if self.daily_count >= self.max_per_day:
                return False, "تم الوصول للحد اليومي"
            
            if self.hourly_count >= self.max_per_hour:
                wait_time = 3600 - (time.time() - self.last_hour_reset)
                return False, f"انتظر {int(wait_time/60)} دقيقة"
            
            return True, None
    
    def record_upload(self):
        """تسجيل عملية رفع ناجحة."""
        with self._lock:
            self._reset_counters_if_needed()
            self.hourly_count += 1
            self.daily_count += 1
    
    def calculate_optimal_delay(self, total_files: int) -> int:
        """
        حساب التأخير الأمثل بين الرفعات.
        
        المعاملات:
            total_files: إجمالي عدد الملفات المراد رفعها
        
        العائد:
            التأخير بالثواني بين كل رفعة
        """
        # توزيع الملفات على الساعة
        if total_files <= self.max_per_hour:
            return 3600 // total_files  # ثواني بين كل رفعة
        else:
            return 3600 // self.max_per_hour
    
    def get_remaining_quota(self) -> dict:
        """
        الحصول على الحصة المتبقية.
        
        العائد:
            dict يحتوي على الحصة المتبقية في الساعة واليوم
        """
        with self._lock:
            self._reset_counters_if_needed()
            
            return {
                'hourly_remaining': max(0, self.max_per_hour - self.hourly_count),
                'daily_remaining': max(0, self.max_per_day - self.daily_count),
                'hourly_used': self.hourly_count,
                'daily_used': self.daily_count,
                'hourly_limit': self.max_per_hour,
                'daily_limit': self.max_per_day
            }
    
    def reset_counters(self):
        """إعادة ضبط جميع العدادات."""
        with self._lock:
            self.hourly_count = 0
            self.daily_count = 0
            self.last_hour_reset = time.time()
            self.last_day_reset = time.time()


# ==================== API Usage Tracker ====================

class APIUsageTracker:
    """
    تتبع استخدام طلبات API.
    
    يستخدم لمراقبة عدد الطلبات في الساعة واليوم لتجنب تجاوز الحدود.
    """
    
    def __init__(self, hourly_limit: int = 100, daily_limit: int = 1000):
        """
        تهيئة متتبع استخدام API.
        
        المعاملات:
            hourly_limit: الحد الأقصى للطلبات في الساعة
            daily_limit: الحد الأقصى للطلبات في اليوم
        """
        self.hourly_limit = hourly_limit
        self.daily_limit = daily_limit
        self.hourly_count = 0
        self.daily_count = 0
        self.last_hour_reset = time.time()
        self.last_day_reset = time.time()
        self._lock = threading.Lock()
    
    def record_call(self, count: int = 1):
        """
        تسجيل طلب API.
        
        المعاملات:
            count: عدد الطلبات المراد تسجيلها (افتراضي 1)
        """
        with self._lock:
            self._reset_if_needed()
            self.hourly_count += count
            self.daily_count += count
    
    def get_usage(self) -> dict:
        """
        الحصول على إحصائيات الاستخدام.
        
        العائد:
            dict يحتوي على إحصائيات الاستخدام الحالية
        """
        with self._lock:
            self._reset_if_needed()
            hourly_percent = (self.hourly_count / self.hourly_limit * 100) if self.hourly_limit > 0 else 0
            daily_percent = (self.daily_count / self.daily_limit * 100) if self.daily_limit > 0 else 0
            return {
                'hourly': self.hourly_count,
                'hourly_limit': self.hourly_limit,
                'hourly_percent': hourly_percent,
                'hourly_remaining': max(0, self.hourly_limit - self.hourly_count),
                'daily': self.daily_count,
                'daily_limit': self.daily_limit,
                'daily_percent': daily_percent,
                'daily_remaining': max(0, self.daily_limit - self.daily_count),
                'time_to_hourly_reset': self._time_to_hourly_reset(),
                'time_to_daily_reset': self._time_to_daily_reset()
            }
    
    def can_make_request(self, count: int = 1) -> tuple:
        """
        التحقق مما إذا كان يمكن إجراء طلب.
        
        المعاملات:
            count: عدد الطلبات المراد التحقق منها
        
        العائد:
            tuple: (يمكن الطلب: bool, رسالة: str أو None)
        """
        with self._lock:
            self._reset_if_needed()
            
            if self.daily_count + count > self.daily_limit:
                wait_time = self._time_to_daily_reset()
                hours = int(wait_time // 3600)
                minutes = int((wait_time % 3600) // 60)
                return False, f"تم الوصول للحد اليومي. انتظر {hours} ساعة و{minutes} دقيقة"
            
            if self.hourly_count + count > self.hourly_limit:
                wait_time = self._time_to_hourly_reset()
                minutes = int(wait_time // 60)
                return False, f"تم الوصول للحد الساعي. انتظر {minutes} دقيقة"
            
            return True, None
    
    def _reset_if_needed(self):
        """إعادة تعيين العدادات إذا لزم الأمر."""
        now = time.time()
        if now - self.last_hour_reset >= 3600:
            self.hourly_count = 0
            self.last_hour_reset = now
        if now - self.last_day_reset >= 86400:
            self.daily_count = 0
            self.last_day_reset = now
    
    def _time_to_hourly_reset(self) -> float:
        """الوقت المتبقي لإعادة ضبط العداد الساعي بالثواني."""
        return max(0, 3600 - (time.time() - self.last_hour_reset))
    
    def _time_to_daily_reset(self) -> float:
        """الوقت المتبقي لإعادة ضبط العداد اليومي بالثواني."""
        return max(0, 86400 - (time.time() - self.last_day_reset))
    
    def reset(self):
        """إعادة تعيين جميع العدادات."""
        with self._lock:
            self.hourly_count = 0
            self.daily_count = 0
            self.last_hour_reset = time.time()
            self.last_day_reset = time.time()
    
    def set_limits(self, hourly_limit: int = None, daily_limit: int = None):
        """
        تعيين حدود جديدة.
        
        المعاملات:
            hourly_limit: الحد الساعي الجديد (اختياري)
            daily_limit: الحد اليومي الجديد (اختياري)
        """
        with self._lock:
            if hourly_limit is not None:
                self.hourly_limit = hourly_limit
            if daily_limit is not None:
                self.daily_limit = daily_limit


# ==================== API Warning System ====================

class APIWarningSystem:
    """
    نظام تحذيرات استخدام API.
    
    يصدر تحذيرات متدرجة عند اقتراب الاستخدام من الحدود.
    """
    
    # عتبات التحذير: (نسبة الاستخدام, مستوى, رسالة)
    WARNING_THRESHOLDS = [
        (70, 'info', '⚠️ تحذير: تم استخدام 70% من حد الطلبات'),
        (85, 'warning', '🔶 تحذير: تم استخدام 85% من حد الطلبات'),
        (95, 'critical', '🔴 تحذير عاجل: تم استخدام 95% من حد الطلبات!'),
        (100, 'stop', '⛔ تم الوصول للحد الأقصى - إيقاف مؤقت')
    ]
    
    def __init__(self, tracker: APIUsageTracker, log_fn: Callable = None, notify_fn: Callable = None):
        """
        تهيئة نظام التحذيرات.
        
        المعاملات:
            tracker: متتبع استخدام API
            log_fn: دالة التسجيل (اختياري)
            notify_fn: دالة الإشعار للتحذيرات الحرجة (اختياري)
        """
        self.tracker = tracker
        self.log_fn = log_fn
        self.notify_fn = notify_fn
        self._warned_thresholds_hourly = set()
        self._warned_thresholds_daily = set()
        self._lock = threading.Lock()
    
    def check_and_warn(self) -> tuple:
        """
        التحقق من الاستخدام وإصدار تحذيرات.
        
        العائد:
            tuple: (can_continue: bool, message: str أو None)
        """
        usage = self.tracker.get_usage()
        
        hourly_percent = usage['hourly_percent']
        daily_percent = usage['daily_percent']
        
        # التحقق من كلا الحدين
        result_hourly = self._check_threshold(hourly_percent, 'الساعي', self._warned_thresholds_hourly)
        result_daily = self._check_threshold(daily_percent, 'اليومي', self._warned_thresholds_daily)
        
        # إرجاع أسوأ نتيجة
        if not result_hourly[0]:
            return result_hourly
        if not result_daily[0]:
            return result_daily
        
        # إذا كانت هناك رسالة تحذير (ليست stop)، أرجعها
        if result_hourly[1]:
            return True, result_hourly[1]
        if result_daily[1]:
            return True, result_daily[1]
        
        return True, None
    
    def _check_threshold(self, percent: float, limit_type: str, warned_set: set) -> tuple:
        """
        التحقق من عتبة محددة.
        
        المعاملات:
            percent: النسبة المئوية للاستخدام
            limit_type: نوع الحد (الساعي/اليومي)
            warned_set: مجموعة العتبات التي تم التحذير منها
        
        العائد:
            tuple: (can_continue: bool, message: str أو None)
        """
        with self._lock:
            for threshold, level, base_message in self.WARNING_THRESHOLDS:
                if percent >= threshold and threshold not in warned_set:
                    warned_set.add(threshold)
                    full_message = f'{base_message} ({limit_type}: {percent:.0f}%)'
                    
                    if self.log_fn:
                        try:
                            self.log_fn(full_message)
                        except Exception:
                            pass
                    
                    if level == 'critical' and self.notify_fn:
                        try:
                            self.notify_fn(full_message)
                        except Exception:
                            pass
                    
                    if level == 'stop':
                        return False, full_message
                    
                    return True, full_message
            
            return True, None
    
    def reset_warnings(self):
        """إعادة تعيين التحذيرات (عند بداية ساعة/يوم جديد)."""
        with self._lock:
            self._warned_thresholds_hourly.clear()
            self._warned_thresholds_daily.clear()
    
    def get_status_message(self) -> str:
        """
        الحصول على رسالة حالة الاستخدام الحالية.
        
        العائد:
            رسالة نصية تصف حالة الاستخدام
        """
        usage = self.tracker.get_usage()
        hourly_percent = usage['hourly_percent']
        daily_percent = usage['daily_percent']
        max_percent = max(hourly_percent, daily_percent)
        
        if max_percent >= 100:
            return '⛔ الحد الأقصى'
        elif max_percent >= 95:
            return '🔴 حرج'
        elif max_percent >= 85:
            return '🔶 تحذير'
        elif max_percent >= 70:
            return '⚠️ مرتفع'
        else:
            return '✅ طبيعي'


# ==================== Global API Tracker Instance ====================

# مثيل عام لتتبع API (يمكن استخدامه من جميع الوحدات)
# يستخدم نمط Singleton مع حماية من التنافس بين الخيوط
_global_api_tracker: Optional[APIUsageTracker] = None
_global_api_warning_system: Optional[APIWarningSystem] = None
_global_api_lock = threading.Lock()

# عدد طلبات API لكل عملية ستوري (رفع + نشر)
API_CALLS_PER_STORY = 2


def get_api_tracker(hourly_limit: int = 100, daily_limit: int = 1000) -> APIUsageTracker:
    """
    الحصول على مثيل متتبع API العام (Singleton).
    
    آمن للاستخدام من عدة خيوط (thread-safe).
    
    المعاملات:
        hourly_limit: الحد الساعي (يستخدم فقط عند الإنشاء الأول)
        daily_limit: الحد اليومي (يستخدم فقط عند الإنشاء الأول)
    
    العائد:
        مثيل APIUsageTracker
    """
    global _global_api_tracker
    if _global_api_tracker is None:
        with _global_api_lock:
            # Double-check locking pattern
            if _global_api_tracker is None:
                _global_api_tracker = APIUsageTracker(hourly_limit, daily_limit)
    return _global_api_tracker


def get_api_warning_system(log_fn: Callable = None, notify_fn: Callable = None) -> APIWarningSystem:
    """
    الحصول على مثيل نظام تحذيرات API العام (Singleton).
    
    آمن للاستخدام من عدة خيوط (thread-safe).
    
    المعاملات:
        log_fn: دالة التسجيل
        notify_fn: دالة الإشعار
    
    العائد:
        مثيل APIWarningSystem
    """
    global _global_api_warning_system
    tracker = get_api_tracker()
    
    with _global_api_lock:
        if _global_api_warning_system is None:
            _global_api_warning_system = APIWarningSystem(tracker, log_fn, notify_fn)
        else:
            # تحديث الدوال إذا تم تمريرها (بشكل آمن)
            if log_fn:
                _global_api_warning_system.log_fn = log_fn
            if notify_fn:
                _global_api_warning_system.notify_fn = notify_fn
    return _global_api_warning_system


# ==================== Smart Schedule Calculation ====================

# [DB] تعيين أيام الأسبوع إلى أرقام Python's datetime.weekday()
# Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
DAY_NAME_TO_NUMBER = {
    'sat': 5,  # Saturday
    'sun': 6,  # Sunday
    'mon': 0,  # Monday
    'tue': 1,  # Tuesday
    'wed': 2,  # Wednesday
    'thu': 3,  # Thursday
    'fri': 4,  # Friday
}

# [DB] العكس: من رقم اليوم إلى الاسم
NUMBER_TO_DAY_NAME = {v: k for k, v in DAY_NAME_TO_NUMBER.items()}


def calculate_next_run_timestamp(
    times_list: list,
    days_list: list,
    reference_time: datetime = None
) -> Optional[datetime]:
    """
    [DB] حساب الطابع الزمني للتشغيل القادم بناءً على قالب الجدولة الذكية.
    
    المعاملات:
        times_list: قائمة الأوقات (مثل ["08:00", "12:00", "18:00"])
        days_list: قائمة الأيام المسموحة (مثل ["sat", "sun", "mon", "tue", "wed", "thu", "fri"])
        reference_time: الوقت المرجعي (افتراضي: الآن)
    
    العائد:
        datetime للتشغيل القادم أو None إذا كانت القوائم فارغة
    
    الخوارزمية:
        1. إذا كان اليوم الحالي ضمن days_list:
           - البحث عن أقرب وقت لاحق في times_list لهذا اليوم
           - إذا وجد، إرجاعه
        2. إذا لم يُعثر على وقت اليوم أو اليوم ليس ضمن days_list:
           - الانتقال لليوم التالي المسموح
           - إرجاع أول وقت في ذلك اليوم
    """
    if not times_list or not days_list:
        return None
    
    # استخدام الوقت الحالي إذا لم يُحدد
    if reference_time is None:
        reference_time = datetime.now()
    
    # تحويل أسماء الأيام إلى أرقام وترتيبها
    allowed_day_numbers = sorted([
        DAY_NAME_TO_NUMBER.get(day.lower().strip(), -1)
        for day in days_list
        if day.lower().strip() in DAY_NAME_TO_NUMBER
    ])
    
    if not allowed_day_numbers:
        return None
    
    # [DB] تطبيع الأوقات لضمان تنسيق HH:MM
    def normalize_time(time_str: str) -> Optional[str]:
        """تطبيع الوقت إلى تنسيق HH:MM"""
        try:
            time_str = time_str.strip()
            parts = time_str.split(':')
            if len(parts) >= 2:
                hour = int(parts[0])
                minute = int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return f"{hour:02d}:{minute:02d}"
        except (ValueError, AttributeError):
            pass
        return None
    
    # تطبيع وترتيب الأوقات
    normalized_times = [normalize_time(t) for t in times_list]
    sorted_times = sorted([t for t in normalized_times if t is not None])
    
    if not sorted_times:
        return None
    
    # الحصول على رقم اليوم الحالي
    current_weekday = reference_time.weekday()
    current_time_str = reference_time.strftime("%H:%M")
    
    # التحقق مما إذا كان اليوم الحالي مسموحاً
    if current_weekday in allowed_day_numbers:
        # البحث عن أقرب وقت لاحق في اليوم الحالي
        for time_str in sorted_times:
            if time_str > current_time_str:
                # وجدنا وقتاً لاحقاً اليوم
                hour, minute = map(int, time_str.split(':'))
                next_run = reference_time.replace(
                    hour=hour, 
                    minute=minute, 
                    second=0, 
                    microsecond=0
                )
                return next_run
    
    # لم نجد وقتاً اليوم، ننتقل لليوم التالي المسموح
    # البحث عن أقرب يوم مسموح
    for days_ahead in range(1, 8):  # البحث في الأيام السبعة القادمة
        next_weekday = (current_weekday + days_ahead) % 7
        
        if next_weekday in allowed_day_numbers:
            # وجدنا اليوم التالي المسموح
            next_date = reference_time + timedelta(days=days_ahead)
            first_time = sorted_times[0]
            hour, minute = map(int, first_time.split(':'))
            
            next_run = next_date.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0
            )
            return next_run
    
    # إذا لم نجد (لا ينبغي أن يحدث مع قائمة أيام صحيحة)
    return None


def calculate_next_run_from_template(template: dict, reference_time: datetime = None) -> Optional[datetime]:
    """
    [DB] حساب الطابع الزمني للتشغيل القادم من قالب كامل.
    
    المعاملات:
        template: قاموس القالب (يحتوي على 'times' و 'days')
        reference_time: الوقت المرجعي (افتراضي: الآن)
    
    العائد:
        datetime للتشغيل القادم أو None
    """
    if not template:
        return None
    
    times_list = template.get('times', [])
    days_list = template.get('days', [])
    
    # إذا كانت قائمة الأيام فارغة، استخدم جميع الأيام للتوافق مع الإصدارات السابقة
    if not days_list:
        days_list = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]
    
    return calculate_next_run_timestamp(times_list, days_list, reference_time)


# ==================== متغيرات التاريخ والوقت في العنوان ====================

def get_date_placeholder(format_type: str = "ymd") -> str:
    """
    الحصول على التاريخ بصيغ مختلفة
    
    Args:
        format_type: نوع الصيغة
            - "ymd" → 2025-12-02
            - "dmy" → 02/12/2025
            - "time" → 2025-12-02 14:55
    
    Returns:
        التاريخ بالصيغة المطلوبة
    """
    now = datetime.now()
    
    if format_type == "ymd":
        return now.strftime("%Y-%m-%d")
    elif format_type == "dmy":
        return now.strftime("%d/%m/%Y")
    elif format_type == "time":
        return now.strftime("%Y-%m-%d %H:%M")
    else:
        return now.strftime("%Y-%m-%d")


def apply_title_placeholders(title: str, filename: str = "") -> str:
    """
    تطبيق جميع المتغيرات على العنوان
    
    المتغيرات المدعومة:
        {filename} - اسم الملف (بدون الامتداد)
        {date} - التاريخ (YYYY-MM-DD)
        {date_ymd} - التاريخ (YYYY-MM-DD)
        {date_dmy} - التاريخ (DD/MM/YYYY)
        {date_time} - التاريخ والوقت (YYYY-MM-DD HH:MM)
        {random_emoji} - إيموجي عشوائي
    
    Args:
        title: قالب العنوان
        filename: اسم الملف (اختياري)
    
    Returns:
        العنوان بعد استبدال المتغيرات
    
    مثال:
        >>> apply_title_placeholders("{filename} - {date} {random_emoji}", "my_video.mp4")
        "my_video - 2025-12-02 🔥"
    """
    if not title:
        return title
    
    # استبدال {filename}
    if filename:
        # إزالة الامتداد من اسم الملف
        name_without_ext = os.path.splitext(filename)[0]
        title = title.replace("{filename}", name_without_ext)
    
    # استبدال متغيرات التاريخ
    title = title.replace("{date}", get_date_placeholder("ymd"))
    title = title.replace("{date_ymd}", get_date_placeholder("ymd"))
    title = title.replace("{date_dmy}", get_date_placeholder("dmy"))
    title = title.replace("{date_time}", get_date_placeholder("time"))
    
    # استبدال {random_emoji}
    emojis = ["🔥", "❤️", "💯", "✨", "🎉", "👍", "💪", "🌟", "😍", "🎊"]
    title = title.replace("{random_emoji}", random.choice(emojis))
    
    return title
