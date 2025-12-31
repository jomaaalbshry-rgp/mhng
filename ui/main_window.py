"""
النافذة الرئيسية - Main Window
النافذة الرئيسية للتطبيق
Main application window
"""

import sys
import os
import time
import threading
import json
import base64
import shutil
import ctypes
import sqlite3
import tempfile
import socket
import subprocess
import random
import re
import gc
import traceback
from functools import partial
from pathlib import Path
import concurrent.futures
from datetime import datetime, timedelta
from typing import Optional, Tuple

from core import get_logger, log_info, log_error, log_warning, log_debug

import requests

# استيراد وحدات قاعدة البيانات والتشفير الآمن
from services import DatabaseManager, get_database_manager, initialize_database
# استيراد وحدة الوصول إلى البيانات - Import data access module
from services import (
    get_settings_file, get_jobs_file, get_database_file, migrate_old_files,
    save_hashtag_group, get_hashtag_groups, delete_hashtag_group,
    is_within_working_hours, calculate_time_to_working_hours_start,
    log_upload, get_upload_stats, reset_upload_stats, generate_text_chart,
    init_default_templates, ensure_default_templates,
    get_all_templates, get_template_by_id, save_template, delete_template,
    get_default_template, set_default_template, get_schedule_times_for_template
)
from secure_utils import encrypt_text as secure_encrypt, decrypt_text as secure_decrypt

# استيراد الوحدات المنفصلة للفيديو والستوري والريلز
from core import BaseJob
from controllers.video_controller import VideoJob, get_video_files, count_video_files
from controllers.story_controller import (
    StoryJob, get_story_files, count_story_files, get_next_story_batch,
    DEFAULT_STORIES_PER_SCHEDULE, DEFAULT_RANDOM_DELAY_MIN, DEFAULT_RANDOM_DELAY_MAX,
    upload_story, is_story_upload_successful, translate_fb_error,
    get_random_emoji, get_random_delay, simulate_human_behavior, log_error_to_file,
    safe_process_story_job
)
from controllers.reels_controller import ReelsJob, get_reels_files, count_reels_files, check_reels_duration
from services import get_pages, PageFetchWorker, TokenExchangeWorker, AllPagesFetchWorker
from core import (
    get_resource_path, get_subprocess_args, run_subprocess, create_popen, SmartUploadScheduler,
    APIUsageTracker, APIWarningSystem, get_api_tracker, get_api_warning_system,
    API_CALLS_PER_STORY, get_date_placeholder, apply_title_placeholders,
    make_job_key, get_job_key
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QTime, QThread
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QColor, QBrush, QFont, QFontMetrics, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QFileDialog, QSpinBox, QDoubleSpinBox, QTextEdit, QHBoxLayout, QVBoxLayout, QFormLayout, QGroupBox,
    QMessageBox, QComboBox, QProgressBar, QCheckBox, QFrame, QMenuBar, QStatusBar, QSystemTrayIcon, QMenu,
    QTabWidget, QTimeEdit, QDialog, QDialogButtonBox, QSlider, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QSizePolicy, QRadioButton, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtNetwork import QLocalSocket, QLocalServer

# استيراد الوحدات المعاد هيكلتها
from core import (
    SingleInstanceManager, SINGLE_INSTANCE_BASE_NAME,
    TokenExchangeThread, FetchPagesThread,
    TelegramNotifier, NotificationSystem,
    APP_TITLE, APP_DATA_FOLDER,
    RESUMABLE_THRESHOLD_BYTES, CHUNK_SIZE_DEFAULT,
    UPLOAD_TIMEOUT_START, UPLOAD_TIMEOUT_TRANSFER, UPLOAD_TIMEOUT_FINISH,
    UPLOADED_FOLDER_NAME, WATERMARK_FFMPEG_TIMEOUT, WATERMARK_MIN_OUTPUT_RATIO,
    WATERMARK_CLEANUP_DELAY, WATERMARK_FILE_CLOSE_DELAY,
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, STORY_EXTENSIONS,
    MAX_VIDEO_DURATION_SECONDS, INTERNET_CHECK_INTERVAL, INTERNET_CHECK_MAX_ATTEMPTS,
    PAGES_FETCH_LIMIT, PAGES_FETCH_MAX_ITERATIONS, PAGES_CACHE_DURATION_SECONDS,
    DEFAULT_TOKEN_EXPIRY_SECONDS, FACEBOOK_API_VERSION, FACEBOOK_API_TIMEOUT,
    THREAD_QUIT_TIMEOUT_MS, THREAD_TERMINATE_TIMEOUT_MS, SECRET_KEY
)
from ui.widgets import NoScrollComboBox, NoScrollSpinBox, NoScrollDoubleSpinBox, NoScrollSlider
from ui.dialogs import HashtagManagerDialog as HashtagManagerDialogBase
from ui.helpers import (
    create_fallback_icon, load_app_icon, get_icon,
    create_icon_button, create_icon_action,
    ICONS, ICON_COLORS, HAS_QTAWESOME,
    # Import formatting functions
    mask_token, seconds_to_value_unit, format_remaining_time,
    format_time_12h, format_datetime_12h
)
from ui.components import JobsTable, LogViewer, LogLevel, ProgressWidget

# استيراد المتحكمات - Import Controllers
from controllers import VideoController, StoryController, ReelsController, SchedulerController

# استيراد فئات الفيديو من video_panel - Import video classes from video_panel
from ui.panels import DraggablePreviewLabel, WatermarkPreviewDialog, StoryPanel, PagesPanel

# استيراد واجهة المجدول - Import Scheduler UI
from ui.scheduler_ui import SchedulerUI



# ==================== Helper Functions from admin.py ====================

def _set_windows_app_id(app_id: str = "JOMAA.PageManagement.1") -> bool:
    """
    تعيين Windows AppUserModelID لجعل إشعارات ويندوز تعرض اسم التطبيق الصحيح.
    يجب استدعاء هذه الدالة قبل إنشاء QApplication.

    المعاملات:
        app_id: معرّف فريد للتطبيق (يُستخدم في ويندوز لتمييز التطبيق).

    العائد:
        True إذا نجح التعيين، False خلاف ذلك.
    """
    if sys.platform != 'win32':
        return False
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except (AttributeError, OSError):
        return False


# محاولة استيراد qdarktheme
HAS_QDARKTHEME = False
QDT_VERSION = ""
try:
    import qdarktheme
    HAS_QDARKTHEME = True
    try:
        import importlib.metadata as _imd
        QDT_VERSION = _imd.version("qdarktheme")
    except Exception:
        QDT_VERSION = "unknown"
except Exception:
    HAS_QDARKTHEME = False


# APP_TITLE and APP_DATA_FOLDER have been moved to core/constants.py

# تنفيذ الترحيل عند تحميل الوحدة - Execute migration when module loads
migrate_old_files()

# ==================== Constants ====================
# All constants have been moved to core/constants.py
# They are imported above from core


# ==================== SQLite Database ====================
# Database path and init functions moved to services/data_access.py
# Note: init_database() is imported from services above

def migrate_json_to_sqlite():
    """
    ترحيل البيانات من ملفات JSON إلى SQLite عند أول تشغيل.
    Migrate data from JSON files to SQLite on first run.
    """
    db_path = get_database_file()
    jobs_file = get_jobs_file()
    settings_file = get_settings_file()

    # التحقق من وجود بيانات للترحيل
    if not jobs_file.exists() and not settings_file.exists():
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # ترحيل الوظائف
    if jobs_file.exists():
        try:
            with open(jobs_file, 'r', encoding='utf-8') as f:
                jobs_data = json.load(f)

            for job in jobs_data:
                cursor.execute('''
                    INSERT OR REPLACE INTO jobs
                    (page_id, page_name, folder, interval_seconds, page_access_token,
                     next_index, title_template, description_template, chunk_size,
                     use_filename_as_title, enabled, is_scheduled, next_run_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job.get('page_id'),
                    job.get('page_name', ''),
                    job.get('folder', ''),
                    job.get('interval_seconds', 10800),
                    job.get('page_access_token'),
                    job.get('next_index', 0),
                    job.get('title_template', '{filename}'),
                    job.get('description_template', ''),
                    job.get('chunk_size', CHUNK_SIZE_DEFAULT),
                    1 if job.get('use_filename_as_title', False) else 0,
                    1 if job.get('enabled', True) else 0,
                    1 if job.get('is_scheduled', False) else 0,
                    job.get('next_run_timestamp')
                ))
        except Exception:
            pass

    # ترحيل الإعدادات
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)

            for key, value in settings.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value)
                    VALUES (?, ?)
                ''', (key, json.dumps(value) if not isinstance(value, str) else value))
        except Exception:
            pass

    conn.commit()
    conn.close()


# ==================== App Tokens Management ====================
# استيراد الخدمات - Import Services
from services import FacebookAPIService, UploadService

# إنشاء نسخة من الخدمات - Create service instances
_facebook_api_service = FacebookAPIService(
    api_version=FACEBOOK_API_VERSION,
    api_timeout=FACEBOOK_API_TIMEOUT,
    default_token_expiry=DEFAULT_TOKEN_EXPIRY_SECONDS
)
_upload_service = UploadService(api_version='v17.0')

def get_all_app_tokens() -> list:
    """
    الحصول على جميع التطبيقات والتوكينات المحفوظة.
    Get all saved applications and tokens.

    العائد:
        قائمة من القواميس تحتوي على بيانات التطبيقات
        List of dictionaries containing app data
    """
    return FacebookAPIService.get_all_app_tokens(get_database_file(), simple_decrypt)


def save_app_token(app_name: str, app_id: str, app_secret: str = '',
                   short_lived_token: str = '', long_lived_token: str = '',
                   token_expires_at: str = None, token_id: int = None) -> Tuple[bool, Optional[int]]:
    """
    حفظ أو تحديث تطبيق وتوكيناته.
    Save or update application and its tokens.

    المعاملات:
        app_name: اسم التطبيق - App name
        app_id: معرف التطبيق - App ID
        app_secret: كلمة المرور - App secret
        short_lived_token: التوكن القصير - Short-lived token
        long_lived_token: التوكن الطويل - Long-lived token
        token_expires_at: تاريخ انتهاء التوكن - Token expiration date
        token_id: معرف التطبيق للتحديث (None لإضافة جديد) - App ID for update (None for new)

    العائد:
        tuple: (نجاح: bool, معرف السجل: int أو None)
        tuple: (success: bool, record ID: int or None)
    """
    return FacebookAPIService.save_app_token(
        get_database_file(), simple_encrypt, app_name, app_id, app_secret,
        short_lived_token, long_lived_token, token_expires_at, token_id
    )


def delete_app_token(token_id: int) -> bool:
    """
    حذف تطبيق من قاعدة البيانات.
    Delete application from database.

    المعاملات:
        token_id: معرف التطبيق - App ID

    العائد:
        True إذا نجح الحذف - True if deletion successful
    """
    return FacebookAPIService.delete_app_token(get_database_file(), token_id)


def exchange_token_for_long_lived(app_id: str, app_secret: str,
                                   short_lived_token: str) -> tuple:
    """
    تحويل التوكن القصير إلى توكن طويل (60 يوم) عبر Facebook Graph API.
    Exchange short-lived token for long-lived token (60 days) via Facebook Graph API.

    المعاملات:
        app_id: معرف التطبيق - App ID
        app_secret: كلمة المرور - App secret
        short_lived_token: التوكن القصير - Short-lived token

    العائد:
        tuple: (نجاح: bool, التوكن الطويل أو رسالة الخطأ: str, تاريخ الانتهاء: str أو None)
        tuple: (success: bool, long-lived token or error message: str, expiry date: str or None)
    """
    return _facebook_api_service.exchange_token_for_long_lived(app_id, app_secret, short_lived_token)


def get_all_long_lived_tokens() -> list:
    """
    الحصول على جميع التوكينات الطويلة الصالحة.
    Get all valid long-lived tokens.

    العائد:
        قائمة من التوكينات الطويلة - List of long-lived tokens
    """
    return FacebookAPIService.get_all_long_lived_tokens(get_database_file(), simple_decrypt)


# ==================== Thread Classes ====================
# TokenExchangeThread and FetchPagesThread have been moved to core/threads.py
# They are imported above from core


def send_telegram_error(error_type: str, message: str, job_name: str = None):
    """
    إرسال إشعار خطأ عبر Telegram.

    المعاملات:
        error_type: نوع الخطأ (مثل: 'خطأ في الرفع', 'خطأ في قاعدة البيانات')
        message: رسالة الخطأ التفصيلية
        job_name: اسم المهمة (اختياري)
    """
    try:
        if telegram_notifier.enabled and telegram_notifier.is_configured():
            def send_notification():
                try:
                    telegram_notifier.send_error_notification(
                        error_type=error_type,
                        message=message,
                        job_name=job_name
                    )
                except Exception:
                    pass  # تجاهل أخطاء الإشعارات
            threading.Thread(target=send_notification, daemon=True).start()
    except Exception:
        pass  # تجاهل أخطاء الإشعارات


# ==================== Hashtag Manager ====================

# ==================== Working Hours (Legacy - Removed) ====================
# تم إزالة نظام ساعات العمل واستبداله بنظام قوالب الجداول الذكية
# Functions moved to services/data_access.py

# ==================== نظام قوالب الجداول الذكية ====================
# Template management functions moved to services/data_access.py


# ==================== Internet Connectivity Check ====================

def check_internet_connection(timeout: int = 5, hosts: list = None) -> bool:
    """
    التحقق من الاتصال بالإنترنت عن طريق Ping لخوادم موثوقة.

    المعاملات:
        timeout: مهلة الاتصال بالثواني
        hosts: قائمة بالمضيفين للتحقق منهم

    العائد:
        True إذا كان هناك اتصال بالإنترنت، False خلاف ذلك
    """
    if hosts is None:
        hosts = [
            ('8.8.8.8', 53),        # Google DNS
            ('8.8.4.4', 53),        # Google DNS Secondary
            ('1.1.1.1', 53),        # Cloudflare DNS
            ('208.67.222.222', 53), # OpenDNS
        ]

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


def wait_for_internet(log_fn=None, check_interval: int = 60, max_attempts: int = 0) -> bool:
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


# ==================== Library Update System ====================

# قائمة المكتبات التي نتحقق من تحديثاتها
UPDATE_PACKAGES = ['requests', 'PySide6', 'pyqtdarktheme', 'qtawesome']


def _get_subprocess_windows_args() -> tuple:
    """
    الحصول على معاملات subprocess لإخفاء نافذة Console على Windows.

    العائد:
        tuple: (startupinfo, creationflags)
    """
    startupinfo = None
    creationflags = 0
    if sys.platform == 'win32':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = subprocess.CREATE_NO_WINDOW
    return startupinfo, creationflags


def check_for_updates(log_fn=None) -> list:
    """
    التحقق من وجود تحديثات للمكتبات.

    العائد:
        قائمة بالمكتبات التي تحتاج تحديث: [(name, current_version, latest_version), ...]
    """
    updates = []
    packages_lower = [p.lower() for p in UPDATE_PACKAGES]

    try:
        # إخفاء نافذة الـ Console على Windows
        startupinfo, creationflags = _get_subprocess_windows_args()

        # الحصول على قائمة المكتبات القديمة
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--outdated', '--format=json'],
            capture_output=True,
            text=True,
            timeout=30,  # تقليل من 60 إلى 30
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        if result.returncode == 0 and result.stdout.strip():
            try:
                outdated = json.loads(result.stdout)
                for pkg in outdated:
                    if pkg.get('name', '').lower() in packages_lower:
                        updates.append((
                            pkg.get('name'),
                            pkg.get('version'),
                            pkg.get('latest_version')
                        ))
            except json.JSONDecodeError:
                pass
    except subprocess.TimeoutExpired:
        if log_fn:
            log_fn('⚠️ انتهت مهلة التحقق من التحديثات')
    except Exception as e:
        if log_fn:
            log_fn(f'❌ خطأ في التحقق من التحديثات: {e}')

    return updates


def get_installed_versions() -> dict:
    """الحصول على إصدارات المكتبات المثبتة."""
    versions = {}

    try:
        # إخفاء نافذة الـ Console على Windows
        startupinfo, creationflags = _get_subprocess_windows_args()

        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--format=json'],
            capture_output=True,
            text=True,
            timeout=30,
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        if result.returncode == 0:
            installed = json.loads(result.stdout)

            for pkg in installed:
                if pkg['name'].lower() in [p.lower() for p in UPDATE_PACKAGES]:
                    versions[pkg['name']] = pkg['version']
    except Exception:
        pass

    return versions


def _validate_package_name(package_name: str) -> bool:
    """
    Validate package name to prevent command injection.
    التحقق من صحة اسم الحزمة لمنع حقن الأوامر.

    Args:
        package_name: Package name to validate

    Returns:
        True if valid, False otherwise
    """
    # Package names should only contain alphanumeric, hyphen, underscore, dot
    # Hyphen at end of character class to avoid escaping
    pattern = r'^[a-zA-Z0-9_.]+[a-zA-Z0-9_.-]*$'
    return bool(re.match(pattern, package_name))


def create_update_script(packages_to_update: list) -> str:
    """
    Create temporary update script.
    إنشاء سكربت التحديث المؤقت.

    Args:
        packages_to_update: List of package names to update

    Returns:
        Path to temporary script
    """
    # Validate all package names to prevent command injection
    for pkg in packages_to_update:
        if not _validate_package_name(pkg):
            raise ValueError(f"Invalid package name: {pkg}")

    # Only allow packages from our whitelist
    allowed_packages = [p.lower() for p in UPDATE_PACKAGES]
    validated_packages = [pkg for pkg in packages_to_update if pkg.lower() in allowed_packages]

    if not validated_packages:
        raise ValueError("No valid packages to update")

    packages_str = ' '.join(validated_packages)
    python_path = sys.executable
    script_path = os.path.abspath(sys.argv[0])

    if sys.platform == 'win32':
        # Windows batch script
        script_content = f'''@echo off
chcp 65001 > nul
echo.
echo ══════════════════════════════════════════════════
echo    جاري تحديث المكتبات - يرجى الانتظار...
echo ══════════════════════════════════════════════════
echo.
timeout /t 3 /nobreak > nul
"{python_path}" -m pip install --upgrade {packages_str}
echo.
echo ══════════════════════════════════════════════════
echo    ✅ تم التحديث بنجاح!
echo    جاري إعادة تشغيل البرنامج...
echo ══════════════════════════════════════════════════
echo.
timeout /t 2 /nobreak > nul
start "" "{python_path}" "{script_path}"
del "%~f0"
'''
        script_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.bat', delete=False, encoding='utf-8'
        )
    else:
        # Linux/Mac shell script
        script_content = f'''#!/bin/bash
echo ""
echo "══════════════════════════════════════════════════"
echo "   جاري تحديث المكتبات - يرجى الانتظار..."
echo "══════════════════════════════════════════════════"
echo ""
sleep 3
"{python_path}" -m pip install --upgrade {packages_str}
echo ""
echo "══════════════════════════════════════════════════"
echo "   ✅ تم التحديث بنجاح!"
echo "   جاري إعادة تشغيل البرنامج..."
echo "══════════════════════════════════════════════════"
echo ""
sleep 2
"{python_path}" "{script_path}" &
rm -- "$0"
'''
        script_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.sh', delete=False, encoding='utf-8'
        )

    script_file.write(script_content)
    script_file.close()

    # جعل السكربت قابل للتنفيذ على Linux/Mac
    if sys.platform != 'win32':
        os.chmod(script_file.name, 0o755)

    return script_file.name


def run_update_and_restart(packages_to_update: list):
    """
    تشغيل سكربت التحديث وإغلاق البرنامج.
    """
    script_path = create_update_script(packages_to_update)

    if sys.platform == 'win32':
        # تشغيل السكربت في نافذة جديدة
        os.startfile(script_path)
    else:
        # تشغيل السكربت في الخلفية
        subprocess.Popen(['bash', script_path], start_new_session=True)

    # إغلاق البرنامج
    sys.exit(0)


# ==================== Title Cleaner ====================

# كلمات يجب إزالتها من أسماء الملفات (lowercase فقط - المقارنة تتم بـ case-insensitive)
TITLE_CLEANUP_WORDS = [
    'hd', 'fhd', 'uhd', 'sd', '4k', '8k', '1080p', '720p', '480p', '360p', '240p',
    'mp4', 'mov', 'avi', 'mkv', 'wmv', 'flv', 'webm',
    'copyright', 'free', 'no copyright', 'royalty free', 'ncs', 'nocopyright',
    'official', 'video', 'clip', 'music', 'audio', 'lyrics', 'lyric',
    'download', 'full', 'complete', 'final', 'version', 'edit', 'remix',
    'www', 'http', 'https', 'com', 'net', 'org',
    'hq', 'lq', 'high quality', 'low quality',
]

# أنماط regex للتنظيف
TITLE_CLEANUP_PATTERNS = [
    r'\[.*?\]',           # إزالة النص بين الأقواس المربعة [...]
    r'\(.*?\)',           # إزالة النص بين الأقواس الدائرية (...)
    r'\{.*?\}',           # إزالة النص بين الأقواس المعقوصة {...}
    r'@\w+',              # إزالة mentions
    r'#\w+',              # إزالة hashtags من الاسم
    r'https?://\S+',      # إزالة الروابط
    r'\b\d{3,4}p\b',      # إزالة الدقة مثل 1080p, 720p
    r'\b[Hh][Dd]\b',      # إزالة HD
    r'\b[4-8][Kk]\b',     # إزالة 4K, 8K
    r'\b(19|20)\d{2}\b',  # إزالة السنوات (1900-2099)
]


def clean_filename_for_title(filename: str, remove_extension: bool = True) -> str:
    """
    تنظيف اسم الملف لاستخدامه كعنوان.

    المعاملات:
        filename: اسم الملف الأصلي
        remove_extension: إزالة امتداد الملف

    العائد:
        اسم الملف المُنظّف والمقروء
    """
    if not filename:
        return filename

    title = filename

    # إزالة الامتداد إذا طُلب
    if remove_extension:
        title = os.path.splitext(title)[0]

    # استبدال الرموز بمسافات
    title = title.replace('_', ' ')
    title = title.replace('-', ' ')
    title = title.replace('.', ' ')
    title = title.replace('+', ' ')
    title = title.replace('~', ' ')

    # تطبيق أنماط regex
    for pattern in TITLE_CLEANUP_PATTERNS:
        title = re.sub(pattern, '', title, flags=re.IGNORECASE)

    # إزالة الكلمات غير المرغوبة (TITLE_CLEANUP_WORDS already lowercase)
    words = title.split()
    cleaned_words = []
    for word in words:
        word_lower = word.lower().strip()
        # تحقق من الكلمات الكاملة فقط
        if word_lower not in TITLE_CLEANUP_WORDS:
            cleaned_words.append(word)

    title = ' '.join(cleaned_words)

    # إزالة المسافات المتعددة
    title = re.sub(r'\s+', ' ', title)

    # إزالة المسافات من البداية والنهاية
    title = title.strip()

    # تحويل الحرف الأول إلى حرف كبير
    if title:
        title = title[0].upper() + title[1:] if len(title) > 1 else title.upper()

    return title


# ==================== Random Jitter (Anti-Ban) ====================

def calculate_jitter_interval(base_interval: int, jitter_percent: int = 10) -> int:
    """
    حساب الفاصل الزمني مع نطاق عشوائي لمحاكاة السلوك البشري.

    المعاملات:
        base_interval: الفاصل الزمني الأساسي بالثواني
        jitter_percent: نسبة التباين المئوية (مثلاً 10 = ±10%)

    العائد:
        الفاصل الزمني مع التباين العشوائي
    """
    if jitter_percent <= 0:
        return base_interval

    # حساب نطاق التباين
    variation = int(base_interval * jitter_percent / 100)

    # إنشاء قيمة عشوائية ضمن النطاق
    jitter = random.randint(-variation, variation)

    # التأكد من أن النتيجة إيجابية (حد أدنى 10 ثواني)
    return max(10, base_interval + jitter)


# ==================== Video Sorting ====================

def sort_video_files(files: list, sort_by: str = 'name', reverse: bool = False) -> list:
    """
    ترتيب ملفات الفيديو حسب المعيار المحدد.

    المعاملات:
        files: قائمة مسارات الملفات (Path objects)
        sort_by: معيار الترتيب ('name', 'random', 'date_created', 'date_modified')
        reverse: عكس الترتيب

    العائد:
        القائمة المرتبة
    """
    if not files:
        return files

    if sort_by == 'random':
        # ترتيب عشوائي
        shuffled = list(files)
        random.shuffle(shuffled)
        return shuffled

    elif sort_by == 'date_created':
        # ترتيب حسب تاريخ الإنشاء
        try:
            return sorted(files, key=lambda f: f.stat().st_ctime, reverse=reverse)
        except Exception:
            return sorted(files, key=lambda f: f.name.lower(), reverse=reverse)

    elif sort_by == 'date_modified':
        # ترتيب حسب تاريخ التعديل
        try:
            return sorted(files, key=lambda f: f.stat().st_mtime, reverse=reverse)
        except Exception:
            return sorted(files, key=lambda f: f.name.lower(), reverse=reverse)

    else:
        # الافتراضي: ترتيب أبجدي
        return sorted(files, key=lambda f: f.name.lower(), reverse=reverse)


# ==================== Video Validation ====================

def validate_video(video_path: str, log_fn=None) -> dict:
    """
    التحقق من صحة ملف الفيديو قبل الرفع.

    المعاملات:
        video_path: مسار ملف الفيديو
        log_fn: دالة للتسجيل

    العائد:
        dict يحتوي على:
        - valid: bool - هل الملف صالح
        - duration: float - مدة الفيديو بالثواني
        - error: str - رسالة الخطأ إن وجدت
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    result = {'valid': False, 'duration': 0, 'error': None}

    if not os.path.exists(video_path):
        result['error'] = 'الملف غير موجود'
        return result

    # التحقق من حجم الملف
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        result['error'] = 'الملف فارغ'
        return result

    # محاولة استخدام ffprobe للتحقق من الفيديو
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        output = run_subprocess(cmd, timeout=30, text=True)

        if output.returncode == 0 and output.stdout.strip():
            duration = float(output.stdout.strip())
            result['valid'] = True
            result['duration'] = duration

            # التحقق من مدة الفيديو
            if duration > MAX_VIDEO_DURATION_SECONDS:
                result['valid'] = False
                result['error'] = 'مدة الفيديو تتجاوز الحد الأقصى (4 ساعات)'
        else:
            result['error'] = 'فشل في قراءة معلومات الفيديو'
    except FileNotFoundError:
        # ffprobe غير متوفر، نفترض صلاحية الملف
        _log('تحذير: ffprobe غير متوفر، تم تخطي التحقق من صحة الفيديو')
        result['valid'] = True
    except subprocess.TimeoutExpired:
        result['error'] = 'انتهت مهلة التحقق من الفيديو'
    except Exception as e:
        result['error'] = f'خطأ في التحقق: {str(e)}'

    return result


# ==================== FFmpeg Watermark ====================

def check_ffmpeg_available() -> dict:
    """
    التحقق من توفر FFmpeg على النظام.

    العائد:
        dict يحتوي على:
        - available: bool - هل FFmpeg متوفر
        - version: str - إصدار FFmpeg
        - path: str - مسار FFmpeg
    """
    result = {'available': False, 'version': None, 'path': None}

    try:
        output = run_subprocess(['ffmpeg', '-version'], timeout=10, text=True)
        if output.returncode == 0:
            result['available'] = True
            # استخراج الإصدار من السطر الأول
            first_line = output.stdout.split('\n')[0]
            result['version'] = first_line

        # محاولة إيجاد المسار
        if sys.platform == 'win32':
            where_output = run_subprocess(['where', 'ffmpeg'], timeout=10, text=True)
            if where_output.returncode == 0:
                result['path'] = where_output.stdout.strip().split('\n')[0]
        else:
            which_output = run_subprocess(['which', 'ffmpeg'], timeout=10, text=True)
            if which_output.returncode == 0:
                result['path'] = which_output.stdout.strip()
    except FileNotFoundError:
        result['available'] = False
    except Exception:
        pass

    return result


def add_watermark(video_path: str, logo_path: str, output_path: str,
                  position: str = 'bottom_right', opacity: float = 0.8,
                  progress_callback=None) -> dict:
    """
    إضافة علامة مائية على الفيديو باستخدام FFmpeg.

    المعاملات:
        video_path: مسار الفيديو الأصلي
        logo_path: مسار ملف الشعار
        output_path: مسار الفيديو الناتج
        position: موقع الشعار (top_left, top_right, bottom_left, bottom_right, center)
        opacity: مستوى الشفافية (0.0 - 1.0)
        progress_callback: دالة لإظهار التقدم

    العائد:
        dict يحتوي على نجاح/فشل العملية
    """
    result = {'success': False, 'error': None, 'output_path': output_path}

    if not os.path.exists(video_path):
        result['error'] = 'ملف الفيديو غير موجود'
        return result

    if not os.path.exists(logo_path):
        result['error'] = 'ملف الشعار غير موجود'
        return result

    # تحديد موقع الشعار
    position_map = {
        'top_left': 'overlay=10:10',
        'top_right': 'overlay=main_w-overlay_w-10:10',
        'bottom_left': 'overlay=10:main_h-overlay_h-10',
        'bottom_right': 'overlay=main_w-overlay_w-10:main_h-overlay_h-10',
        'center': 'overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2'
    }

    overlay_filter = position_map.get(position, position_map['bottom_right'])

    # بناء الأمر
    filter_complex = f"[1:v]format=rgba,colorchannelmixer=aa={opacity}[logo];[0:v][logo]{overlay_filter}"

    cmd = [
        'ffmpeg', '-y', '-i', video_path, '-i', logo_path,
        '-filter_complex', filter_complex,
        '-codec:a', 'copy',
        output_path
    ]

    try:
        process = create_popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        _, stderr = process.communicate()

        if process.returncode == 0:
            result['success'] = True
        else:
            result['error'] = f'فشل FFmpeg: {stderr[:500]}'
    except FileNotFoundError:
        result['error'] = 'FFmpeg غير مثبت على النظام'
    except Exception as e:
        result['error'] = f'خطأ: {str(e)}'

    return result


# تهيئة قاعدة البيانات عند تحميل الوحدة
# Database is initialized in admin.py before this module is imported
# Step 1: Run legacy database initialization for other tables
migrate_json_to_sqlite()

# Step 2: Run legacy template initialization (for backwards compatibility)
init_default_templates()  # إنشاء قوالب الجداول الافتراضية
ensure_default_templates()  # ضمان وجود القوالب الافتراضية (للترقية)


def simple_encrypt(plain: str) -> str:
    """
    تشفير النص باستخدام نظام التشفير الآمن الجديد.
    يستخدم Fernet إذا كان متاحاً، وإلا يستخدم XOR للتوافقية.
    """
    return secure_encrypt(plain)


def simple_decrypt(enc: str) -> str:
    """
    فك تشفير النص باستخدام نظام التشفير الآمن الجديد.
    يدعم فك تشفير البيانات المشفرة بالنظام القديم (XOR) للتوافقية.
    """
    return secure_decrypt(enc)


# ==================== Notification Systems ====================
# TelegramNotifier and NotificationSystem have been moved to core/notifications.py
# They are imported above from core

# مثيل عام لنظام إشعارات Telegram
telegram_notifier = TelegramNotifier()


# ==================== Light Theme Fallback ====================

LIGHT_THEME_FALLBACK = """
QWidget {
    background-color: #f5f5f5;
    color: #333333;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 15px;
    color: #333333;
}

QGroupBox::title {
    color: #333333;
    background-color: #ffffff;
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}

QPushButton {
    background-color: #e0e0e0;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #d0d0d0;
}

QPushButton:pressed {
    background-color: #c0c0c0;
}

QPushButton:disabled {
    background-color: #f0f0f0;
    color: #999999;
    border-color: #ddd;
}

QLineEdit, QSpinBox, QComboBox, QTimeEdit, QDateEdit {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px;
}

QListWidget {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ddd;
}

QListWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QTextEdit {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ddd;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: #ffffff;
}

QTabWidget::pane {
    background-color: #ffffff;
    border: 1px solid #ddd;
}

QTabBar::tab {
    background-color: #e0e0e0;
    color: #333333;
    padding: 8px 16px;
    border: 1px solid #ccc;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    border-bottom: none;
    color: #0078d4;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #d8d8d8;
}

QLabel {
    color: #333333;
    background-color: transparent;
}

QCheckBox {
    color: #333333;
}

QSlider::groove:horizontal {
    background-color: #ddd;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background-color: #0078d4;
    width: 16px;
    height: 16px;
    border-radius: 8px;
    margin: -5px 0;
}

QProgressBar {
    background-color: #e0e0e0;
    border: 1px solid #ccc;
    border-radius: 4px;
    text-align: center;
    color: #333333;
}

QProgressBar::chunk {
    background-color: #28a745;
    border-radius: 3px;
}

QMenuBar {
    background-color: #f0f0f0;
    color: #333333;
    border-bottom: 1px solid #ddd;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #e0e0e0;
}

QMenu {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ddd;
}

QMenu::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QTableWidget {
    background-color: #ffffff;
    color: #333333;
    gridline-color: #ddd;
    border: 1px solid #ddd;
}

QTableWidget::item {
    background-color: #ffffff;
    color: #333333;
    padding: 4px;
}

QTableWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #e0e0e0;
    color: #333333;
    padding: 6px;
    border: 1px solid #ccc;
    font-weight: bold;
}

QToolTip {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px 8px;
}
"""

CUSTOM_STYLES = """
QPushButton {
  background-color: #2e3440;
  color: #e6e6e6;
  border: 1px solid #3b4252;
  border-radius: 6px;
  padding: 6px 12px;
}
QPushButton:hover { background-color: #3b4252; }
QPushButton:pressed { background-color: #2b303b; }
QPushButton:disabled { background-color: #1f232b; color: #8a8f98; border-color: #2a2f38; }
QCheckBox { text-decoration: none; border: 0; }
QToolTip {
  background-color: #2e3440;
  color: #e6e6e6;
  border: 1px solid #3b4252;
  border-radius: 4px;
  padding: 4px 8px;
}
QLineEdit[readonly="true"] {
  background-color: #1f2329;
  color: #bdc3c7;
}
QGroupBox {
  border: 1px solid #3b4252;
  border-radius: 6px;
  margin-top: 8px;
  padding-top: 18px;
}
QGroupBox::title {
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 6px;
  background-color: transparent;
}
/* تحسين ألوان التبويبات للثيم الداكن */
QTabWidget::pane {
  border: 1px solid #3b4252;
  background-color: #2e3440;
  border-radius: 4px;
}
QTabBar::tab {
  background-color: #2e3440;
  color: #e6e6e6;
  border: 1px solid #3b4252;
  border-bottom: none;
  padding: 8px 16px;
  margin-right: 2px;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
}
QTabBar::tab:selected {
  background-color: #3b4252;
  color: #88c0d0;
  font-weight: bold;
}
QTabBar::tab:hover:!selected {
  background-color: #434c5e;
}
QTabBar::tab:!selected {
  margin-top: 2px;
}
/* إصلاح ألوان جدول الإحصائيات للثيم الداكن */
QTableWidget {
  background-color: #2e3440;
  color: #e6e6e6;
  gridline-color: #3b4252;
  border: 1px solid #3b4252;
}
QTableWidget::item {
  background-color: #2e3440;
  color: #e6e6e6;
  padding: 4px;
}
QTableWidget::item:selected {
  background-color: #3b4252;
  color: #88c0d0;
}
QHeaderView::section {
  background-color: #3b4252;
  color: #e6e6e6;
  padding: 6px;
  border: 1px solid #434c5e;
  font-weight: bold;
}
QComboBox {
  background-color: #2e3440;
  color: #e6e6e6;
  border: 1px solid #3b4252;
  border-radius: 4px;
  padding: 4px 8px;
}
QComboBox::drop-down {
  border: none;
}
QComboBox QAbstractItemView {
  background-color: #2e3440;
  color: #e6e6e6;
  selection-background-color: #3b4252;
  selection-color: #88c0d0;
  border: 1px solid #3b4252;
}
"""

# ألوان العدّاد الزمني للوظائف
COUNTDOWN_COLOR_GREEN = '#27ae60'   # أخضر: ≥5 دقائق
COUNTDOWN_COLOR_YELLOW = '#f39c12'  # أصفر: 1-5 دقائق
COUNTDOWN_COLOR_RED = '#e74c3c'     # أحمر: <1 دقيقة
COUNTDOWN_COLOR_GRAY = '#808080'    # رمادي: معطّل

# نصوص الوقت المتبقي
REMAINING_TIME_RUNNING = "⏰ جاري التشغيل..."  # نص يظهر عند تشغيل الوظيفة
REMAINING_TIME_NOT_SCHEDULED = "---"  # نص يظهر للوظائف غير المجدولة

class PageJob:
    """
    تمثيل وظيفة رفع فيديوهات لصفحة فيسبوك.

    ملاحظة ترتيب الأقفال:
    - _state_lock: قفل خفيف لحماية enabled و cancel_requested (لا يجب الاحتفاظ به أثناء I/O)
    - lock: قفل لمنع التشغيل المتزامن لعمليات الرفع (يمكن الاحتفاظ به لفترة طويلة)

    لا يجب أبداً الحصول على _state_lock أثناء الاحتفاظ بـ lock لتجنب حالات الجمود.

    الفرق بين enabled و is_scheduled:
    - enabled: حالة التفعيل (مفعّل/معطّل) - لا يؤثر على العدّاد أو الجدولة
    - is_scheduled: حالة الجدولة الفعلية - عند True يبدأ العدّاد والجدولة
    """
    def __init__(self, page_id, page_name, folder,
                 interval_seconds=10800,
                 page_access_token=None,
                 title_template="{filename}",
                 description_template="",
                 chunk_size=CHUNK_SIZE_DEFAULT,
                 use_filename_as_title=False,
                 enabled=True,
                 is_scheduled=False,
                 next_run_timestamp=None,
                 sort_by='name',
                 jitter_enabled=False,
                 jitter_percent=10,
                 watermark_enabled=False,
                 watermark_path='',
                 watermark_position='bottom_right',
                 watermark_opacity=0.8,
                 watermark_scale=0.15,
                 use_smart_schedule=False,
                 template_id=None,
                 app_name=''):
        self.page_id = page_id
        self.page_name = page_name
        self.app_name = app_name  # اسم التطبيق المصدر للصفحة
        self.folder = folder
        self.interval_seconds = int(interval_seconds)
        self.page_access_token = page_access_token
        self.next_index = 0
        self.title_template = title_template
        self.description_template = description_template
        self.chunk_size = chunk_size
        self.use_filename_as_title = use_filename_as_title
        self._enabled = enabled
        self._is_scheduled = is_scheduled
        self._cancel_requested = False
        # ختم وقت يونكس للتشغيل التالي - إذا لم يُحدد يتم تعيينه إلى الآن + الفاصل الزمني
        self._next_run_timestamp = next_run_timestamp if next_run_timestamp is not None else (time.time() + max(1, int(interval_seconds)))
        # قفل خفيف لحماية القيم البولية - لا يحتفظ به أثناء عمليات I/O
        self._state_lock = threading.Lock()
        # قفل لمنع التشغيل المتزامن لعمليات الرفع - قد يحتفظ به لفترة طويلة
        self.lock = threading.Lock()
        # خيارات جديدة
        self.sort_by = sort_by  # 'name', 'random', 'date_created', 'date_modified'
        self.jitter_enabled = jitter_enabled  # تفعيل التوقيت العشوائي
        self.jitter_percent = jitter_percent  # نسبة التباين %
        # إعدادات العلامة المائية لكل مهمة
        self.watermark_enabled = watermark_enabled
        self.watermark_path = watermark_path
        self.watermark_position = watermark_position
        self.watermark_opacity = watermark_opacity
        self.watermark_scale = watermark_scale
        # إحداثيات العلامة المائية المخصصة (من السحب بالماوس)
        self.watermark_x = None  # إحداثي X (None = استخدام position)
        self.watermark_y = None  # إحداثي Y (None = استخدام position)
        # إعدادات الجدولة الذكية
        self.use_smart_schedule = use_smart_schedule
        self.template_id = template_id

    @property
    def enabled(self):
        """الحصول على حالة التفعيل بشكل آمن من الـ threads."""
        with self._state_lock:
            return self._enabled

    @enabled.setter
    def enabled(self, value):
        """تعيين حالة التفعيل بشكل آمن من الـ threads."""
        with self._state_lock:
            self._enabled = value

    @property
    def is_scheduled(self):
        """الحصول على حالة الجدولة بشكل آمن من الـ threads."""
        with self._state_lock:
            return self._is_scheduled

    @is_scheduled.setter
    def is_scheduled(self, value):
        """تعيين حالة الجدولة بشكل آمن من الـ threads."""
        with self._state_lock:
            self._is_scheduled = value

    @property
    def cancel_requested(self):
        """الحصول على حالة طلب الإلغاء بشكل آمن من الـ threads."""
        with self._state_lock:
            return self._cancel_requested

    @cancel_requested.setter
    def cancel_requested(self, value):
        """تعيين حالة طلب الإلغاء بشكل آمن من الـ threads."""
        with self._state_lock:
            self._cancel_requested = value

    def check_and_reset_cancel(self):
        """التحقق من حالة الإلغاء وإعادة ضبطها بشكل ذري."""
        with self._state_lock:
            if self._cancel_requested:
                self._cancel_requested = False
                return True
            return False

    @property
    def next_run_timestamp(self):
        """الحصول على ختم وقت التشغيل التالي بشكل آمن من الـ threads."""
        with self._state_lock:
            return self._next_run_timestamp

    @next_run_timestamp.setter
    def next_run_timestamp(self, value):
        """تعيين ختم وقت التشغيل التالي بشكل آمن من الـ threads."""
        with self._state_lock:
            self._next_run_timestamp = value

    def reset_next_run_timestamp(self):
        """
        إعادة ضبط وقت التشغيل التالي.

        تستخدم الجدولة الذكية إذا كانت مفعلة (use_smart_schedule=True و template_id موجود)،
        وإلا تستخدم الفاصل الزمني التقليدي.
        """
        next_time = None

        # محاولة استخدام الجدولة الذكية إذا كانت مفعلة
        if self.use_smart_schedule and self.template_id is not None:
            try:
                # استيراد محلي لتجنب الاستيراد الدائري
                from core import calculate_next_run_from_template
                from services import get_database_manager

                # الحصول على القالب من قاعدة البيانات
                db = get_database_manager()
                template = db.get_template_by_id(self.template_id)

                if template:
                    from datetime import datetime
                    next_datetime = calculate_next_run_from_template(template)

                    if next_datetime:
                        next_time = next_datetime.timestamp()
                        log_debug(f"[SmartSchedule] الوقت التالي للوظيفة {self.page_name}: {next_datetime.strftime('%Y-%m-%d %H:%M')}")
                    else:
                        log_warning(f"[SmartSchedule] فشل حساب الوقت التالي من القالب {self.template_id} - استخدام الفاصل الزمني")
                else:
                    log_warning(f"[SmartSchedule] القالب {self.template_id} غير موجود - استخدام الفاصل الزمني")

            except Exception as e:
                log_warning(f"[SmartSchedule] خطأ في حساب الوقت من القالب: {e} - استخدام الفاصل الزمني")

        # إذا فشلت الجدولة الذكية أو لم تكن مفعلة، استخدم الفاصل الزمني
        if next_time is None:
            # تطبيق التوقيت العشوائي إذا كان مفعّلاً
            interval = self.interval_seconds
            if self.jitter_enabled and self.jitter_percent > 0:
                interval = calculate_jitter_interval(interval, self.jitter_percent)
            next_time = time.time() + max(1, int(interval))

        self.next_run_timestamp = next_time

    def to_dict(self):
        return {
            'page_id': self.page_id,
            'page_name': self.page_name,
            'app_name': self.app_name,
            'folder': self.folder,
            'interval_seconds': self.interval_seconds,
            'page_access_token': self.page_access_token,
            'next_index': self.next_index,
            'title_template': self.title_template,
            'description_template': self.description_template,
            'chunk_size': self.chunk_size,
            'use_filename_as_title': self.use_filename_as_title,
            'enabled': self.enabled,
            'is_scheduled': self.is_scheduled,
            'next_run_timestamp': self.next_run_timestamp,
            'sort_by': self.sort_by,
            'jitter_enabled': self.jitter_enabled,
            'jitter_percent': self.jitter_percent,
            'watermark_enabled': self.watermark_enabled,
            'watermark_path': self.watermark_path,
            'watermark_position': self.watermark_position,
            'watermark_opacity': self.watermark_opacity,
            'watermark_scale': self.watermark_scale,
            'watermark_x': self.watermark_x,
            'watermark_y': self.watermark_y,
            'use_smart_schedule': self.use_smart_schedule,
            'template_id': self.template_id
        }

    @classmethod
    def from_dict(cls, d):
        secs = d.get('interval_seconds', 10800)
        # إذا كان next_run_timestamp محفوظاً نستخدمه، وإلا نعيّنه إلى الآن + الفاصل الزمني
        saved_timestamp = d.get('next_run_timestamp')
        obj = cls(
            d['page_id'],
            d.get('page_name', ''),
            d.get('folder', ''),
            secs,
            d.get('page_access_token'),
            d.get('title_template', "{filename}"),
            d.get('description_template', ""),
            d.get('chunk_size', CHUNK_SIZE_DEFAULT),
            d.get('use_filename_as_title', False),
            d.get('enabled', True),
            d.get('is_scheduled', False),
            next_run_timestamp=saved_timestamp,
            sort_by=d.get('sort_by', 'name'),
            jitter_enabled=d.get('jitter_enabled', False),
            jitter_percent=d.get('jitter_percent', 10),
            watermark_enabled=d.get('watermark_enabled', False),
            watermark_path=d.get('watermark_path', ''),
            watermark_position=d.get('watermark_position', 'bottom_right'),
            watermark_opacity=d.get('watermark_opacity', 0.8),
            watermark_scale=d.get('watermark_scale', 0.15),
            use_smart_schedule=d.get('use_smart_schedule', False),
            template_id=d.get('template_id'),
            app_name=d.get('app_name', '')
        )
        obj.next_index = d.get('next_index', 0)
        obj.watermark_x = d.get('watermark_x')
        obj.watermark_y = d.get('watermark_y')
        return obj


def apply_template(template_str, page_job: PageJob, filename: str, file_index: int, total_files: int):
    """
    تطبيق قالب على النص مع استبدال المتغيرات.

    المتغيرات المدعومة:
        {filename} - اسم الملف
        {page_name} - اسم الصفحة
        {page_id} - معرف الصفحة
        {index} - رقم الملف الحالي
        {total} - إجمالي الملفات
        {datetime} - التاريخ والوقت
        {date} - التاريخ فقط (YYYY-MM-DD)
        {date_ymd} - التاريخ (YYYY-MM-DD)
        {date_dmy} - التاريخ (DD/MM/YYYY)
        {date_time} - التاريخ والوقت (YYYY-MM-DD HH:MM)
        {time} - الوقت فقط
        {day} - اسم اليوم بالعربية
        {random_emoji} - إيموجي عشوائي
    """
    now = datetime.now()
    days_ar = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']

    repl = {
        'filename': filename,
        'page_name': page_job.page_name,
        'page_id': page_job.page_id,
        'index': file_index,
        'total': total_files,
        'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
        'date': now.strftime('%Y-%m-%d'),
        'date_ymd': now.strftime('%Y-%m-%d'),
        'date_dmy': now.strftime('%d/%m/%Y'),
        'date_time': now.strftime('%Y-%m-%d %H:%M'),
        'time': now.strftime('%H:%M'),
        'day': days_ar[now.weekday()],
        'random_emoji': get_random_emoji(),
    }
    out = template_str or ""
    for k, v in repl.items():
        out = out.replace(f'{{{k}}}', str(v))
    return out


def move_video_to_uploaded_folder(video_path: str, log_fn=None) -> bool:
    """
    نقل ملف الفيديو إلى مجلد فرعي باسم 'Uploaded' داخل نفس المجلد الأب.

    - إذا لم يكن مجلد 'Uploaded' موجوداً يتم إنشاؤه تلقائياً.
    - في حالة وجود ملف بنفس الاسم في مجلد Uploaded، يتم إعادة تسميته بإضافة رقم مميز.
    - يتم إرجاع True فقط إذا تم نقل الملف فعلياً والتأكد من وجوده في الوجهة.
    - جميع الأخطاء تُسجل في السجل بوضوح.

    المعاملات:
        video_path: المسار الكامل لملف الفيديو المراد نقله.
        log_fn: دالة اختيارية للتسجيل (logging).

    الاستخدام:
        يتم استدعاء هذه الدالة بعد نجاح رفع الفيديو لنقله تلقائياً.
    """

    def _log(msg):
        if log_fn:
            log_fn(msg)

    # التحقق من صحة المسار المُدخل
    if not video_path:
        _log('خطأ: مسار الفيديو فارغ أو غير صالح')
        return False

    try:
        video_file = Path(video_path)
    except Exception as e:
        _log(f'خطأ في تحليل مسار الملف: {video_path} - {e}')
        return False

    # التحقق من وجود الملف المصدر فعلياً
    if not video_file.exists():
        _log(f'فشل النقل: الملف المصدر غير موجود: {video_path}')
        return False

    if not video_file.is_file():
        _log(f'فشل النقل: المسار ليس ملفاً صالحاً: {video_path}')
        return False

    parent_folder = video_file.parent
    uploaded_folder = parent_folder / UPLOADED_FOLDER_NAME

    # إنشاء مجلد Uploaded إذا لم يكن موجوداً
    if not uploaded_folder.exists():
        try:
            uploaded_folder.mkdir(parents=True, exist_ok=True)
            _log(f'تم إنشاء مجلد Uploaded: {uploaded_folder}')
        except PermissionError as e:
            _log(f'فشل إنشاء مجلد Uploaded - خطأ صلاحيات: {uploaded_folder} - {e}')
            return False
        except OSError as e:
            _log(f'فشل إنشاء مجلد Uploaded - خطأ نظام الملفات: {uploaded_folder} - {e}')
            return False
        except Exception as e:
            _log(f'فشل إنشاء مجلد Uploaded - خطأ غير متوقع: {uploaded_folder} - {e}')
            return False

    # التأكد من وجود المجلد بعد الإنشاء
    if not uploaded_folder.exists():
        _log(f'فشل النقل: مجلد Uploaded لم يُنشأ رغم عدم وجود خطأ: {uploaded_folder}')
        return False

    if not uploaded_folder.is_dir():
        _log(f'فشل النقل: المسار {uploaded_folder} موجود لكنه ليس مجلداً')
        return False

    # معالجة حالة تكرار اسم الملف
    target_path = uploaded_folder / video_file.name
    if target_path.exists():
        # إضافة رقم مميز لتجنب التكرار
        base_name = video_file.stem
        extension = video_file.suffix
        counter = 1
        max_attempts = 1000  # حد أقصى لمنع حلقة لا نهائية
        while target_path.exists() and counter < max_attempts:
            new_name = f"{base_name}_{counter}{extension}"
            target_path = uploaded_folder / new_name
            counter += 1

        if target_path.exists():
            _log(f'فشل النقل: لا يمكن إيجاد اسم فريد للملف بعد {max_attempts} محاولة')
            return False

        _log(f'تم إعادة تسمية الملف لتجنب التكرار: {target_path.name}')

    # نقل الملف
    try:
        shutil.move(str(video_file), str(target_path))
    except PermissionError as e:
        _log(f'فشل نقل الفيديو - خطأ صلاحيات: {video_file} -> {target_path} - {e}')
        return False
    except shutil.Error as e:
        _log(f'فشل نقل الفيديو - خطأ shutil: {video_file} -> {target_path} - {e}')
        return False
    except OSError as e:
        _log(f'فشل نقل الفيديو - خطأ نظام الملفات: {video_file} -> {target_path} - {e}')
        return False
    except Exception as e:
        _log(f'فشل نقل الفيديو - خطأ غير متوقع: {video_file} -> {target_path} - {e}')
        return False

    # التحقق من أن الملف نُقل فعلاً إلى الوجهة
    if not target_path.exists():
        _log(f'فشل النقل: الملف لم يظهر في الوجهة بعد عملية النقل: {target_path}')
        return False

    # التحقق من أن الملف الأصلي لم يعد موجوداً (تم نقله وليس نسخه)
    # ملاحظة: في حالة النقل بين أنظمة ملفات مختلفة، قد يقوم shutil.move بنسخ ثم حذف
    # إذا بقي الملف الأصلي، فهذا يعني أن الحذف فشل - نسجل تحذير لكن لا نعتبره فشلاً
    # لأن الهدف الأساسي (وجود الملف في Uploaded) تحقق
    if video_file.exists():
        _log(f'تحذير: الملف الأصلي لا يزال موجوداً بعد النقل (قد يكون نقل عبر أنظمة ملفات): {video_file}')

    _log(f'تم نقل الفيديو بنجاح إلى: {target_path}')
    return True


def is_upload_successful(status, body) -> bool:
    """
    التحقق من نجاح عملية رفع الفيديو إلى فيسبوك.
    Check if video upload to Facebook was successful.

    يُعتبر الرفع ناجحاً إذا:
    - كان status code بين 200-299
    - واستجابة الـ body تحتوي على id للفيديو (ولا تحتوي على خطأ)

    المعاملات:
        status: كود حالة HTTP للاستجابة - HTTP status code
        body: جسم الاستجابة (dict أو str) - Response body (dict or str)

    العائد:
        True إذا نجح الرفع، False خلاف ذلك
        True if upload successful, False otherwise
    """
    return _upload_service.is_upload_successful(status, body)


def is_rate_limit_error(body) -> bool:
    """
    التحقق مما إذا كان الخطأ هو Rate Limit من فيسبوك.
    Check if error is a Rate Limit error from Facebook.

    كود الخطأ 4 = Application request limit reached

    المعاملات:
        body: جسم الاستجابة (dict) - Response body (dict)

    العائد:
        True إذا كان خطأ Rate Limit، False خلاف ذلك
        True if Rate Limit error, False otherwise
    """
    return _upload_service.is_rate_limit_error(body)


class UiSignals(QObject):
    log_signal = Signal(str)
    progress_signal = Signal(int, str)
    clear_progress_signal = Signal()
    job_enabled_changed = Signal(str, bool)  # page_id, enabled
    # إشارات لاختبار Telegram والتحديثات - لضمان تحديث الواجهة من الخيط الرئيسي
    telegram_test_result = Signal(bool, str)  # success, message
    update_check_finished = Signal()  # إشارة لإنهاء التحقق من التحديثات


class JobListItemWidget(QWidget):
    """ويدجت مخصص لعنصر الوظيفة في القائمة مع عدّاد ملوّن في مكان ثابت."""

    # ثوابت لعرض الأعمدة الثابتة
    COUNTDOWN_WIDTH = 120
    STATUS_WIDTH = 80
    MARGINS_WIDTH = 40  # الهوامش والمسافات

    def __init__(self, job, parent=None):  # يقبل PageJob أو StoryJob
        super().__init__(parent)
        self.job = job
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        # ترتيب الأعمدة بحيث يظهر العدّاد أولاً (أقصى اليسار في LTR = أقصى اليمين في RTL)
        # ثم الحالة، ثم معلومات الوظيفة

        # عدّاد الوقت المتبقي (عرض ثابت مع خلفية مميزة)
        self.countdown_label = QLabel()
        self.countdown_label.setFixedWidth(self.COUNTDOWN_WIDTH)
        self.countdown_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.countdown_label)

        # مؤشر حالة الوظيفة (مفعّلة/معطّلة + مجدولة/غير مجدولة) - عمود ثابت
        self.status_label = QLabel()
        self.status_label.setFixedWidth(self.STATUS_WIDTH)
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # معلومات الوظيفة (تأخذ المساحة المتبقية مع اقتطاع النص الطويل)
        self.info_label = QLabel()
        self.info_label.setMinimumWidth(100)
        self.info_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # محاذاة النص لليمين
        layout.addWidget(self.info_label, 1)  # stretch=1 للتمدد

        self.update_display()

    def _elide_text(self, text: str, max_width: int) -> str:
        """اقتطاع النص مع إضافة ... إذا تجاوز العرض المحدد."""
        fm = QFontMetrics(self.info_label.font())
        return fm.elidedText(text, Qt.ElideMiddle, max_width)

    def update_display(self, remaining_seconds=None, outside_working_hours=False, time_to_working_hours=0):
        """تحديث عرض معلومات الوظيفة والعدّاد (Requirement 1 - العداد الذكي)."""

        # التحقق من نظام الجدولة المستخدم (ذكي أو فاصل زمني)
        use_smart_schedule = getattr(self.job, 'use_smart_schedule', False)
        template_id = getattr(self.job, 'template_id', None)

        if use_smart_schedule and template_id:
            # عرض اسم القالب عند استخدام الجدولة الذكية
            template = get_template_by_id(template_id)
            if template:
                schedule_info = f"📅 {template['name']}"
            else:
                # القالب غير موجود - العودة للفاصل الزمني
                val, unit = seconds_to_value_unit(self.job.interval_seconds)
                schedule_info = f"كل {val} {unit}"
        else:
            # نظام الفاصل الزمني
            val, unit = seconds_to_value_unit(self.job.interval_seconds)
            schedule_info = f"كل {val} {unit}"

        # عرض اسم التطبيق إذا كان موجوداً
        app_name = getattr(self.job, 'app_name', '')
        if app_name:
            info_text = f"{self.job.page_name} | {app_name} | ID: {self.job.page_id} - مجلد: {self.job.folder} - {schedule_info}"
        else:
            info_text = f"{self.job.page_name} | ID: {self.job.page_id} - مجلد: {self.job.folder} - {schedule_info}"

        # حساب العرض المتاح لنص المعلومات (العرض الكلي - عرض الحالة والعدّاد - الهوامش)
        available_width = self.width() - self.COUNTDOWN_WIDTH - self.STATUS_WIDTH - self.MARGINS_WIDTH
        if available_width > 100:
            elided_text = self._elide_text(info_text, available_width)
            self.info_label.setText(elided_text)
            # عرض النص الكامل كتلميح فقط إذا تم اقتطاع النص
            if elided_text != info_text:
                self.info_label.setToolTip(info_text)
            else:
                self.info_label.setToolTip('')
        else:
            self.info_label.setText(info_text)
            self.info_label.setToolTip('')

        # تحديث حالة الوظيفة
        if not self.job.enabled:
            self.status_label.setText('معطّل')
            self.status_label.setStyleSheet(f'color: {COUNTDOWN_COLOR_GRAY}; font-weight: bold;')
            self.countdown_label.setText('--:--:--')
        elif self.job.is_scheduled:
            if outside_working_hours:
                # خارج ساعات العمل - عرض الوقت المتبقي لبداية ساعات العمل (Requirement 1)
                self.status_label.setText('خارج ساعات العمل')
                self.status_label.setStyleSheet(f'color: {COUNTDOWN_COLOR_YELLOW}; font-weight: bold;')
                self.countdown_label.setText(f'⏳ تبدأ بعد: {format_remaining_time(time_to_working_hours)}')
            else:
                self.status_label.setText('مجدول')
                self.status_label.setStyleSheet(f'color: {COUNTDOWN_COLOR_GREEN}; font-weight: bold;')
                if remaining_seconds is not None:
                    self.countdown_label.setText(format_remaining_time(remaining_seconds))
                else:
                    self.countdown_label.setText('--:--:--')
        else:
            # مفعّل لكن غير مجدول
            self.status_label.setText('مفعّل')
            self.status_label.setStyleSheet(f'color: {COUNTDOWN_COLOR_YELLOW}; font-weight: bold;')
            self.countdown_label.setText('غير مجدول')

        self.update_countdown_style(remaining_seconds, outside_working_hours)

    def update_countdown_style(self, remaining_seconds=None, outside_working_hours=False):
        """تحديث لون العدّاد بناءً على الوقت المتبقي مع خلفية مميزة (Requirement 1)."""
        # ستايل أساسي للعدّاد مع خلفية داكنة وزوايا مستديرة
        base_style = 'font-weight: bold; padding: 4px 8px; border-radius: 4px;'

        if not self.job.enabled:
            # رمادي داكن للوظائف المعطّلة
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_GRAY}; background-color: #1a1d23; {base_style}'
            )
        elif outside_working_hours:
            # برتقالي لخارج ساعات العمل (Requirement 1)
            self.countdown_label.setStyleSheet(
                f'color: #FF9800; background-color: #2a1f10; {base_style}'
            )
        elif not self.job.is_scheduled:
            # أصفر للوظائف المفعّلة لكن غير المجدولة
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_YELLOW}; background-color: #2a2510; {base_style}'
            )
        elif remaining_seconds is None:
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_GRAY}; background-color: #1a1d23; {base_style}'
            )
        elif remaining_seconds >= 300:  # أخضر: ≥5 دقائق
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_GREEN}; background-color: #0d2818; {base_style}'
            )
        elif remaining_seconds >= 60:  # أصفر: 1-5 دقائق
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_YELLOW}; background-color: #2a2510; {base_style}'
            )
        else:  # أحمر: <1 دقيقة
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_RED}; background-color: #2a1010; {base_style}'
            )

def resumable_upload(page_job: PageJob, video_path, token, ui_signals: UiSignals,
                     final_title="", final_description=""):
    """
    رفع فيديو بشكل مجزأ إلى فيسبوك.
    Upload video to Facebook in chunks (resumable upload).

    Args:
        page_job: وظيفة الصفحة - Page job
        video_path: مسار الفيديو - Video path
        token: توكن الوصول - Access token
        ui_signals: إشارات الواجهة - UI signals
        final_title: عنوان الفيديو - Video title
        final_description: وصف الفيديو - Video description

    Returns:
        tuple: (status_code, response_body)
    """
    chunk_size = page_job.chunk_size if page_job.chunk_size > 0 else CHUNK_SIZE_DEFAULT

    return _upload_service.resumable_upload(
        page_id=page_job.page_id,
        video_path=video_path,
        token=token,
        ui_signals=ui_signals,
        final_title=final_title,
        final_description=final_description,
        chunk_size=chunk_size,
        upload_timeout_start=UPLOAD_TIMEOUT_START,
        upload_timeout_transfer=UPLOAD_TIMEOUT_TRANSFER,
        upload_timeout_finish=UPLOAD_TIMEOUT_FINISH,
        page_job=page_job
    )


def apply_watermark_to_video(video_path: str, job: PageJob, log_fn) -> str:
    """
    تطبيق العلامة المائية على الفيديو إذا كانت مفعلة بشكل آمن.
    Apply watermark to video if enabled.

    المعاملات:
        video_path: مسار الفيديو الأصلي - Original video path
        job: وظيفة الصفحة التي تحتوي على إعدادات العلامة المائية - Page job with watermark settings
        log_fn: دالة التسجيل - Logging function

    العائد:
        مسار الفيديو النهائي (الأصلي أو المعدّل)
        Final video path (original or modified)
    """
    # التحقق من تفعيل العلامة المائية
    if not getattr(job, 'watermark_enabled', False):
        return video_path

    watermark_path = getattr(job, 'watermark_path', '')
    if not watermark_path:
        return video_path

    # الحصول على إعدادات العلامة المائية
    position = getattr(job, 'watermark_position', 'bottom_right')
    opacity = getattr(job, 'watermark_opacity', 0.8)
    scale = getattr(job, 'watermark_scale', 0.15)
    watermark_x = getattr(job, 'watermark_x', None)
    watermark_y = getattr(job, 'watermark_y', None)

    return _upload_service.apply_watermark_to_video(
        video_path=video_path,
        watermark_path=watermark_path,
        position=position,
        opacity=opacity,
        scale=scale,
        watermark_x=watermark_x,
        watermark_y=watermark_y,
        log_fn=log_fn,
        run_subprocess_fn=run_subprocess,
        notification_system=NotificationSystem,
        page_name=job.page_name,
        watermark_ffmpeg_timeout=WATERMARK_FFMPEG_TIMEOUT,
        watermark_min_output_ratio=WATERMARK_MIN_OUTPUT_RATIO,
        watermark_file_close_delay=WATERMARK_FILE_CLOSE_DELAY
    )


def cleanup_temp_watermark_file(video_path: str, original_path: str, log_fn=None):
    """
    حذف ملف الفيديو المؤقت بعد الرفع إذا كان مختلفاً عن الأصلي بشكل آمن.
    Delete temporary video file after upload if different from original.

    المعاملات:
        video_path: مسار الفيديو المستخدم (قد يكون مؤقتاً) - Video path used (may be temporary)
        original_path: مسار الفيديو الأصلي - Original video path
        log_fn: دالة التسجيل - Logging function
    """
    _upload_service.cleanup_temp_watermark_file(
        video_path=video_path,
        original_path=original_path,
        log_fn=log_fn,
        watermark_cleanup_delay=WATERMARK_CLEANUP_DELAY
    )


def upload_video_once(page_job: PageJob, video_path, token, ui_signals: UiSignals,
                      title_tmpl, desc_tmpl, log_fn):
    """
    رفع فيديو واحد إلى فيسبوك مع دعم العلامة المائية.

    هذه الدالة محمية من الأخطاء لمنع crash البرنامج.
    """
    endpoint = f'https://graph-video.facebook.com/v17.0/{page_job.page_id}/videos'
    folder = Path(page_job.folder)

    # متغيرات للتتبع
    original_video_path = video_path
    video_path_to_upload = video_path

    try:
        # الحصول على قائمة الملفات
        try:
            files_all = sorted([p for p in folder.iterdir()
                                if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS])
        except Exception:
            files_all = [Path(video_path)]

        filename = os.path.basename(video_path)
        idx = files_all.index(Path(video_path)) if Path(video_path) in files_all else 0

        # تنظيف اسم الملف تلقائياً (داخلياً)
        original_name = os.path.splitext(filename)[0]
        display_filename = clean_filename_for_title(filename)
        # Problem 1 fix: إزالة رسالة السجل الزائدة
        # if display_filename != original_name:
        #     log_fn(f'🧹 تم تنظيف العنوان: "{original_name}" -> "{display_filename}"')

        title = display_filename if page_job.use_filename_as_title else apply_template(title_tmpl, page_job, display_filename, idx + 1, len(files_all))
        description = apply_template(desc_tmpl, page_job, display_filename, idx + 1, len(files_all))
        # Problem 1 fix: إزالة رسالة السجل الزائدة
        # log_fn(f'رفع بسيط: {filename} -> {page_job.page_name} عنوان="{title}"')

        # تطبيق العلامة المائية إذا كانت مفعلة
        try:
            video_path_to_upload = apply_watermark_to_video(video_path, page_job, log_fn)
        except Exception as wm_error:
            log_fn(f'⚠️ خطأ في العلامة المائية: {wm_error}')
            video_path_to_upload = video_path  # استخدام الفيديو الأصلي

        # محاولة الرفع البسيط
        try:
            with open(video_path_to_upload, 'rb') as f:
                data = {
                    'access_token': token,
                    'title': title,
                    'description': description,
                    'published': 'true'
                }
                r = requests.post(endpoint, data=data, files={'source': (filename, f, 'video/mp4')}, timeout=300)
        except Exception as e:
            log_fn(f'خطأ رفع بسيط: {e}')
            try:
                size = os.path.getsize(original_video_path)
            except Exception:
                size = 0

            if size >= RESUMABLE_THRESHOLD_BYTES:
                log_fn('تحويل للمجزأ بسبب الحجم.')
                # استخدام الفيديو مع العلامة المائية إذا كان موجوداً
                try:
                    result = resumable_upload(page_job, video_path_to_upload, token, ui_signals, title, description)
                    return result
                except Exception as res_error:
                    log_fn(f'❌ خطأ في الرفع المجزأ: {res_error}')
                    return None, {'error': 'resumable_exception', 'detail': str(res_error)}
            return None, {'error': 'simple_exception', 'detail': str(e)}

        status = getattr(r, 'status_code', None)
        try:
            body = r.json()
        except Exception:
            body = r.text

        # التحقق من الحاجة للرفع المجزأ
        try:
            file_size = os.path.getsize(video_path_to_upload) if os.path.exists(video_path_to_upload) else 0
        except Exception:
            file_size = 0

        if status == 413 or (isinstance(body, dict) and body.get('error', {}).get('code') == 413) \
           or file_size >= RESUMABLE_THRESHOLD_BYTES:
            log_fn('تحويل للمجزأ (413 أو الحجم).')
            try:
                result = resumable_upload(page_job, video_path_to_upload, token, ui_signals, title, description)
                return result
            except Exception as res_error:
                log_fn(f'❌ خطأ في الرفع المجزأ: {res_error}')
                return None, {'error': 'resumable_exception', 'detail': str(res_error)}

        try:
            ui_signals.progress_signal.emit(100, 'تم الرفع البسيط 100%')
        except Exception:
            pass  # تجاهل أخطاء إرسال الإشارة

        log_fn(f'نتيجة الرفع البسيط ({status}): {body}')
        return status, body

    except Exception as e:
        # التقاط أي خطأ غير متوقع
        log_fn(f'❌ خطأ غير متوقع في عملية الرفع: {e}')
        try:
            from controllers.story_controller import log_error_to_file
            log_error_to_file(e, f'Unexpected error in upload_video_once: {video_path}')
        except Exception:
            pass
        return None, {'error': 'unexpected_exception', 'detail': str(e)}

    finally:
        # تنظيف الملف المؤقت بشكل آمن (دائماً يتم تنفيذه)
        try:
            cleanup_temp_watermark_file(video_path_to_upload, original_video_path, log_fn)
        except Exception as cleanup_error:
            # تجاهل أي خطأ في التنظيف لمنع crash
            try:
                log_fn(f'⚠️ خطأ في تنظيف الملف المؤقت: {cleanup_error}')
            except Exception:
                pass

class SchedulerThread(threading.Thread):
    def __init__(self, jobs_map, token_getter, ui_signals: UiSignals, stop_event, max_workers=3,
                 auto_move_getter=None, validate_videos_getter=None, internet_check_getter=None):
        super().__init__(daemon=True)
        self.jobs_map = jobs_map
        self.token_getter = token_getter
        self.ui = ui_signals
        self.stop_event = stop_event
        self.max_workers = max_workers
        # دالة للحصول على حالة نقل الفيديوهات تلقائياً
        self.auto_move_getter = auto_move_getter or (lambda: False)
        # دالة للحصول على حالة التحقق من الفيديو
        self.validate_videos_getter = validate_videos_getter or (lambda: False)
        # دالة للحصول على حالة فحص الإنترنت
        self.internet_check_getter = internet_check_getter or (lambda: True)

    def log(self, text):
        self.ui.log_signal.emit(text)

    def _handle_rate_limit(self, job) -> bool:
        """
        معالجة خطأ Rate Limit - تأجيل النشر والمحاولة مرة أخرى بدلاً من الإيقاف.

        العائد: True لتخطي هذه المحاولة (سيتم المحاولة لاحقاً)
        """
        # تأخير عشوائي بين 30-60 دقيقة
        delay_minutes = random.randint(30, 60)
        delay_seconds = delay_minutes * 60

        NotificationSystem.notify(self.log, NotificationSystem.WARNING,
            f'⏳ تم الوصول لحد الطلبات (Rate Limit) - سيتم المحاولة تلقائياً بعد {delay_minutes} دقيقة', job.page_name)

        # تأجيل وقت النشر القادم بدلاً من الإيقاف
        job.next_run_timestamp = time.time() + delay_seconds

        # إرسال إشعار Telegram إذا كان مفعلاً
        try:
            send_telegram_error('تم الوصول لحد الطلبات',
                f'سيتم تأجيل النشر لمدة {delay_minutes} دقيقة والمحاولة مرة أخرى تلقائياً', job.page_name)
        except Exception:
            pass

        return True

    def run(self):
        self.log('تم تشغيل المجدول')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not self.stop_event.is_set():
                now = time.time()

                for job in list(self.jobs_map.values()):
                    if self.stop_event.is_set():
                        break
                    # تخطّي الوظائف غير المجدولة أو المعطّلة
                    if not job.enabled or not job.is_scheduled:
                        continue

                    # التحقق من وصول الوقت باستخدام job.next_run_timestamp
                    if now >= job.next_run_timestamp:
                        executor.submit(self._upload_wrapper, job)
                        # ضبط الوقت التالي بعد الرفع
                        job.reset_next_run_timestamp()
                time.sleep(1)
        self.log('توقف المجدول.')

    def _upload_wrapper(self, job: PageJob):
        """غلاف آمن لعملية الرفع مع معالجة شاملة للأخطاء."""
        if not job.lock.acquire(blocking=False):
            self.log(f'تخطي: رفع سابق قيد التنفيذ {job.page_name}')
            return
        try:
            self._process_job(job)
        except Exception as e:
            # التقاط أي استثناء غير متوقع لمنع crash البرنامج
            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                f'خطأ غير متوقع في عملية الرفع: {str(e)[:100]}', job.page_name)
            try:
                # تسجيل الخطأ في ملف السجلات
                from controllers.story_controller import log_error_to_file
                log_error_to_file(e, f'Unexpected error in video upload for job: {job.page_name}')
            except Exception:
                pass  # تجاهل أخطاء التسجيل
        finally:
            try:
                job.lock.release()
            except Exception:
                pass  # تجاهل أي خطأ في تحرير القفل

    def _process_job(self, job: PageJob):
        # فحص الاتصال بالإنترنت قبل الرفع (Internet Safety Check)
        if self.internet_check_getter():
            if not check_internet_connection():
                NotificationSystem.notify(self.log, NotificationSystem.NETWORK,
                    'فشل الاتصال بالإنترنت - الدخول في وضع الغفوة', job.page_name)
                # الانتظار حتى يعود الاتصال
                attempts = 0
                while not check_internet_connection() and attempts < INTERNET_CHECK_MAX_ATTEMPTS:
                    if self.stop_event.is_set():
                        self.log('تم إيقاف المجدول أثناء انتظار الاتصال')
                        return
                    if job.check_and_reset_cancel():
                        self.log(f'تم إلغاء الوظيفة أثناء انتظار الاتصال: {job.page_name}')
                        return
                    attempts += 1
                    self.log(f'📶 المحاولة {attempts}/{INTERNET_CHECK_MAX_ATTEMPTS} - الانتظار {INTERNET_CHECK_INTERVAL} ثانية...')
                    time.sleep(INTERNET_CHECK_INTERVAL)

                if check_internet_connection():
                    NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                        'عاد الاتصال بالإنترنت - استئناف الرفع', job.page_name)
                else:
                    NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                        'انتهت المحاولات - تخطي الرفع', job.page_name)
                    return

        folder = Path(job.folder)
        if not folder.exists():
            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                f'المجلد غير موجود: {folder}', job.page_name)
            return

        # الحصول على الملفات وترتيبها حسب الخيار المحدد
        raw_files = [p for p in folder.iterdir()
                     if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]

        # تطبيق ترتيب الملفات
        files = sort_video_files(raw_files, job.sort_by)

        if not files:
            NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                f'لا توجد فيديوهات في المجلد ({job.folder}) - تم إيقاف الرفع مؤقتاً', job.page_name)
            return
        idx = job.next_index % len(files)
        video_path = str(files[idx])

        # التحقق من صحة الفيديو قبل الرفع
        if self.validate_videos_getter():
            validation = validate_video(video_path, self.log)
            if not validation['valid']:
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    f'تخطي الفيديو (غير صالح): {validation.get("error", "خطأ غير معروف")}', job.page_name)
                # تسجيل الفشل في قاعدة البيانات
                log_upload(job.page_id, job.page_name, video_path, os.path.basename(video_path),
                          'video', status='failed', error_message=validation.get('error'))
                job.next_index = (job.next_index + 1) % len(files)
                return

        job.next_index = (job.next_index + 1) % len(files)
        token = job.page_access_token or self.token_getter()
        if not token:
            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                'التوكن غير صالح أو منتهي الصلاحية', job.page_name)
            return

        NotificationSystem.notify(self.log, NotificationSystem.UPLOAD,
            f'بدء رفع الفيديو: {os.path.basename(video_path)}', job.page_name)

        status, body = upload_video_once(job, video_path, token, self.ui,
                                         job.title_template, job.description_template, self.log)

        # التحقق من نجاح الرفع ونقل الفيديو إلى مجلد Uploaded
        upload_success = is_upload_successful(status, body)

        # التحقق من Rate Limit
        if is_rate_limit_error(body):
            self._handle_rate_limit(job)
            return  # الخروج فوراً بدون متابعة

        # تسجيل الرفع في قاعدة البيانات
        video_id = body.get('id') if isinstance(body, dict) else None
        video_url = f'https://www.facebook.com/{video_id}' if video_id else None
        log_upload(
            job.page_id, job.page_name, video_path, os.path.basename(video_path),
            'video', video_id=video_id, video_url=video_url,
            status='success' if upload_success else 'failed',
            error_message=str(body.get('error', '')) if isinstance(body, dict) and not upload_success else None
        )

        if upload_success:
            NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                f'تم رفع الفيديو بنجاح: {os.path.basename(video_path)}', job.page_name)
            if self.auto_move_getter():
                move_video_to_uploaded_folder(video_path, self.log)
        else:
            error_msg = str(body.get('error', {}).get('message', '')) if isinstance(body, dict) else str(body)
            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                f'فشل رفع الفيديو: {error_msg[:100]}', job.page_name)

        if status in (400, 403):
            if isinstance(body, dict):
                err = body.get('error', {})
                msg = err.get('message', '')
                code = err.get('code', '')
                if msg and ('permission' in msg.lower() or code == 100):
                    NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                        'صلاحيات غير كافية للنشر', job.page_name)


class StorySchedulerThread(threading.Thread):
    """
    خيط مجدول لنشر الستوري.
    يعالج وظائف الستوري ويرفعها إلى فيسبوك.
    """

    def __init__(self, story_jobs_map, token_getter, ui_signals: UiSignals, stop_event,
                 max_workers=3, auto_move_getter=None, internet_check_getter=None):
        super().__init__(daemon=True)
        self.story_jobs_map = story_jobs_map
        self.token_getter = token_getter
        self.ui = ui_signals
        self.stop_event = stop_event
        self.max_workers = max_workers
        # دالة للحصول على حالة نقل الملفات تلقائياً
        self.auto_move_getter = auto_move_getter or (lambda: False)
        # دالة للحصول على حالة فحص الإنترنت
        self.internet_check_getter = internet_check_getter or (lambda: True)

    def log(self, text):
        self.ui.log_signal.emit(text)

    def _handle_rate_limit(self, job) -> bool:
        """
        معالجة خطأ Rate Limit - تأجيل النشر والمحاولة مرة أخرى بدلاً من الإيقاف.

        العائد: True لتخطي هذه المحاولة (سيتم المحاولة لاحقاً)
        """
        # تأخير عشوائي بين 30-60 دقيقة
        delay_minutes = random.randint(30, 60)
        delay_seconds = delay_minutes * 60

        NotificationSystem.notify(self.log, NotificationSystem.WARNING,
            f'⏳ تم الوصول لحد الطلبات (Rate Limit) - سيتم المحاولة تلقائياً بعد {delay_minutes} دقيقة', job.page_name)

        # تأجيل وقت النشر القادم بدلاً من الإيقاف
        job.next_run_timestamp = time.time() + delay_seconds

        # إرسال إشعار Telegram إذا كان مفعلاً
        try:
            send_telegram_error('تم الوصول لحد الطلبات',
                f'سيتم تأجيل النشر لمدة {delay_minutes} دقيقة والمحاولة مرة أخرى تلقائياً', job.page_name)
        except Exception:
            pass

        return True

    def run(self):
        self.log('تم تشغيل مجدول الستوري')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not self.stop_event.is_set():
                now = time.time()

                for job in list(self.story_jobs_map.values()):
                    if self.stop_event.is_set():
                        break
                    # تخطّي الوظائف غير المجدولة أو المعطّلة
                    if not job.enabled or not job.is_scheduled:
                        continue

                    # التحقق من وصول الوقت باستخدام job.next_run_timestamp
                    if now >= job.next_run_timestamp:
                        executor.submit(self._upload_wrapper, job)
                        # ضبط الوقت التالي بعد الرفع
                        job.reset_next_run_timestamp()
                time.sleep(1)
        self.log('توقف مجدول الستوري.')

    def _upload_wrapper(self, job: StoryJob):
        if not job.lock.acquire(blocking=False):
            self.log(f'تخطي: رفع ستوري سابق قيد التنفيذ {job.page_name}')
            return
        try:
            self._process_story_job(job)
        finally:
            job.lock.release()

    def _process_story_job(self, job: StoryJob):
        """معالجة وظيفة ستوري واحدة مع حماية شاملة من الأخطاء."""
        # Import from storyTasks
        from controllers.story_controller import (
            get_story_files, get_next_story_batch, upload_story,
            is_story_upload_successful, log_error_to_file
        )

        try:
            # فحص الاتصال بالإنترنت قبل الرفع
            if self.internet_check_getter():
                if not check_internet_connection():
                    NotificationSystem.notify(self.log, NotificationSystem.NETWORK,
                        'فشل الاتصال بالإنترنت - الدخول في وضع الغفوة', job.page_name)
                    # الانتظار حتى يعود الاتصال
                    attempts = 0
                    while not check_internet_connection() and attempts < INTERNET_CHECK_MAX_ATTEMPTS:
                        if self.stop_event.is_set():
                            self.log('تم إيقاف مجدول الستوري أثناء انتظار الاتصال')
                            return
                        if job.check_and_reset_cancel():
                            self.log(f'تم إلغاء وظيفة الستوري أثناء انتظار الاتصال: {job.page_name}')
                            return
                        attempts += 1
                        self.log(f'📶 المحاولة {attempts}/{INTERNET_CHECK_MAX_ATTEMPTS} - الانتظار {INTERNET_CHECK_INTERVAL} ثانية...')
                        time.sleep(INTERNET_CHECK_INTERVAL)

                    if check_internet_connection():
                        NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                            'عاد الاتصال بالإنترنت - استئناف الرفع', job.page_name)
                    else:
                        NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                            'انتهت المحاولات - تخطي الرفع', job.page_name)
                        return

            folder = Path(job.folder)
            if not folder.exists():
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    f'المجلد غير موجود: {folder}', job.page_name)
                return

            # الحصول على الملفات وترتيبها حسب الخيار المحدد
            try:
                files = get_story_files(str(folder), job.sort_by)
            except Exception as e:
                self.log(f'❌ فشل قراءة ملفات الستوري: {e}')
                log_error_to_file(e, f'get_story_files error for {folder}')
                return

            if not files:
                NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                    f'انتهت جميع الفيديوهات في المجلد ({job.folder})', job.page_name)
                return

            # الحصول على الدفعة التالية
            try:
                batch = get_next_story_batch(job, files)
            except Exception as e:
                self.log(f'❌ فشل تحديد الدفعة: {e}')
                log_error_to_file(e, f'get_next_story_batch error for {job.page_name}')
                return

            if not batch:
                NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                    'لا توجد ملفات في الدفعة للنشر', job.page_name)
                return

            token = job.page_access_token or self.token_getter()
            if not token:
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    'التوكن غير صالح أو منتهي الصلاحية', job.page_name)
                return

            # التحقق من حدود API
            try:
                tracker = get_api_tracker(job.hourly_limit, job.daily_limit)
                warning_system = get_api_warning_system(self.log)

                can_continue, warning_msg = warning_system.check_and_warn()
                if not can_continue:
                    NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                        warning_msg, job.page_name)
                    return
            except Exception as e:
                # استمر حتى لو فشل نظام التتبع
                self.log(f'⚠️ تحذير: فشل نظام تتبع API: {str(e)}')
                log_error_to_file(e, 'API tracker failed in _process_story_job')

            NotificationSystem.notify(self.log, NotificationSystem.UPLOAD,
                f'بدء نشر {len(batch)} ستوري', job.page_name)

            successful_count = 0
            failed_count = 0

            # استخدام Session لتحسين الأداء مع معالجة استثناءات
            session = None
            try:
                session = requests.Session()
                for file_path in batch:
                    try:
                        if self.stop_event.is_set():
                            self.log('تم إيقاف مجدول الستوري أثناء النشر')
                            break

                        if job.check_and_reset_cancel():
                            self.log(f'تم إلغاء وظيفة الستوري: {job.page_name}')
                            break

                        self.log(f'📱 رفع ستوري: {file_path.name} -> {job.page_name} ({mask_token(token)})')

                        status, body = upload_story(job.page_id, str(file_path), token, self.log, session)

                        # تسجيل طلب API
                        try:
                            tracker.record_call(API_CALLS_PER_STORY)
                        except Exception:
                            pass

                        # تسجيل النتيجة
                        upload_success = is_story_upload_successful(status, body)

                        # التحقق من Rate Limit
                        if is_rate_limit_error(body):
                            self._handle_rate_limit(job)
                            break  # الخروج من حلقة الستوري

                        # تسجيل الرفع في قاعدة البيانات
                        story_id = body.get('id') if isinstance(body, dict) else None
                        log_upload(
                            job.page_id, job.page_name, str(file_path), file_path.name,
                            'story', video_id=story_id, video_url=None,
                            status='success' if upload_success else 'failed',
                            error_message=str(body.get('error', '')) if isinstance(body, dict) and not upload_success else None
                        )

                        if upload_success:
                            successful_count += 1
                            NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                                f'تم رفع الستوري بنجاح: {file_path.name}', job.page_name)
                            # نقل الملف إذا مفعّل
                            if self.auto_move_getter():
                                try:
                                    move_video_to_uploaded_folder(str(file_path), self.log)
                                except Exception as move_err:
                                    self.log(f'⚠️ فشل نقل الملف: {move_err}')
                        else:
                            failed_count += 1
                            error_msg = str(body.get('error', {}).get('message', '')) if isinstance(body, dict) else str(body)
                            NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                                f'فشل رفع الستوري: {error_msg[:50]}', job.page_name)

                        # تأخير بين كل ستوري لتجنب rate limiting (حماية من الحظر) - Requirement 4
                        if job.anti_ban_enabled and len(batch) > 1:
                            # استخدام التأخير العشوائي فقط
                            delay = random.randint(job.random_delay_min, job.random_delay_max)
                            NotificationSystem.notify(self.log, NotificationSystem.INFO,
                                f'⏳ استراحة حماية لمدة {delay} ثانية', job.page_name)
                            time.sleep(delay)

                    except requests.exceptions.Timeout as e:
                        failed_count += 1
                        self.log(f'⏱️ انتهت مهلة رفع الستوري ({file_path.name})')
                        log_error_to_file(e, f'Story upload timeout: {file_path}')

                    except requests.exceptions.ConnectionError as e:
                        failed_count += 1
                        self.log(f'🔌 فشل الاتصال أثناء رفع الستوري ({file_path.name})')
                        log_error_to_file(e, f'Story upload connection error: {file_path}')

                    except Exception as e:
                        failed_count += 1
                        self.log(f'❌ خطأ في رفع الستوري ({file_path.name}): {e}')
                        log_error_to_file(e, f'Story upload error: {file_path}')

            finally:
                # إغلاق Session بشكل آمن
                if session:
                    try:
                        session.close()
                    except Exception:
                        pass
                # تنظيف الذاكرة بعد انتهاء الدفعة بالكامل
                gc.collect()

            # تحديث next_index
            job.next_index = (job.next_index + len(batch)) % len(files)

            self.log(f'📱 انتهى نشر الستوري: {successful_count} نجح، {failed_count} فشل')

        except Exception as e:
            self.log(f'❌ خطأ غير متوقع في معالجة وظيفة الستوري: {e}')
            log_error_to_file(e, f'Process story job error: {job.page_name}')


class ReelsSchedulerThread(threading.Thread):
    """
    خيط مجدول لنشر الريلز.
    يعالج وظائف الريلز ويرفعها إلى فيسبوك.
    Reels scheduler thread - handles reels jobs and uploads them to Facebook.
    """

    def __init__(self, reels_jobs_map, token_getter, ui_signals: UiSignals, stop_event,
                 max_workers=3, auto_move_getter=None, internet_check_getter=None):
        super().__init__(daemon=True)
        self.reels_jobs_map = reels_jobs_map
        self.token_getter = token_getter
        self.ui = ui_signals
        self.stop_event = stop_event
        self.max_workers = max_workers
        # دالة للحصول على حالة نقل الملفات تلقائياً
        self.auto_move_getter = auto_move_getter or (lambda: False)
        # دالة للحصول على حالة فحص الإنترنت
        self.internet_check_getter = internet_check_getter or (lambda: True)

    def log(self, text):
        self.ui.log_signal.emit(text)

    def _handle_rate_limit(self, job) -> bool:
        """
        معالجة خطأ Rate Limit - تأجيل النشر والمحاولة مرة أخرى بدلاً من الإيقاف.
        
        العائد: True لتخطي هذه المحاولة (سيتم المحاولة لاحقاً)
        """
        # تأخير عشوائي بين 30-60 دقيقة
        delay_minutes = random.randint(30, 60)
        delay_seconds = delay_minutes * 60

        NotificationSystem.notify(self.log, NotificationSystem.WARNING,
            f'⏳ تم الوصول لحد الطلبات (Rate Limit) - سيتم المحاولة تلقائياً بعد {delay_minutes} دقيقة', job.page_name)

        # تأجيل وقت النشر القادم بدلاً من الإيقاف
        job.next_run_timestamp = time.time() + delay_seconds

        # إرسال إشعار Telegram إذا كان مفعلاً
        try:
            send_telegram_error('تم الوصول لحد الطلبات',
                f'سيتم تأجيل النشر لمدة {delay_minutes} دقيقة والمحاولة مرة أخرى تلقائياً', job.page_name)
        except Exception:
            pass

        return True

    def run(self):
        self.log('تم تشغيل مجدول الريلز')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while not self.stop_event.is_set():
                now = time.time()

                for job in list(self.reels_jobs_map.values()):
                    if self.stop_event.is_set():
                        break
                    # تخطّي الوظائف غير المجدولة أو المعطّلة
                    if not job.enabled or not job.is_scheduled:
                        continue

                    # التحقق من وصول الوقت باستخدام job.next_run_timestamp
                    if now >= job.next_run_timestamp:
                        executor.submit(self._upload_wrapper, job)
                        # ضبط الوقت التالي بعد الرفع
                        job.reset_next_run_timestamp()
                time.sleep(1)
        self.log('توقف مجدول الريلز.')

    def _upload_wrapper(self, job: ReelsJob):
        if not job.lock.acquire(blocking=False):
            self.log(f'تخطي: رفع ريلز سابق قيد التنفيذ {job.page_name}')
            return
        try:
            self._process_reels_job(job)
        finally:
            job.lock.release()

    def _process_reels_job(self, job: ReelsJob):
        """معالجة وظيفة ريلز واحدة مع حماية شاملة من الأخطاء."""
        # Import from reels_controller
        from controllers.reels_controller import (
            get_reels_files, upload_reels_with_retry, is_reels_upload_successful,
            log_error_to_file, check_reels_duration
        )

        try:
            # فحص الاتصال بالإنترنت قبل الرفع
            if self.internet_check_getter():
                if not check_internet_connection():
                    NotificationSystem.notify(self.log, NotificationSystem.NETWORK,
                        'فشل الاتصال بالإنترنت - الدخول في وضع الغفوة', job.page_name)
                    # الانتظار حتى يعود الاتصال
                    attempts = 0
                    while not check_internet_connection() and attempts < INTERNET_CHECK_MAX_ATTEMPTS:
                        if self.stop_event.is_set():
                            self.log('تم إيقاف مجدول الريلز أثناء انتظار الاتصال')
                            return
                        if job.check_and_reset_cancel():
                            self.log(f'تم إلغاء وظيفة الريلز أثناء انتظار الاتصال: {job.page_name}')
                            return
                        attempts += 1
                        self.log(f'📶 المحاولة {attempts}/{INTERNET_CHECK_MAX_ATTEMPTS} - الانتظار {INTERNET_CHECK_INTERVAL} ثانية...')
                        time.sleep(INTERNET_CHECK_INTERVAL)

                    if check_internet_connection():
                        NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                            'عاد الاتصال بالإنترنت - استئناف الرفع', job.page_name)
                    else:
                        NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                            'انتهت المحاولات - تخطي الرفع', job.page_name)
                        return

            folder = Path(job.folder)
            if not folder.exists():
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    f'المجلد غير موجود: {folder}', job.page_name)
                return

            # الحصول على الملفات وترتيبها حسب الخيار المحدد
            try:
                files = get_reels_files(str(folder), job.sort_by)
            except Exception as e:
                self.log(f'❌ فشل قراءة ملفات الريلز: {e}')
                log_error_to_file(e, f'get_reels_files error for {folder}')
                return

            if not files:
                NotificationSystem.notify(self.log, NotificationSystem.WARNING,
                    f'لا توجد ملفات ريلز في المجلد ({job.folder})', job.page_name)
                return

            # الحصول على الفيديو التالي
            idx = job.next_index % len(files)
            video_path = str(files[idx])

            # فحص مدة الفيديو قبل البدء بالرفع
            is_valid_duration, duration, error_msg = check_reels_duration(video_path)
            if not is_valid_duration:
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    f'⚠️ تم رفض الفيديو: {error_msg}', job.page_name)
                # تخطي هذا الفيديو والانتقال للتالي
                job.next_index = (job.next_index + 1) % len(files)
                return

            token = job.page_access_token or self.token_getter()
            if not token:
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    'التوكن غير صالح أو منتهي الصلاحية', job.page_name)
                return

            NotificationSystem.notify(self.log, NotificationSystem.UPLOAD,
                f'بدء رفع ريلز: {Path(video_path).name}', job.page_name)
            if duration > 0:
                self.log(f'📊 مدة الفيديو: {duration:.1f} ثانية')

            # إعداد العنوان والوصف
            title = apply_title_placeholders(job.title_template, Path(video_path).name) if job.title_template else ''
            description = apply_title_placeholders(job.description_template, Path(video_path).name) if job.description_template else ''

            # رفع الريلز
            status, body = upload_reels_with_retry(
                page_id=job.page_id,
                video_path=video_path,
                token=token,
                description=description,
                title=title,
                log_fn=self.log,
                progress_callback=lambda p: self.ui.progress_signal.emit(int(p), f'رفع الريلز {int(p)}%'),
                stop_event=self.stop_event
            )

            # التحقق من النجاح
            upload_success = is_reels_upload_successful(status, body)

            # التحقق من Rate Limit
            if is_rate_limit_error(body):
                self._handle_rate_limit(job)
                return

            # تسجيل الرفع في قاعدة البيانات
            video_id = body.get('video_id') or body.get('id') if isinstance(body, dict) else None
            log_upload(
                job.page_id, job.page_name, video_path, Path(video_path).name,
                'reels', video_id=video_id, video_url=None,
                status='success' if upload_success else 'failed',
                error_message=str(body.get('error', '')) if isinstance(body, dict) and not upload_success else None
            )

            if upload_success:
                NotificationSystem.notify(self.log, NotificationSystem.SUCCESS,
                    f'✅ تم رفع الريلز بنجاح: {Path(video_path).name}', job.page_name)
                # تحديث next_index للفيديو التالي
                job.next_index = (job.next_index + 1) % len(files)
                # نقل الملف إذا مفعّل
                if self.auto_move_getter():
                    try:
                        move_video_to_uploaded_folder(video_path, self.log)
                    except Exception as move_err:
                        self.log(f'⚠️ فشل نقل الملف: {move_err}')
            else:
                error_msg = str(body.get('error', {}).get('message', '')) if isinstance(body, dict) else str(body)
                NotificationSystem.notify(self.log, NotificationSystem.ERROR,
                    f'❌ فشل رفع الريلز: {error_msg[:50]}', job.page_name)

        except Exception as e:
            self.log(f'❌ خطأ غير متوقع في معالجة وظيفة الريلز: {e}')
            log_error_to_file(e, f'Process reels job error: {job.page_name}')


# ==================== Hashtag Manager Dialog ====================

# ==================== Hashtag Manager Dialog ====================
# HashtagManagerDialog has been moved to ui/dialogs/hashtag_dialog.py
# This is a wrapper that injects dependencies

class HashtagManagerDialog(HashtagManagerDialogBase):
    """Wrapper for HashtagManagerDialog that injects dependencies."""

    def __init__(self, parent=None):
        super().__init__(
            parent=parent,
            create_icon_button=create_icon_button,
            get_icon=get_icon,
            HAS_QTAWESOME=HAS_QTAWESOME,
            ICONS=ICONS,
            ICON_COLORS=ICON_COLORS,
            get_hashtag_groups=get_hashtag_groups,
            save_hashtag_group=save_hashtag_group,
            delete_hashtag_group=delete_hashtag_group,
            NoScrollComboBox=NoScrollComboBox
        )


# ==================== Schedule Templates Dialog ====================


# ==================== Helper Dialog Classes ====================

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



class TokenManagementDialog(QDialog):
    """
    نافذة إدارة التوكينات - تمكن من إضافة عدة تطبيقات وتحويل التوكينات القصيرة إلى طويلة.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('🔑 إدارة التوكينات')
        self.setMinimumSize(700, 500)
        self._apps = []  # قائمة التطبيقات المحلية
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
        apps = get_all_app_tokens()

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
                save_success, new_id = save_app_token(
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

        save_success, new_id = save_app_token(
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
            delete_app_token(app_entry['db_id'])

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

            save_success, new_id = save_app_token(
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





# ==================== Main Window Class ====================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        # تعيين أيقونة النافذة الرئيسية
        self.setWindowIcon(load_app_icon())

        # تحسين حجم النافذة ليعمل على جميع أحجام الشاشات
        self._setup_responsive_window_size()

        self.jobs_map = {}
        self.story_jobs_map = {}  # مهام الستوري
        self.reels_jobs_map = {}  # مهام الريلز
        self.current_mode = 'video'  # 'video' أو 'story' أو 'reels'
        self.scheduler_thread = None
        self.story_scheduler_thread = None  # مجدول الستوري
        self.reels_scheduler_thread = None  # مجدول الريلز
        # إنشاء stop_event منفصل لكل نوع مهمة لتجنب التداخل
        self.video_scheduler_stop = threading.Event()
        self.story_scheduler_stop = threading.Event()
        self.reels_scheduler_stop = threading.Event()
        # الاحتفاظ بـ scheduler_stop للتوافقية مع الكود القديم
        self.scheduler_stop = self.video_scheduler_stop
        self.ui_signals = UiSignals()
        self.ui_signals.log_signal.connect(self._log_append)
        self.ui_signals.progress_signal.connect(self._update_progress)
        self.ui_signals.clear_progress_signal.connect(self._clear_progress)
        self.ui_signals.job_enabled_changed.connect(self._on_job_schedule_changed)
        # ربط إشارات Telegram والتحديثات
        self.ui_signals.telegram_test_result.connect(self._update_telegram_test_result)
        self.ui_signals.update_check_finished.connect(self._finish_update_check)

        # Cache للصفحات
        self._pages_cache = []
        self._pages_cache_grouped = {}  # النتائج مجمعة حسب التطبيق
        self._pages_cache_time = 0
        self._pages_cache_duration = PAGES_CACHE_DURATION_SECONDS

        # تتبع الـ Threads النشطة لضمان التنظيف الآمن عند الإغلاق
        self._active_token_threads = []  # قائمة بجميع threads جلب التوكن النشطة

        self.theme = "dark"
        self._load_settings_basic()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._update_all_job_countdowns)

        self._build_ui()
        self._setup_system_tray()
        self.apply_theme(self.theme, announce=False)
        self._load_jobs()

        # التحقق من FFmpeg عند بدء التشغيل
        self._check_ffmpeg_on_startup()

        # إزالة رسالة QtAwesome من السجل (Issue #4)
        # تم تعليق الكود لأنها رسالة غير ضرورية
        # if HAS_QTAWESOME:
        #     try:
        #         test_icon = qta.icon('fa5s.check')
        #         if not test_icon.isNull():
        #             self._log_append('✅ مكتبة الأيقونات (QtAwesome) تعمل بنجاح')
        #     except Exception:
        #         pass

    def _setup_responsive_window_size(self):
        """تعيين حجم النافذة بشكل متجاوب مع حجم الشاشة."""
        # الحصول على حجم الشاشة المتاحة
        screen = QApplication.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            screen_width = available_geometry.width()
            screen_height = available_geometry.height()

            # حساب الحجم المناسب (85% من حجم الشاشة كحد أقصى)
            target_width = min(1140, int(screen_width * 0.85))
            target_height = min(840, int(screen_height * 0.85))

            # التأكد من الحد الأدنى للحجم
            target_width = max(800, target_width)
            target_height = max(600, target_height)

            self.resize(target_width, target_height)

            # توسيط النافذة على الشاشة
            x = (screen_width - target_width) // 2 + available_geometry.x()
            y = (screen_height - target_height) // 2 + available_geometry.y()
            self.move(x, y)
        else:
            # قيم افتراضية إذا لم يتم الحصول على معلومات الشاشة
            self.resize(1000, 700)

        # تعيين الحد الأدنى للحجم
        self.setMinimumSize(800, 600)

    def _check_ffmpeg_on_startup(self):
        """التحقق من توفر FFmpeg عند بدء التشغيل."""
        ffmpeg_status = check_ffmpeg_available()
        if not ffmpeg_status['available']:
            self._log_append('⚠️ تحذير: FFmpeg غير مثبت. ميزات العلامة المائية والتحقق من الفيديو لن تعمل.')
            self._log_append('💡 قم بتثبيت FFmpeg من: https://ffmpeg.org/download.html')

    def _load_settings_basic(self):
        settings_file = get_settings_file()
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    st = json.load(f)
                self.theme = st.get('theme', 'dark')
                self._user_token_buffer = simple_decrypt(st.get('user_token_enc', ''))
                self._saved_page_tokens_buffer = {pid: simple_decrypt(enc) for pid, enc in st.get('page_tokens_enc', {}).items()}
                # إعداد نقل الفيديوهات تلقائياً بعد الرفع
                self.auto_move_uploaded = st.get('auto_move_uploaded', True)
                # ساعات العمل
                self.working_hours_enabled = st.get('working_hours_enabled', False)
                self.working_hours_start = st.get('working_hours_start', '09:00')
                self.working_hours_end = st.get('working_hours_end', '23:00')
                # إعدادات العلامة المائية
                self.watermark_enabled = st.get('watermark_enabled', False)
                self.watermark_logo_path = st.get('watermark_logo_path', '')
                self.watermark_position = st.get('watermark_position', 'bottom_right')
                self.watermark_opacity = st.get('watermark_opacity', 0.8)
                # التحقق من صحة الفيديو
                self.validate_videos = st.get('validate_videos', True)
                # فحص الاتصال بالإنترنت قبل الرفع
                self.internet_check_enabled = st.get('internet_check_enabled', True)
                # إعدادات Telegram Bot
                self.telegram_enabled = st.get('telegram_enabled', False)
                self.telegram_bot_token = simple_decrypt(st.get('telegram_bot_token_enc', ''))
                self.telegram_chat_id = st.get('telegram_chat_id', '')
                # خيارات أنواع الإشعارات
                self.telegram_notify_success = st.get('telegram_notify_success', True)
                self.telegram_notify_errors = st.get('telegram_notify_errors', True)
                # تحديث مثيل TelegramNotifier
                telegram_notifier.enabled = self.telegram_enabled
                telegram_notifier.bot_token = self.telegram_bot_token
                telegram_notifier.chat_id = self.telegram_chat_id
                telegram_notifier.notify_success = self.telegram_notify_success
                telegram_notifier.notify_errors = self.telegram_notify_errors
            except Exception:
                self.theme = 'dark'
                self._user_token_buffer = ""
                self._saved_page_tokens_buffer = {}
                self.auto_move_uploaded = True
                self.working_hours_enabled = False
                self.working_hours_start = '09:00'
                self.working_hours_end = '23:00'
                self.watermark_enabled = False
                self.watermark_logo_path = ''
                self.watermark_position = 'bottom_right'
                self.watermark_opacity = 0.8
                self.validate_videos = True
                self.internet_check_enabled = True
                self.telegram_enabled = False
                self.telegram_bot_token = ''
                self.telegram_chat_id = ''
                self.telegram_notify_success = True
                self.telegram_notify_errors = True
                # تحديث مثيل TelegramNotifier عند فشل التحميل
                telegram_notifier.enabled = self.telegram_enabled
                telegram_notifier.bot_token = self.telegram_bot_token
                telegram_notifier.chat_id = self.telegram_chat_id
                telegram_notifier.notify_success = self.telegram_notify_success
                telegram_notifier.notify_errors = self.telegram_notify_errors
        else:
            self._user_token_buffer = ""
            self._saved_page_tokens_buffer = {}
            self.auto_move_uploaded = True
            self.working_hours_enabled = False
            self.working_hours_start = '09:00'
            self.working_hours_end = '23:00'
            self.watermark_enabled = False
            self.watermark_logo_path = ''
            self.watermark_position = 'bottom_right'
            self.watermark_opacity = 0.8
            self.validate_videos = True
            self.internet_check_enabled = True
            self.telegram_enabled = False
            self.telegram_bot_token = ''
            self.telegram_chat_id = ''
            self.telegram_notify_success = True
            self.telegram_notify_errors = True
            # تحديث مثيل TelegramNotifier عند عدم وجود ملف إعدادات
            telegram_notifier.enabled = self.telegram_enabled
            telegram_notifier.bot_token = self.telegram_bot_token
            telegram_notifier.chat_id = self.telegram_chat_id
            telegram_notifier.notify_success = self.telegram_notify_success
            telegram_notifier.notify_errors = self.telegram_notify_errors

    def _setup_system_tray(self):
        """إعداد أيقونة System Tray للتشغيل في الخلفية."""
        # التحقق من توفر System Tray
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            self._log_append('تحذير: System Tray غير متوفر في هذا النظام')
            return

        # استخدام الأيقونة الموحدة للتطبيق
        app_icon = load_app_icon()

        self.tray_icon = QSystemTrayIcon(app_icon, self)
        self.tray_icon.setToolTip(APP_TITLE)

        # إنشاء قائمة السياق لأيقونة Tray
        tray_menu = QMenu()

        # خيار إظهار/إخفاء النافذة
        show_action = create_icon_action('إظهار النافذة', 'eye', self)
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        # خيار تشغيل/إيقاف المجدول
        self.tray_start_action = create_icon_action('تشغيل المجدول', 'play', self)
        self.tray_start_action.triggered.connect(self.start_scheduler)
        tray_menu.addAction(self.tray_start_action)

        self.tray_stop_action = create_icon_action('إيقاف المجدول', 'stop', self)
        self.tray_stop_action.triggered.connect(self.stop_scheduler)
        tray_menu.addAction(self.tray_stop_action)

        tray_menu.addSeparator()

        # خيار الخروج النهائي
        exit_action = create_icon_action('إغلاق البرنامج نهائياً', 'close', self)
        exit_action.triggered.connect(self._exit_app)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)

        # التعامل مع النقر على أيقونة Tray
        self.tray_icon.activated.connect(self._on_tray_activated)

        # إظهار الأيقونة في Tray
        self.tray_icon.show()

    def show_from_tray(self):
        """إظهار النافذة من صينية النظام."""
        self.show()
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)

    def restore_from_another_instance(self):
        """استعادة النافذة عند استلام رسالة من نسخة أخرى."""
        self.show_from_tray()

    def _show_from_tray(self):
        """إظهار النافذة الرئيسية من Tray."""
        log_info('[Window] _show_from_tray called - جاري إظهار النافذة')

        # Use the new show_from_tray method
        self.show_from_tray()

        # في Windows، استخدام SetForegroundWindow لضمان جلب النافذة للأمام
        # هذا مهم خصوصاً عند استدعاء الإظهار من نسخة أخرى
        if sys.platform == 'win32':
            try:
                # الحصول على handle النافذة
                hwnd = int(self.winId())

                # استخدام Windows API لجلب النافذة للأمام بشكل قوي
                # تخزين مؤقت للـ user32 لتجنب البحث المتكرر
                if not hasattr(self, '_user32'):
                    self._user32 = ctypes.windll.user32

                # Windows API Constants
                SW_RESTORE = 9
                SW_SHOW = 5
                HWND_TOP = 0
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2
                SWP_SHOWWINDOW = 0x0040
                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002

                # إذا كانت النافذة مصغرة، استعادتها
                self._user32.ShowWindow(hwnd, SW_RESTORE)
                self._user32.ShowWindow(hwnd, SW_SHOW)

                # محاولة ربط الخيط بالنافذة الأمامية الحالية (لتجاوز قيود Windows)
                try:
                    foreground_hwnd = self._user32.GetForegroundWindow()
                    if foreground_hwnd and foreground_hwnd != hwnd:
                        # الحصول على معرف الخيط للنافذة الأمامية الحالية
                        foreground_thread = self._user32.GetWindowThreadProcessId(foreground_hwnd, None)

                        # التحقق من نجاح الحصول على معرف الخيط
                        if foreground_thread:
                            # الحصول على معرف الخيط الحالي
                            current_thread = ctypes.windll.kernel32.GetCurrentThreadId()

                            if foreground_thread != current_thread:
                                # ربط الخيوط لإعطاء صلاحية SetForegroundWindow
                                attached = self._user32.AttachThreadInput(foreground_thread, current_thread, True)
                                if attached:
                                    try:
                                        self._user32.SetForegroundWindow(hwnd)
                                    finally:
                                        # فك الربط دائماً
                                        self._user32.AttachThreadInput(foreground_thread, current_thread, False)
                                else:
                                    # فشل الربط، حاول مباشرة
                                    self._user32.SetForegroundWindow(hwnd)
                            else:
                                # نفس الخيط، لا حاجة للربط
                                self._user32.SetForegroundWindow(hwnd)
                        else:
                            # فشل الحصول على معرف الخيط
                            self._user32.SetForegroundWindow(hwnd)
                    else:
                        # لا توجد نافذة أمامية أو نحن بالفعل في المقدمة
                        self._user32.SetForegroundWindow(hwnd)
                except (OSError, AttributeError, ctypes.ArgumentError) as e:
                    # إذا فشل الربط، حاول مباشرة
                    log_debug(f'[Window] خطأ في AttachThreadInput: {e}')
                    try:
                        self._user32.SetForegroundWindow(hwnd)
                    except Exception:
                        pass

                # تفعيل النافذة
                self._user32.SetActiveWindow(hwnd)

                # جعل النافذة topmost مؤقتاً ثم إعادتها لحالتها الطبيعية
                # هذا يضمن ظهورها فوق جميع النوافذ الأخرى
                self._user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                          SWP_SHOWWINDOW | SWP_NOSIZE | SWP_NOMOVE)
                self._user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                                          SWP_SHOWWINDOW | SWP_NOSIZE | SWP_NOMOVE)

                # رفع النافذة لأعلى Z-order
                self._user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
                                          SWP_SHOWWINDOW | SWP_NOSIZE | SWP_NOMOVE)

                # جلب التركيز للنافذة
                self._user32.BringWindowToTop(hwnd)

            except Exception as e:
                log_debug(f'[Window] خطأ في استخدام Windows API لإظهار النافذة: {e}')

    def _on_tray_activated(self, reason):
        """معالج النقر على أيقونة Tray."""
        # إظهار النافذة عند النقر على الأيقونة (نقرة واحدة أو مزدوجة)
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self._show_from_tray()

    def _exit_app(self):
        """إغلاق البرنامج نهائياً."""
        # تنظيف الـ Threads النشطة قبل الإغلاق لتجنب crash
        self._cleanup_threads()
        self.stop_scheduler()
        self.save_all()
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()

    def apply_theme(self, theme: str, announce=True):
        self.theme = "dark" if theme == "dark" else "light"
        app = QApplication.instance()
        if HAS_QDARKTHEME:
            try:
                css = qdarktheme.load_stylesheet(self.theme)
            except Exception:
                css = ""
        else:
            # Fallback يدوي إذا لم تتوفر المكتبة
            if self.theme == "dark":
                css = """
                QWidget { background-color: #242933; color: #e6e6e6; }
                QMenuBar, QMenu { background-color: #2e3440; color:#e6e6e6; }
                """
            else:
                # استخدام Light Theme Fallback للوضع الفاتح
                css = LIGHT_THEME_FALLBACK

        # تطبيق الستايل المناسب حسب الثيم
        if self.theme == "dark":
            app.setStyleSheet(css + CUSTOM_STYLES)
        else:
            # للوضع الفاتح، نستخدم الستايل الفاتح فقط (بدون CUSTOM_STYLES الداكن)
            app.setStyleSheet(css)

        # تحديث مؤشرات القائمة
        self._update_theme_menu_indicators()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # تعيين اتجاه الواجهة من اليمين لليسار (RTL) للغة العربية
        central.setLayoutDirection(Qt.RightToLeft)
        self.setLayoutDirection(Qt.RightToLeft)

        root = QVBoxLayout(central)

        self._build_menu_bar()

        # ═══════════════════════════════════════════════════════════
        # القائمة الرئيسية
        # ═══════════════════════════════════════════════════════════

        main_h = QHBoxLayout()
        left = QVBoxLayout()

        # تبويبات الصفحات والإعدادات (تم إزالة تبويب الإحصائيات)
        # تم إزالة تبويب الستوري المنفصل من هنا (Requirement 3)
        # لأن خيار الفيديو/الستوري موجود بالفعل في إعدادات الصفحة على اليمين
        self.mode_tabs = QTabWidget()

        # تبويب الصفحات - استخدام PagesPanel
        self.pages_panel = PagesPanel(self)
        if HAS_QTAWESOME:
            self.mode_tabs.addTab(self.pages_panel, get_icon(ICONS['pages'], ICON_COLORS.get('pages')), 'الصفحات')
        else:
            self.mode_tabs.addTab(self.pages_panel, 'الصفحات')

        # تبويب الإعدادات المتقدمة (تم إزالة ساعات العمل منها - Requirement 4)
        # إضافة QScrollArea لدعم التمرير بعجلة الماوس (Issue #2)
        settings_tab = QWidget()
        settings_tab_layout = QVBoxLayout(settings_tab)
        settings_tab_layout.setContentsMargins(0, 0, 0, 0)

        # إنشاء منطقة التمرير
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        settings_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        settings_scroll.setFrameShape(QFrame.NoFrame)

        # ويدجت داخلي يحتوي على جميع الإعدادات
        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)
        self._build_settings_tab(settings_layout)

        settings_scroll.setWidget(settings_content)
        settings_tab_layout.addWidget(settings_scroll)

        if HAS_QTAWESOME:
            self.mode_tabs.addTab(settings_tab, get_icon(ICONS['settings'], ICON_COLORS.get('settings')), 'إعدادات')
        else:
            self.mode_tabs.addTab(settings_tab, 'إعدادات')

        self.mode_tabs.currentChanged.connect(self._on_mode_tab_changed)
        left.addWidget(self.mode_tabs)
        main_h.addLayout(left, 2)

        right = QVBoxLayout()
        page_group = QGroupBox('إعدادات الصفحة المحددة')
        page_group_layout = QVBoxLayout()

        # إنشاء منطقة التمرير
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)

        # ويدجت داخلي يحتوي على جميع الإعدادات
        scroll_content = QWidget()
        page_form = QFormLayout(scroll_content)
        page_form.setSpacing(8)
        page_form.setContentsMargins(5, 5, 5, 5)

        # خيار التبديل بين فيديوهات وستوري وريلز (في الأعلى)
        self.job_type_combo = NoScrollComboBox()
        self.job_type_combo.addItems(['🎥 فيديوهات', '📱 ستوري', '🎬 ريلز'])
        self.job_type_combo.setToolTip('اختر نوع المحتوى: فيديوهات أو ستوري أو ريلز')
        self.job_type_combo.currentIndexChanged.connect(self._on_job_type_changed)
        page_form.addRow('نوع المحتوى:', self.job_type_combo)

        self.selected_page_label = QLabel('لم يتم اختيار صفحة')
        page_form.addRow('الصفحة:', self.selected_page_label)

        self.folder_btn = create_icon_button('اختر مجلد الفيديوهات', 'folder')
        self.folder_btn.clicked.connect(self.choose_folder)
        page_form.addRow('المجلد:', self.folder_btn)

        # ==================== نظام الجدولة ====================
        schedule_group = QGroupBox('⏰ نظام الجدولة')
        schedule_layout = QVBoxLayout()

        # خيار التبديل بين النظامين
        switch_row = QHBoxLayout()

        self.interval_radio = QRadioButton('⏱️ الفاصل الزمني')
        self.interval_radio.setChecked(True)  # الافتراضي
        self.interval_radio.toggled.connect(self._on_schedule_mode_changed)
        switch_row.addWidget(self.interval_radio)

        switch_row.addStretch()

        self.smart_schedule_radio = QRadioButton('📅 الجدول الذكي')
        self.smart_schedule_radio.toggled.connect(self._on_schedule_mode_changed)
        switch_row.addWidget(self.smart_schedule_radio)

        schedule_layout.addLayout(switch_row)

        # ─────────────────────────────────────────────────────

        # قسم الفاصل الزمني (يظهر عند اختيار الفاصل الزمني)
        self.interval_widget = QWidget()
        interval_layout = QHBoxLayout(self.interval_widget)
        interval_layout.setContentsMargins(0, 10, 0, 0)

        # الساعة في اليسار
        self.current_time_label = QLabel()
        self.current_time_label.setStyleSheet('font-size: 14px; font-weight: bold; color: #3498db;')
        interval_layout.addWidget(self.current_time_label)

        interval_layout.addStretch()

        # الفاصل الزمني في اليمين
        interval_layout.addWidget(QLabel('الفاصل:'))
        self.interval_value_spin = NoScrollSpinBox()
        self.interval_value_spin.setRange(1, 1000000)
        self.interval_value_spin.setValue(3)
        interval_layout.addWidget(self.interval_value_spin)

        self.interval_unit_combo = NoScrollComboBox()
        self.interval_unit_combo.addItems(['ساعات', 'دقائق'])
        interval_layout.addWidget(self.interval_unit_combo)

        schedule_layout.addWidget(self.interval_widget)

        # ─────────────────────────────────────────────────────

        # قسم الجدول الذكي (يظهر عند اختيار الجدول الذكي)
        self.smart_schedule_widget = QWidget()
        self.smart_schedule_widget.setVisible(False)  # مخفي افتراضياً
        smart_layout = QVBoxLayout(self.smart_schedule_widget)
        smart_layout.setContentsMargins(0, 10, 0, 0)

        # اختيار القالب
        template_row = QHBoxLayout()
        template_row.addWidget(QLabel('اختر قالب:'))

        self.template_combo = NoScrollComboBox()
        self.template_combo.setMinimumWidth(150)
        self._refresh_templates_combo()
        self.template_combo.currentIndexChanged.connect(self._update_template_times_label)
        template_row.addWidget(self.template_combo)

        self.manage_templates_btn = QPushButton('📋 إدارة القوالب')
        self.manage_templates_btn.clicked.connect(self._open_schedule_templates_dialog_and_refresh)
        template_row.addWidget(self.manage_templates_btn)

        template_row.addStretch()
        smart_layout.addLayout(template_row)

        # عرض أوقات القالب المختار
        self.template_times_label = QLabel('📋 الأوقات: --')
        self.template_times_label.setStyleSheet('color: #7f8c8d; margin-top: 5px;')
        smart_layout.addWidget(self.template_times_label)

        schedule_layout.addWidget(self.smart_schedule_widget)

        schedule_group.setLayout(schedule_layout)
        page_form.addRow(schedule_group)

        # Timer لتحديث الوقت الحالي كل ثانية
        self.time_update_timer = QTimer()
        self.time_update_timer.timeout.connect(self._update_current_time)
        self.time_update_timer.start(1000)
        self._update_current_time()  # تحديث فوري

        # لوحة إعدادات الستوري - Story Panel
        self.story_panel = StoryPanel(self)
        self.story_panel.setVisible(False)  # مخفية افتراضياً (تظهر فقط في وضع الستوري)
        page_form.addRow(self.story_panel)

        # التوقيت العشوائي (Anti-Ban) - للفيديو فقط
        jitter_row = QHBoxLayout()
        self.jitter_checkbox = QCheckBox('تفعيل التوقيت العشوائي')
        self.jitter_checkbox.setToolTip('إضافة تباين عشوائي للفاصل الزمني لمحاكاة السلوك البشري')
        jitter_row.addWidget(self.jitter_checkbox)
        jitter_row.addWidget(QLabel('نسبة التباين:'))
        self.jitter_percent_spin = NoScrollSpinBox()
        self.jitter_percent_spin.setRange(1, 50)
        self.jitter_percent_spin.setValue(10)
        self.jitter_percent_spin.setSuffix('%')
        self.jitter_percent_spin.setToolTip('مثال: 10% يعني أن الفاصل 60 دقيقة سيكون بين 54-66 دقيقة')
        jitter_row.addWidget(self.jitter_percent_spin)
        self.jitter_widget = QWidget()
        self.jitter_widget.setLayout(jitter_row)
        page_form.addRow('🛡️ Anti-Ban:', self.jitter_widget)

        # ترتيب الملفات
        sort_row = QHBoxLayout()
        self.sort_by_combo = NoScrollComboBox()
        self.sort_by_combo.addItems(['أبجدي (الافتراضي)', 'عشوائي', 'الأقدم أولاً', 'الأحدث أولاً'])
        self.sort_by_combo.setToolTip('اختر طريقة ترتيب الملفات للنشر')
        sort_row.addWidget(self.sort_by_combo)
        page_form.addRow('🔀 ترتيب النشر:', sort_row)

        # العنوان (للفيديو فقط)
        # العنوان (للفيديو والريلز فقط) - Requirement 5: إزالة من الستوري
        title_row = QHBoxLayout()
        self.title_label = QLabel('العنوان:')
        title_row.addWidget(self.title_label)
        self.page_title_input = QLineEdit()
        self.page_title_input.setPlaceholderText('عنوان الفيديو (يدعم المتغيرات)')
        self.page_title_input.setToolTip(
            'المتغيرات المدعومة:\n'
            '{filename} - اسم الملف\n'
            '{date} أو {date_ymd} - التاريخ (YYYY-MM-DD)\n'
            '{date_dmy} - التاريخ (DD/MM/YYYY)\n'
            '{date_time} - التاريخ والوقت (YYYY-MM-DD HH:MM)\n'
            '{random_emoji} - إيموجي عشوائي\n'
            '{page_name} - اسم الصفحة\n'
            '{index} - رقم الملف\n'
            '{total} - إجمالي الملفات'
        )
        self.use_filename_checkbox = QCheckBox('استخدم اسم الملف كعنوان')
        self.use_filename_checkbox.stateChanged.connect(self._toggle_title_editable)
        title_row.addWidget(self.page_title_input, 4)
        title_row.addWidget(self.use_filename_checkbox, 1)
        self.title_widget = QWidget()
        self.title_widget.setLayout(title_row)
        page_form.addRow(self.title_widget)

        # صف الوصف مع زر مدير الهاشتاجات (للفيديو والريلز فقط) - Requirement 5
        desc_row = QHBoxLayout()
        self.desc_label = QLabel('الوصف:')
        desc_row.addWidget(self.desc_label)
        self.page_desc_input = QLineEdit()
        self.page_desc_input.setPlaceholderText('وصف الفيديو (يدعم المتغيرات)')
        self.page_desc_input.setToolTip(
            'المتغيرات المدعومة:\n'
            '{filename} - اسم الملف\n'
            '{date} أو {date_ymd} - التاريخ (YYYY-MM-DD)\n'
            '{date_dmy} - التاريخ (DD/MM/YYYY)\n'
            '{date_time} - التاريخ والوقت (YYYY-MM-DD HH:MM)\n'
            '{random_emoji} - إيموجي عشوائي\n'
            '{page_name} - اسم الصفحة\n'
            '{index} - رقم الملف\n'
            '{total} - إجمالي الملفات'
        )
        desc_row.addWidget(self.page_desc_input, 4)

        hashtag_btn = create_icon_button('هاشتاجات', 'hashtag')
        hashtag_btn.setToolTip('فتح مدير الهاشتاجات')
        hashtag_btn.clicked.connect(self._show_hashtag_manager)
        desc_row.addWidget(hashtag_btn, 1)
        self.desc_widget = QWidget()
        self.desc_widget.setLayout(desc_row)
        page_form.addRow(self.desc_widget)

        # مجموعة العلامة المائية (للفيديو فقط) - لكل مهمة
        self.job_watermark_group = QGroupBox('العلامة المائية')
        if HAS_QTAWESOME:
            self.job_watermark_group.setTitle('')
            watermark_title_layout = QHBoxLayout()
            watermark_icon_label = QLabel()
            watermark_icon_label.setPixmap(get_icon(ICONS['watermark'], ICON_COLORS.get('watermark')).pixmap(16, 16))
            watermark_title_layout.addWidget(watermark_icon_label)
            watermark_title_layout.addWidget(QLabel('العلامة المائية'))
            watermark_title_layout.addStretch()
        watermark_layout = QFormLayout()

        self.job_watermark_checkbox = QCheckBox('تفعيل العلامة المائية')
        self.job_watermark_checkbox.setToolTip('إضافة علامة مائية على الفيديو قبل الرفع')
        watermark_layout.addRow(self.job_watermark_checkbox)

        watermark_path_row = QHBoxLayout()
        self.job_watermark_path_label = QLabel('لم يتم اختيار شعار')
        self.job_watermark_path_label.setStyleSheet('color: gray;')
        watermark_path_row.addWidget(self.job_watermark_path_label, 3)
        self.job_watermark_browse_btn = create_icon_button('اختر', 'folder')
        self.job_watermark_browse_btn.clicked.connect(self._choose_job_watermark)
        watermark_path_row.addWidget(self.job_watermark_browse_btn, 1)
        watermark_layout.addRow('الشعار:', watermark_path_row)

        self.job_watermark_position_combo = NoScrollComboBox()
        self.job_watermark_position_combo.addItems(['أعلى يسار', 'أعلى يمين', 'أسفل يسار', 'أسفل يمين', 'وسط'])
        self.job_watermark_position_combo.setCurrentIndex(3)  # أسفل يمين
        watermark_layout.addRow('الموقع:', self.job_watermark_position_combo)

        # الحجم (جديد)
        size_row = QHBoxLayout()
        self.job_watermark_size_slider = NoScrollSlider(Qt.Horizontal)
        self.job_watermark_size_slider.setRange(10, 100)  # 10% إلى 100%
        self.job_watermark_size_slider.setValue(15)  # 15% افتراضي
        self.job_watermark_size_label = QLabel('15%')
        self.job_watermark_size_slider.valueChanged.connect(
            lambda v: self.job_watermark_size_label.setText(f'{v}%')
        )
        size_row.addWidget(self.job_watermark_size_slider, 4)
        size_row.addWidget(self.job_watermark_size_label, 1)
        watermark_layout.addRow('الحجم:', size_row)

        opacity_row = QHBoxLayout()
        self.job_watermark_opacity_slider = NoScrollSlider(Qt.Horizontal)
        self.job_watermark_opacity_slider.setRange(10, 100)
        self.job_watermark_opacity_slider.setValue(80)
        self.job_watermark_opacity_label = QLabel('80%')
        self.job_watermark_opacity_slider.valueChanged.connect(
            lambda v: self.job_watermark_opacity_label.setText(f'{v}%')
        )
        opacity_row.addWidget(self.job_watermark_opacity_slider, 4)
        opacity_row.addWidget(self.job_watermark_opacity_label, 1)
        watermark_layout.addRow('الشفافية:', opacity_row)

        # زر المعاينة
        preview_btn = create_icon_button('معاينة', 'eye')
        preview_btn.setToolTip('معاينة العلامة المائية على فيديو')
        preview_btn.clicked.connect(self._show_watermark_preview)
        watermark_layout.addRow(preview_btn)

        self.job_watermark_group.setLayout(watermark_layout)
        self.job_watermark_group.setVisible(True)  # للفيديو فقط
        page_form.addRow(self.job_watermark_group)

        # تعيين المحتوى للـ ScrollArea
        scroll_area.setWidget(scroll_content)
        page_group_layout.addWidget(scroll_area)

        # أزرار الإضافة والاختبار (خارج منطقة التمرير)
        buttons_row = QHBoxLayout()
        add_job_btn = create_icon_button('إضافة/تحديث وظيفة', 'add')
        add_job_btn.clicked.connect(self.add_update_job)
        buttons_row.addWidget(add_job_btn)

        # زر اختبار رفع الآن (Requirement 6)
        self.run_now_btn = create_icon_button('اختبار رفع الآن', 'play')
        self.run_now_btn.clicked.connect(self.run_selected_job_now)
        buttons_row.addWidget(self.run_now_btn)

        # زر إيقاف الرفع (Requirement 6 - مخفي افتراضياً)
        self.stop_upload_btn = create_icon_button('⏹️ إيقاف', 'stop')
        self.stop_upload_btn.setStyleSheet('background-color: #d32f2f; color: white; font-weight: bold;')
        self.stop_upload_btn.setToolTip('إيقاف عملية الرفع الجارية')
        self.stop_upload_btn.setVisible(False)
        self.stop_upload_btn.clicked.connect(self._on_stop_upload)
        buttons_row.addWidget(self.stop_upload_btn)

        # متغير لإيقاف الرفع (Requirement 6)
        self._upload_stop_requested = threading.Event()
        # متغير لتتبع الوظيفة قيد الرفع (لإيقاف الفيديو بسرعة)
        self._current_uploading_job = None

        page_group_layout.addLayout(buttons_row)
        page_group.setLayout(page_group_layout)
        right.addWidget(page_group)

        # استخدام مكون SchedulerUI المستخرج
        # Use extracted SchedulerUI component
        self.scheduler_ui = SchedulerUI(self)
        
        # ربط الإشارات - Connect signals
        self.scheduler_ui.log_message.connect(self._log_append)
        self.scheduler_ui.save_requested.connect(self.save_all)
        self.scheduler_ui.job_scheduled.connect(self._on_job_scheduled)
        self.scheduler_ui.job_cancelled.connect(self._on_job_cancelled)
        self.scheduler_ui.scheduler_started.connect(self._on_scheduler_ui_start_requested)
        self.scheduler_ui.jobs_table.job_double_clicked.connect(self._load_job_to_form)
        
        # إضافة واجهة المجدول
        right.addWidget(self.scheduler_ui)
        
        # الحفاظ على مرجع للوصول السريع
        self.jobs_table = self.scheduler_ui.jobs_table
        self.concurrent_spin = self.scheduler_ui.concurrent_spin

        main_h.addLayout(right, 3)
        root.addLayout(main_h)

        root.addWidget(self._separator())

        # صف التحكم السفلي
        bottom_controls = QHBoxLayout()

        # زر ملوّن لخيار نقل الفيديوهات تلقائياً بعد الرفع
        self.auto_move_btn = QPushButton()
        self._update_auto_move_button()
        self.auto_move_btn.setToolTip('انقر للتبديل بين تفعيل/تعطيل نقل الفيديو تلقائياً إلى مجلد "Uploaded" بعد نجاح الرفع')
        self.auto_move_btn.clicked.connect(self._toggle_auto_move)
        bottom_controls.addWidget(self.auto_move_btn)

        save_btn = create_icon_button('حفظ', 'save')
        save_btn.clicked.connect(self.save_all)
        bottom_controls.addWidget(save_btn)

        root.addLayout(bottom_controls)

        prog_h = QHBoxLayout()
        prog_h.addWidget(QLabel('التقدم:'))

        # استخدام مكون ProgressWidget المستخرج
        # Use extracted ProgressWidget component
        self.progress_widget = ProgressWidget(show_label=True)
        prog_h.addWidget(self.progress_widget)
        root.addLayout(prog_h)

        # للتوافق مع الكود القديم - For backward compatibility
        self.progress_bar = self.progress_widget.progress_bar
        self.progress_label = self.progress_widget.status_label

        # استخدام مكون LogViewer المستخرج
        # Use extracted LogViewer component
        self.log_text = LogViewer()
        root.addWidget(self.log_text)

        # شريط الحالة لرسائل الثيم
        status = QStatusBar()
        self.setStatusBar(status)

        # ربط إشارات لوحة الصفحات - Connect PagesPanel signals
        self.pages_panel.page_selected.connect(self.on_page_selected)
        self.pages_panel.pages_refreshed.connect(self._on_pages_refreshed)
        self.pages_panel.log_message.connect(self._log_append)
        self.pages_panel.token_management_requested.connect(self._open_token_management)

    def _build_menu_bar(self):
        menubar = QMenuBar()
        menubar.setLayoutDirection(Qt.RightToLeft)

        # قائمة العرض
        view_menu = menubar.addMenu('عرض')
        if HAS_QTAWESOME:
            view_menu.setIcon(get_icon(ICONS['eye'], ICON_COLORS.get('eye')))

        # قائمة المظهر الفرعية
        theme_menu = view_menu.addMenu('المظهر')
        if HAS_QTAWESOME:
            theme_menu.setIcon(get_icon(ICONS['watermark'], ICON_COLORS.get('watermark')))

        # إضافة أيقونات للمظهر
        dark_text = 'داكن ✓' if self.theme == 'dark' else 'داكن'
        light_text = 'فاتح ✓' if self.theme == 'light' else 'فاتح'

        self.act_dark = create_icon_action(dark_text, 'moon', self)
        self.act_light = create_icon_action(light_text, 'sun', self)

        self.act_dark.triggered.connect(self._set_dark_theme)
        self.act_light.triggered.connect(self._set_light_theme)

        theme_menu.addAction(self.act_dark)
        theme_menu.addAction(self.act_light)
        self.setMenuBar(menubar)

    def _set_dark_theme(self):
        if self.theme != 'dark':
            self.apply_theme('dark')
            self._save_settings()

    def _set_light_theme(self):
        if self.theme != 'light':
            self.apply_theme('light')
            self._save_settings()

    def _update_theme_menu_indicators(self):
        if hasattr(self, 'act_dark') and hasattr(self, 'act_light'):
            self.act_dark.setText('🌙 داكن ✓' if self.theme == 'dark' else '🌙 داكن')
            self.act_light.setText('☀️ فاتح ✓' if self.theme == 'light' else '☀️ فاتح')

    def _separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep

    def _toggle_title_editable(self, state):
        checked = (state == Qt.Checked)
        self.page_title_input.setReadOnly(checked)
        if checked:
            self.page_title_input.setText('{filename}')

    def _update_current_time(self):
        """تحديث عرض الوقت الحالي (Requirement 9)."""
        now = datetime.now()
        self.current_time_label.setText(f'🕐 {now.strftime("%I:%M:%S %p")}')

    def _refresh_templates_combo(self):
        """تحديث قائمة القوالب في الكومبو بوكس."""
        try:
            self.template_combo.clear()
            templates = get_all_templates()

            for template in templates:
                name = template['name']
                if template['is_default']:
                    name = f'⭐ {name}'
                self.template_combo.addItem(name, template['id'])

            # تحديد القالب الافتراضي
            default_template = get_default_template()
            if default_template:
                for i in range(self.template_combo.count()):
                    if self.template_combo.itemData(i) == default_template['id']:
                        self.template_combo.setCurrentIndex(i)
                        break
        except Exception:
            self.template_combo.addItem('الافتراضي', 0)

    def _on_schedule_mode_changed(self, checked):
        """التبديل بين نظام الفاصل الزمني والجدول الذكي."""
        use_interval = self.interval_radio.isChecked()
        self.interval_widget.setVisible(use_interval)
        self.smart_schedule_widget.setVisible(not use_interval)

        # تحديث عرض أوقات القالب عند التبديل للجدول الذكي
        if not use_interval:
            self._update_template_times_label()

    def _update_template_times_label(self):
        """تحديث عرض أوقات القالب المختار."""
        try:
            template_id = self.template_combo.currentData()
            if template_id:
                template = get_template_by_id(template_id)
                if template and 'times' in template:
                    times_str = ', '.join(template['times'])
                    self.template_times_label.setText(f'📋 الأوقات: {times_str}')
                else:
                    self.template_times_label.setText('📋 الأوقات: --')
            else:
                self.template_times_label.setText('📋 الأوقات: --')
        except Exception:
            self.template_times_label.setText('📋 الأوقات: --')

    def _open_schedule_templates_dialog_and_refresh(self):
        """فتح نافذة إدارة القوالب ثم تحديث القائمة."""
        self._open_schedule_templates_dialog()
        self._refresh_templates_combo()
        self._update_template_times_label()

    def _on_job_double_clicked(self, item):
        """فتح نافذة تعديل المهمة عند الضغط المزدوج (للتوافق مع الكود القديم)."""
        job = item.data(Qt.UserRole)
        if not job:
            return

        # تحميل بيانات المهمة في النموذج
        self._load_job_to_form(job)

    def _load_job_to_form(self, job):
        """تحميل بيانات المهمة إلى نموذج التعديل (Requirement 3)."""
        # Store the job being edited so add_update_job() can update it directly
        self._editing_job = job

        # تحديد نوع المهمة
        if isinstance(job, StoryJob):
            self.job_type_combo.setCurrentIndex(1)  # ستوري
            self.folder_btn.setText(job.folder if job.folder else 'اختر مجلد الستوري')
            self.story_panel.set_stories_per_schedule(job.stories_per_schedule)
            self.story_panel.set_anti_ban_enabled(job.anti_ban_enabled)
            self.story_panel.set_random_delay_min(job.random_delay_min if job.random_delay_min > 0 else DEFAULT_RANDOM_DELAY_MIN)
            self.story_panel.set_random_delay_max(job.random_delay_max if job.random_delay_max > 0 else DEFAULT_RANDOM_DELAY_MAX)
        elif isinstance(job, ReelsJob):
            self.job_type_combo.setCurrentIndex(2)  # ريلز
            self.folder_btn.setText(job.folder if job.folder else 'اختر مجلد الريلز')
            self.page_title_input.setText(job.title_template or '{filename}')
            self.page_desc_input.setText(job.description_template or '')
            self.use_filename_checkbox.setChecked(job.use_filename_as_title)
            self.jitter_checkbox.setChecked(job.jitter_enabled)
            self.jitter_percent_spin.setValue(job.jitter_percent)
            # العلامة المائية
            self.job_watermark_checkbox.setChecked(job.watermark_enabled)
            if job.watermark_path:
                self.job_watermark_path_label.setText(job.watermark_path)
                self.job_watermark_path_label.setStyleSheet('')
            else:
                self.job_watermark_path_label.setText('لم يتم اختيار شعار')
                self.job_watermark_path_label.setStyleSheet('color: gray;')
            position_index = {'top_left': 0, 'top_right': 1, 'bottom_left': 2, 'bottom_right': 3, 'center': 4}.get(job.watermark_position, 3)
            self.job_watermark_position_combo.setCurrentIndex(position_index)
            self.job_watermark_opacity_slider.setValue(int(job.watermark_opacity * 100))
            self.job_watermark_size_slider.setValue(int(job.watermark_scale * 100))
        else:
            # فيديو
            self.job_type_combo.setCurrentIndex(0)
            self.folder_btn.setText(job.folder if job.folder else 'اختر مجلد الفيديوهات')
            self.page_title_input.setText(job.title_template or '{filename}')
            self.page_desc_input.setText(job.description_template or '')
            self.use_filename_checkbox.setChecked(job.use_filename_as_title)
            self.jitter_checkbox.setChecked(job.jitter_enabled)
            self.jitter_percent_spin.setValue(job.jitter_percent)
            # العلامة المائية
            if hasattr(job, 'watermark_enabled'):
                self.job_watermark_checkbox.setChecked(job.watermark_enabled)
                if job.watermark_path:
                    self.job_watermark_path_label.setText(job.watermark_path)
                    self.job_watermark_path_label.setStyleSheet('')
                else:
                    self.job_watermark_path_label.setText('لم يتم اختيار شعار')
                    self.job_watermark_path_label.setStyleSheet('color: gray;')
                position_index = {'top_left': 0, 'top_right': 1, 'bottom_left': 2, 'bottom_right': 3, 'center': 4}.get(job.watermark_position, 3)
                self.job_watermark_position_combo.setCurrentIndex(position_index)
                self.job_watermark_opacity_slider.setValue(int(job.watermark_opacity * 100))
                self.job_watermark_size_slider.setValue(int(job.watermark_scale * 100))

        # الإعدادات المشتركة
        val, unit = seconds_to_value_unit(job.interval_seconds)
        self.interval_value_spin.setValue(val)
        idx = self.interval_unit_combo.findText(unit)
        if idx >= 0:
            self.interval_unit_combo.setCurrentIndex(idx)

        sort_index = {'name': 0, 'random': 1, 'date_created': 2, 'date_modified': 3}.get(job.sort_by, 0)
        self.sort_by_combo.setCurrentIndex(sort_index)

        # تحميل إعدادات نظام الجدولة (الفاصل الزمني أو الجدول الذكي)
        use_smart_schedule = getattr(job, 'use_smart_schedule', False)
        template_id = getattr(job, 'template_id', None)

        if use_smart_schedule:
            self.smart_schedule_radio.setChecked(True)
            # تحديد القالب إذا كان موجوداً
            if template_id:
                for i in range(self.template_combo.count()):
                    if self.template_combo.itemData(i) == template_id:
                        self.template_combo.setCurrentIndex(i)
                        break
        else:
            self.interval_radio.setChecked(True)

        # البحث في الصفحات وتحديدها باستخدام pages_panel
        job_app_name = getattr(job, 'app_name', '')  # الحصول على اسم التطبيق من المهمة
        self.pages_panel.find_and_select_page(job.page_id, job_app_name)

        # تطبيق تغيير نوع المحتوى
        self._on_job_type_changed(self.job_type_combo.currentIndex())

        self._log_append(f'📝 تم تحميل إعدادات المهمة: {job.page_name}')

    def _on_stop_upload(self):
        """إيقاف عملية الرفع الجارية (Requirement 6)."""
        self._upload_stop_requested.set()
        # إيقاف الوظيفة الحالية إذا كانت موجودة (للفيديو)
        if self._current_uploading_job is not None:
            self._current_uploading_job.cancel_requested = True
        self._log_append('⏹️ جاري إيقاف الرفع...')
        self.stop_upload_btn.setEnabled(False)
        self.stop_upload_btn.setText('⏹️ جاري الإيقاف...')

    def _on_upload_started(self):
        """تحديث الواجهة عند بدء الرفع (Requirement 6)."""
        self._upload_stop_requested.clear()
        self.run_now_btn.setEnabled(False)
        self.stop_upload_btn.setVisible(True)
        self.stop_upload_btn.setEnabled(True)
        self.stop_upload_btn.setText('⏹️ إيقاف')

    def _on_upload_finished(self):
        """تحديث الواجهة عند انتهاء الرفع (Requirement 6)."""
        self.run_now_btn.setEnabled(True)
        self.stop_upload_btn.setVisible(False)
        self._upload_stop_requested.clear()
        self._current_uploading_job = None

    def _update_auto_move_button(self):
        """تحديث مظهر زر نقل الفيديوهات بناءً على الحالة."""
        if self.auto_move_uploaded:
            self.auto_move_btn.setText('📁 نقل الفيديو: مفعّل')
            if HAS_QTAWESOME:
                self.auto_move_btn.setIcon(get_icon(ICONS['folder'], '#4CAF50'))
            self.auto_move_btn.setStyleSheet('''
                QPushButton {
                    background-color: #1B5E20;
                    color: white;
                    font-weight: bold;
                    border: 1px solid #4CAF50;
                    border-radius: 6px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #2E7D32;
                }
            ''')
        else:
            self.auto_move_btn.setText('📁 نقل الفيديو: معطّل')
            if HAS_QTAWESOME:
                self.auto_move_btn.setIcon(get_icon(ICONS['folder'], '#808080'))
            self.auto_move_btn.setStyleSheet('''
                QPushButton {
                    background-color: #424242;
                    color: #BDBDBD;
                    font-weight: bold;
                    border: 1px solid #616161;
                    border-radius: 6px;
                    padding: 6px 12px;
                }
                QPushButton:hover {
                    background-color: #515151;
                }
            ''')

    def _toggle_auto_move(self):
        """تبديل حالة نقل الفيديوهات تلقائياً."""
        self.auto_move_uploaded = not self.auto_move_uploaded
        self._update_auto_move_button()
        self._log_append(f'تم {"تفعيل" if self.auto_move_uploaded else "تعطيل"} نقل الفيديوهات تلقائياً بعد الرفع')

    def _log_append(self, text):
        """إضافة رسالة للسجل مع التمرير التلقائي للأسفل."""
        # معالجة رسالة إنهاء الرفع الخاصة (Requirement 6)
        if text == '__UPLOAD_FINISHED__':
            self._on_upload_finished()
            return

        ts = format_datetime_12h()
        self.log_text.append(f'[{ts}] {text}')

        # التمرير التلقائي للأسفل
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()

    def _update_progress(self, percent, status_text):
        """تحديث شريط التقدم والحالة - Update progress bar and status"""
        self.progress_widget.update(percent, status_text)

    def _clear_progress(self):
        """مسح شريط التقدم - Clear progress bar"""
        self.progress_widget.reset()

    def token_getter(self):
        """
        الحصول على التوكن للاستخدام.
        يستخدم أول توكن طويل متاح من نظام إدارة التوكينات.
        """
        # الحصول على التوكينات الطويلة من نظام إدارة التوكينات
        tokens = get_all_long_lived_tokens()
        if tokens:
            return tokens[0]  # استخدام أول توكن متاح
        return None

    def _open_token_management(self):
        """فتح نافذة إدارة التوكينات."""
        dialog = TokenManagementDialog(self)
        dialog.exec()
        # إعادة تعيين الـ Cache بعد تحديث التوكينات
        self._pages_cache = []
        self._pages_cache_grouped = {}
        self._pages_cache_time = 0

    def load_pages(self):
        """
        جلب الصفحات باستخدام جميع التطبيقات المحفوظة.
        يقوم بتفويض العملية إلى PagesPanel.
        """
        # الحصول على جميع التطبيقات (وليس فقط التوكينات)
        apps = get_all_app_tokens()

        if not apps:
            QMessageBox.warning(
                self,
                'لا توجد تطبيقات',
                'لم يتم العثور على تطبيقات.\n\n'
                'اضغط على "إدارة التوكينات" لإضافة تطبيق وجلب توكن طويل.'
            )
            return

        # التحقق من وجود توكينات طويلة
        apps_with_tokens = [app for app in apps if app.get('long_lived_token')]
        
        # تفويض عملية الجلب إلى PagesPanel
        self.pages_panel.load_pages(apps_with_tokens)
    
    def _on_pages_refreshed(self, pages: list):
        """
        معالج تحديث قائمة الصفحات من PagesPanel.
        يقوم بتحديث الـ cache المحلي للتوافق مع الكود القديم.
        
        Args:
            pages: قائمة الصفحات المحدثة
        
        Note:
            هذا للتوافق مع الكود القديم. يجب إعادة هيكلة الكود المعتمد
            لاستخدام pages_panel.get_pages_cache() مباشرة.
        """
        self._pages_cache = pages

    def on_page_selected(self, page_data=None):
        """
        معالج اختيار صفحة من لوحة الصفحات.
        
        Args:
            page_data: بيانات الصفحة المختارة (dict) أو None إذا لم يتم اختيار صفحة
        """
        if not page_data:
            self.selected_page_label.setText('لم يتم اختيار صفحة')
            self.folder_btn.setText('اختر مجلد الفيديوهات')
            self.interval_value_spin.setValue(3)
            self.interval_unit_combo.setCurrentIndex(0)
            self.page_title_input.setText('{filename}')
            self.page_desc_input.setText('')
            self.use_filename_checkbox.setChecked(False)
            self.page_title_input.setReadOnly(False)
            # إعادة تعيين الخيارات الجديدة
            self.job_type_combo.setCurrentIndex(0)
            self.jitter_checkbox.setChecked(False)
            self.jitter_percent_spin.setValue(10)
            self.sort_by_combo.setCurrentIndex(0)
            self.page_working_hours_checkbox.setChecked(False)
            self.story_panel.set_stories_per_schedule(DEFAULT_STORIES_PER_SCHEDULE)
            # إعادة تعيين نظام الجدولة للافتراضي (الفاصل الزمني)
            self.interval_radio.setChecked(True)
            # إعادة تعيين العلامة المائية
            self.job_watermark_checkbox.setChecked(False)
            self.job_watermark_path_label.setText('لم يتم اختيار شعار')
            self.job_watermark_path_label.setStyleSheet('color: gray;')
            self.job_watermark_position_combo.setCurrentIndex(3)  # أسفل يمين
            self.job_watermark_opacity_slider.setValue(80)
            self.job_watermark_size_slider.setValue(15)  # 15% افتراضي
            # إعادة تعيين إعدادات الستوري
            self.story_panel.reset_to_defaults()
            return

        # استخدام page_data المرسلة من PagesPanel
        p = page_data
        if not p or not isinstance(p, dict) or 'id' not in p:
            # البيانات غير صحيحة
            self.selected_page_label.setText('اختر صفحة من القائمة')
            return

        pid = p.get('id')
        # الحصول على اسم التطبيق من بيانات الصفحة (يتم تخزينه كـ _app_name أو app_name)
        app_name = p.get('_app_name', '') or p.get('app_name', '')
        job_key = make_job_key(pid, app_name)

        # عرض اسم الصفحة مع اسم التطبيق إذا كان موجوداً
        if app_name:
            self.selected_page_label.setText(f"{p.get('name')} ({pid}) - {app_name}")
        else:
            self.selected_page_label.setText(f"{p.get('name')} ({pid})")

        # البحث عن وظيفة موجودة (فيديو أو ستوري أو ريلز) باستخدام المفتاح المركب
        existing_video = self.jobs_map.get(job_key)
        existing_story = self.story_jobs_map.get(job_key)
        existing_reels = self.reels_jobs_map.get(job_key)

        if existing_video:
            self.job_type_combo.setCurrentIndex(0)  # فيديو
            self.folder_btn.setText(existing_video.folder if existing_video.folder else 'اختر مجلد الفيديوهات')
            val, unit = seconds_to_value_unit(existing_video.interval_seconds)
            self.interval_value_spin.setValue(val)
            idx = self.interval_unit_combo.findText(unit)
            if idx >= 0:
                self.interval_unit_combo.setCurrentIndex(idx)
            self.page_title_input.setText(existing_video.title_template or '{filename}')
            self.page_desc_input.setText(existing_video.description_template or '')
            self.use_filename_checkbox.setChecked(existing_video.use_filename_as_title)
            self.page_title_input.setReadOnly(existing_video.use_filename_as_title)
            self.jitter_checkbox.setChecked(existing_video.jitter_enabled)
            self.jitter_percent_spin.setValue(existing_video.jitter_percent)
            sort_index = {'name': 0, 'random': 1, 'date_created': 2, 'date_modified': 3}.get(existing_video.sort_by, 0)
            self.sort_by_combo.setCurrentIndex(sort_index)
            # تحميل إعدادات نظام الجدولة
            if getattr(existing_video, 'use_smart_schedule', False):
                self.smart_schedule_radio.setChecked(True)
                template_id = getattr(existing_video, 'template_id', None)
                if template_id:
                    for i in range(self.template_combo.count()):
                        if self.template_combo.itemData(i) == template_id:
                            self.template_combo.setCurrentIndex(i)
                            break
            else:
                self.interval_radio.setChecked(True)
            # تحميل إعدادات العلامة المائية
            self.job_watermark_checkbox.setChecked(existing_video.watermark_enabled)
            if existing_video.watermark_path:
                self.job_watermark_path_label.setText(existing_video.watermark_path)
                self.job_watermark_path_label.setStyleSheet('')
            else:
                self.job_watermark_path_label.setText('لم يتم اختيار شعار')
                self.job_watermark_path_label.setStyleSheet('color: gray;')
            positions = {'top_left': 0, 'top_right': 1, 'bottom_left': 2, 'bottom_right': 3, 'center': 4}
            self.job_watermark_position_combo.setCurrentIndex(positions.get(existing_video.watermark_position, 3))
            self.job_watermark_opacity_slider.setValue(int(existing_video.watermark_opacity * 100))
            self.job_watermark_size_slider.setValue(int(existing_video.watermark_scale * 100))
        elif existing_reels:
            self.job_type_combo.setCurrentIndex(2)  # ريلز
            self.folder_btn.setText(existing_reels.folder if existing_reels.folder else 'اختر مجلد الريلز')
            val, unit = seconds_to_value_unit(existing_reels.interval_seconds)
            self.interval_value_spin.setValue(val)
            idx = self.interval_unit_combo.findText(unit)
            if idx >= 0:
                self.interval_unit_combo.setCurrentIndex(idx)
            self.page_title_input.setText(existing_reels.title_template or '{filename}')
            self.page_desc_input.setText(existing_reels.description_template or '')
            self.use_filename_checkbox.setChecked(existing_reels.use_filename_as_title)
            self.page_title_input.setReadOnly(existing_reels.use_filename_as_title)
            self.jitter_checkbox.setChecked(existing_reels.jitter_enabled)
            self.jitter_percent_spin.setValue(existing_reels.jitter_percent)
            sort_index = {'name': 0, 'random': 1, 'date_created': 2, 'date_modified': 3}.get(existing_reels.sort_by, 0)
            self.sort_by_combo.setCurrentIndex(sort_index)
            # تحميل إعدادات نظام الجدولة
            if getattr(existing_reels, 'use_smart_schedule', False):
                self.smart_schedule_radio.setChecked(True)
                template_id = getattr(existing_reels, 'template_id', None)
                if template_id:
                    for i in range(self.template_combo.count()):
                        if self.template_combo.itemData(i) == template_id:
                            self.template_combo.setCurrentIndex(i)
                            break
            else:
                self.interval_radio.setChecked(True)
            # تحميل إعدادات العلامة المائية
            self.job_watermark_checkbox.setChecked(existing_reels.watermark_enabled)
            if existing_reels.watermark_path:
                self.job_watermark_path_label.setText(existing_reels.watermark_path)
                self.job_watermark_path_label.setStyleSheet('')
            else:
                self.job_watermark_path_label.setText('لم يتم اختيار شعار')
                self.job_watermark_path_label.setStyleSheet('color: gray;')
            positions = {'top_left': 0, 'top_right': 1, 'bottom_left': 2, 'bottom_right': 3, 'center': 4}
            self.job_watermark_position_combo.setCurrentIndex(positions.get(existing_reels.watermark_position, 3))
            self.job_watermark_opacity_slider.setValue(int(existing_reels.watermark_opacity * 100))
            self.job_watermark_size_slider.setValue(int(existing_reels.watermark_scale * 100))
        elif existing_story:
            self.job_type_combo.setCurrentIndex(1)  # ستوري
            self.folder_btn.setText(existing_story.folder if existing_story.folder else 'اختر مجلد الستوري')
            val, unit = seconds_to_value_unit(existing_story.interval_seconds)
            self.interval_value_spin.setValue(val)
            idx = self.interval_unit_combo.findText(unit)
            if idx >= 0:
                self.interval_unit_combo.setCurrentIndex(idx)
            sort_index = {'name': 0, 'random': 1, 'date_created': 2, 'date_modified': 3}.get(existing_story.sort_by, 0)
            self.sort_by_combo.setCurrentIndex(sort_index)
            self.story_panel.set_stories_per_schedule(existing_story.stories_per_schedule)
            # تحميل إعدادات نظام الجدولة
            if getattr(existing_story, 'use_smart_schedule', False):
                self.smart_schedule_radio.setChecked(True)
                template_id = getattr(existing_story, 'template_id', None)
                if template_id:
                    for i in range(self.template_combo.count()):
                        if self.template_combo.itemData(i) == template_id:
                            self.template_combo.setCurrentIndex(i)
                            break
            else:
                self.interval_radio.setChecked(True)
            # تحميل إعدادات الحماية من الحظر
            self.story_panel.set_anti_ban_enabled(existing_story.anti_ban_enabled)
            # تحميل قيم التأخير العشوائي
            self.story_panel.set_random_delay_min(existing_story.random_delay_min if existing_story.random_delay_min > 0 else DEFAULT_RANDOM_DELAY_MIN)
            self.story_panel.set_random_delay_max(existing_story.random_delay_max if existing_story.random_delay_max > 0 else DEFAULT_RANDOM_DELAY_MAX)
        else:
            self.folder_btn.setText('اختر مجلد الفيديوهات')
            self.interval_value_spin.setValue(3)
            self.interval_unit_combo.setCurrentIndex(0)
            self.page_title_input.setText('{filename}')
            self.page_desc_input.setText('')
            self.use_filename_checkbox.setChecked(False)
            self.page_title_input.setReadOnly(False)
            self.jitter_checkbox.setChecked(False)
            self.jitter_percent_spin.setValue(10)
            self.sort_by_combo.setCurrentIndex(0)
            self.story_panel.set_stories_per_schedule(DEFAULT_STORIES_PER_SCHEDULE)
            # إعادة تعيين نظام الجدولة للافتراضي
            self.interval_radio.setChecked(True)
            # إعادة تعيين العلامة المائية للقيم الافتراضية
            self.job_watermark_checkbox.setChecked(False)
            self.job_watermark_path_label.setText('لم يتم اختيار شعار')
            self.job_watermark_path_label.setStyleSheet('color: gray;')
            self.job_watermark_position_combo.setCurrentIndex(3)
            self.job_watermark_opacity_slider.setValue(80)
            self.job_watermark_size_slider.setValue(15)  # 15% افتراضي
            # إعادة تعيين إعدادات الستوري
            self.story_panel.reset_to_defaults()

        # تطبيق تغيير نوع المحتوى
        self._on_job_type_changed(self.job_type_combo.currentIndex())

    def choose_folder(self):
        dlg = QFileDialog(self, 'اختر مجلد الفيديوهات')
        dlg.setFileMode(QFileDialog.Directory)
        if dlg.exec():
            folder = dlg.selectedFiles()[0]
            self.folder_btn.setText(folder)

    def _value_unit_to_seconds(self, v: int, unit: str) -> int:
        return v * 3600 if unit == 'ساعات' else v * 60 if unit == 'دقائق' else v

    def add_update_job(self):
        # Check if we're editing an existing job
        editing_job = getattr(self, '_editing_job', None)

        # الحصول على الصفحة المختارة من pages_panel
        selected_page = self.pages_panel.get_selected_page()
        
        if not selected_page:
            # If editing, we can use the job's page_id and app_name
            if not editing_job:
                QMessageBox.warning(self, 'اختيار مطلوب', 'اختر صفحة أولاً')
                return

        # Get page info from selected item or from editing job
        if selected_page and not editing_job:
            pid = selected_page.get('id')
            app_name = selected_page.get('_app_name', '') or selected_page.get('app_name', '')
            page_token = selected_page.get('access_token')
        elif editing_job:
            # Use info from the job being edited
            pid = editing_job.page_id
            app_name = getattr(editing_job, 'app_name', '')
            page_token = getattr(editing_job, 'page_access_token', None)
            # Try to get updated token from selected page if available
            if selected_page:
                page_token = selected_page.get('access_token', page_token)
        else:
            QMessageBox.warning(self, 'اختيار مطلوب', 'اختر صفحة أولاً')
            return

        job_key = make_job_key(pid, app_name)  # إنشاء المفتاح المركب
        folder = self.folder_btn.text()

        # التحقق من المجلد
        job_type_index = self.job_type_combo.currentIndex()
        is_story_mode = (job_type_index == 1)
        is_reels_mode = (job_type_index == 2)

        if is_story_mode:
            folder_text = 'اختر مجلد الستوري'
        elif is_reels_mode:
            folder_text = 'اختر مجلد الريلز'
        else:
            folder_text = 'اختر مجلد الفيديوهات'

        if folder == folder_text or folder.startswith('📁 اختر') or not folder:
            QMessageBox.warning(self, 'المجلد', 'حدد المجلد')
            return

        # التحقق من نظام الجدولة
        use_smart_schedule = self.smart_schedule_radio.isChecked()
        template_id = None

        if use_smart_schedule:
            template_id = self.template_combo.currentData()
            if template_id is None:
                QMessageBox.warning(self, 'تحذير', '⚠️ يجب اختيار قالب للجدولة الذكية\nأو استخدم نظام الفاصل الزمني')
                return

        interval_secs = self._value_unit_to_seconds(self.interval_value_spin.value(), self.interval_unit_combo.currentText())

        # Get page name - either from selected item or from editing job
        editing_job_page_name = getattr(editing_job, 'page_name', '') if editing_job else ''
        if selected_page:
            page_name = selected_page.get('name', editing_job_page_name)
        else:
            page_name = editing_job_page_name

        sort_index = self.sort_by_combo.currentIndex()
        sort_by = ['name', 'random', 'date_created', 'date_modified'][sort_index]

        if is_story_mode:
            # إنشاء/تحديث وظيفة ستوري
            stories_per_schedule = self.story_panel.get_stories_per_schedule()
            anti_ban_enabled = self.story_panel.get_anti_ban_enabled()

            # التأخير العشوائي فقط (Requirement 4)
            random_delay_min = self.story_panel.get_random_delay_min()
            random_delay_max = self.story_panel.get_random_delay_max()

            story_job = self.story_jobs_map.get(job_key)
            if story_job:
                story_job.folder = folder
                story_job.interval_seconds = interval_secs
                story_job.page_name = page_name
                story_job.app_name = app_name  # تحديث اسم التطبيق
                story_job.sort_by = sort_by
                story_job.stories_per_schedule = stories_per_schedule
                story_job.anti_ban_enabled = anti_ban_enabled
                story_job.random_delay_min = random_delay_min
                story_job.random_delay_max = random_delay_max
                story_job.use_smart_schedule = use_smart_schedule
                story_job.template_id = template_id
                if page_token:
                    story_job.page_access_token = page_token
            else:
                story_job = StoryJob(pid, page_name, folder, interval_secs, page_token,
                                    stories_per_schedule=stories_per_schedule, sort_by=sort_by,
                                    anti_ban_enabled=anti_ban_enabled,
                                    random_delay_min=random_delay_min,
                                    random_delay_max=random_delay_max,
                                    use_smart_schedule=use_smart_schedule,
                                    template_id=template_id,
                                    app_name=app_name)
                self.story_jobs_map[job_key] = story_job
            self._log_append('تمت إضافة/تحديث وظيفة الستوري.')
        elif is_reels_mode:
            # إنشاء/تحديث وظيفة ريلز
            title_tmpl = self.page_title_input.text().strip() or "{filename}"
            desc_tmpl = self.page_desc_input.text().strip() or ""
            use_filename = self.use_filename_checkbox.isChecked()
            jitter_enabled = self.jitter_checkbox.isChecked()
            jitter_percent = self.jitter_percent_spin.value()

            # إعدادات العلامة المائية لهذه المهمة
            watermark_enabled = self.job_watermark_checkbox.isChecked()
            watermark_path = self.job_watermark_path_label.text()
            if watermark_path == 'لم يتم اختيار شعار':
                watermark_path = ''
            positions = ['top_left', 'top_right', 'bottom_left', 'bottom_right', 'center']
            watermark_position = positions[self.job_watermark_position_combo.currentIndex()]
            watermark_opacity = self.job_watermark_opacity_slider.value() / 100.0
            watermark_scale = self.job_watermark_size_slider.value() / 100.0

            reels_job = self.reels_jobs_map.get(job_key)
            if reels_job:
                reels_job.folder = folder
                reels_job.interval_seconds = interval_secs
                reels_job.page_name = page_name
                reels_job.app_name = app_name  # تحديث اسم التطبيق
                reels_job.title_template = title_tmpl
                reels_job.description_template = desc_tmpl
                reels_job.use_filename_as_title = use_filename
                reels_job.jitter_enabled = jitter_enabled
                reels_job.jitter_percent = jitter_percent
                reels_job.sort_by = sort_by
                # تحديث إعدادات العلامة المائية
                reels_job.watermark_enabled = watermark_enabled
                reels_job.watermark_path = watermark_path
                reels_job.watermark_position = watermark_position
                reels_job.watermark_opacity = watermark_opacity
                reels_job.watermark_scale = watermark_scale
                reels_job.use_smart_schedule = use_smart_schedule
                reels_job.template_id = template_id
                if page_token:
                    reels_job.page_access_token = page_token
                # تحديث الإحداثيات المخصصة (من السحب بالماوس)
                reels_job.watermark_x = getattr(self, '_current_watermark_x', None)
                reels_job.watermark_y = getattr(self, '_current_watermark_y', None)
            else:
                reels_job = ReelsJob(pid, page_name, folder, interval_secs, page_token,
                              title_tmpl, desc_tmpl, CHUNK_SIZE_DEFAULT, use_filename_as_title=use_filename,
                              sort_by=sort_by, jitter_enabled=jitter_enabled, jitter_percent=jitter_percent,
                              watermark_enabled=watermark_enabled, watermark_path=watermark_path,
                              watermark_position=watermark_position, watermark_opacity=watermark_opacity,
                              watermark_scale=watermark_scale, app_name=app_name)
                # إضافة الإحداثيات المخصصة للوظيفة الجديدة
                reels_job.watermark_x = getattr(self, '_current_watermark_x', None)
                reels_job.watermark_y = getattr(self, '_current_watermark_y', None)
                reels_job.use_smart_schedule = use_smart_schedule
                reels_job.template_id = template_id
                self.reels_jobs_map[job_key] = reels_job
            self._log_append('تمت إضافة/تحديث وظيفة الريلز.')
        else:
            # إنشاء/تحديث وظيفة فيديو
            title_tmpl = self.page_title_input.text().strip() or "{filename}"
            desc_tmpl = self.page_desc_input.text().strip() or ""
            use_filename = self.use_filename_checkbox.isChecked()
            jitter_enabled = self.jitter_checkbox.isChecked()
            jitter_percent = self.jitter_percent_spin.value()

            # إعدادات العلامة المائية لهذه المهمة
            watermark_enabled = self.job_watermark_checkbox.isChecked()
            watermark_path = self.job_watermark_path_label.text()
            if watermark_path == 'لم يتم اختيار شعار':
                watermark_path = ''
            positions = ['top_left', 'top_right', 'bottom_left', 'bottom_right', 'center']
            watermark_position = positions[self.job_watermark_position_combo.currentIndex()]
            watermark_opacity = self.job_watermark_opacity_slider.value() / 100.0
            watermark_scale = self.job_watermark_size_slider.value() / 100.0

            job = self.jobs_map.get(job_key)
            if job:
                job.folder = folder
                job.interval_seconds = interval_secs
                job.page_name = page_name
                job.app_name = app_name  # تحديث اسم التطبيق
                job.title_template = title_tmpl
                job.description_template = desc_tmpl
                job.use_filename_as_title = use_filename
                job.jitter_enabled = jitter_enabled
                job.jitter_percent = jitter_percent
                job.sort_by = sort_by
                # تحديث إعدادات العلامة المائية
                job.watermark_enabled = watermark_enabled
                job.watermark_path = watermark_path
                job.watermark_position = watermark_position
                job.watermark_opacity = watermark_opacity
                job.watermark_scale = watermark_scale
                # تحديث الإحداثيات المخصصة (من السحب بالماوس)
                job.watermark_x = getattr(self, '_current_watermark_x', None)
                job.watermark_y = getattr(self, '_current_watermark_y', None)
                job.use_smart_schedule = use_smart_schedule
                job.template_id = template_id
                if page_token:
                    job.page_access_token = page_token
            else:
                job = PageJob(pid, page_name, folder, interval_secs, page_token,
                              title_tmpl, desc_tmpl, CHUNK_SIZE_DEFAULT, use_filename_as_title=use_filename,
                              sort_by=sort_by, jitter_enabled=jitter_enabled, jitter_percent=jitter_percent,
                              watermark_enabled=watermark_enabled, watermark_path=watermark_path,
                              watermark_position=watermark_position, watermark_opacity=watermark_opacity,
                              watermark_scale=watermark_scale, app_name=app_name)
                # إضافة الإحداثيات المخصصة للوظيفة الجديدة
                job.watermark_x = getattr(self, '_current_watermark_x', None)
                job.watermark_y = getattr(self, '_current_watermark_y', None)
                job.use_smart_schedule = use_smart_schedule
                job.template_id = template_id
                self.jobs_map[job_key] = job
            self._log_append('تمت إضافة/تحديث وظيفة الفيديو.')

        # Clear the editing state after successful add/update
        self._editing_job = None

        self.refresh_jobs_list()
        self._save_jobs()

    def _on_job_schedule_changed(self, page_id: str, is_scheduled: bool):
        """معالج تغيير حالة جدولة الوظيفة من الخيط."""
        # تحديث القائمة
        self.refresh_jobs_list()
        self._save_jobs()

    def refresh_jobs_list(self):
        """تحديث جدول الوظائف بناءً على الوضع الحالي (فيديو/ستوري/ريلز)."""
        # تفويض المهمة لمكون SchedulerUI
        # Delegate to SchedulerUI component
        self.scheduler_ui.set_jobs_maps(self.jobs_map, self.story_jobs_map, self.reels_jobs_map)
        self.scheduler_ui.set_mode(self.current_mode)

    def _add_job_to_table(self, job):
        """إضافة وظيفة إلى جدول الوظائف."""
        # استخدام الدالة المستخرجة في JobsTable عبر SchedulerUI
        self.jobs_table.add_job(job)

    def _update_all_job_countdowns(self):
        """تحديث حالات الجدولة والوقت المتبقي في الجدول."""
        # تفويض المهمة لمكون SchedulerUI
        # Delegate to SchedulerUI component
        self.scheduler_ui.update_all_countdowns()

    def _delete_job_by_type(self, job):
        """حذف وظيفة من القائمة المناسبة بناءً على نوعها."""
        # تفويض المهمة لمكون SchedulerUI
        # Delegate to SchedulerUI component
        return self.scheduler_ui._delete_job_by_type(job)

    def _on_job_scheduled(self, job):
        """
        معالج إشارة جدولة وظيفة - Handler for job scheduled signal
        يتم استدعاؤه عندما يتم جدولة وظيفة من SchedulerUI
        """
        # إذا كان المجدول متوقفاً نشغّله
        if not (self.scheduler_thread and self.scheduler_thread.is_alive()):
            self.start_scheduler()
    
    def _on_job_cancelled(self, job):
        """
        معالج إشارة إلغاء جدولة وظيفة - Handler for job cancelled signal
        يتم استدعاؤه عندما يتم إلغاء جدولة وظيفة من SchedulerUI
        """
        pass  # لا حاجة لإجراء إضافي
    
    def _on_scheduler_ui_start_requested(self):
        """
        معالج إشارة طلب بدء المجدول - Handler for scheduler start requested signal
        يتم استدعاؤه عندما يطلب SchedulerUI بدء المجدول
        """
        if not (self.scheduler_thread and self.scheduler_thread.is_alive()):
            self.start_scheduler()

    def remove_job(self):
        """حذف الوظيفة المحددة من الجدول - تفويض لـ SchedulerUI."""
        # Delegate to SchedulerUI component
        self.scheduler_ui.remove_job()

    def _get_selected_job_from_table(self):
        """الحصول على الوظيفة المحددة من الجدول - تفويض لـ SchedulerUI."""
        # Delegate to SchedulerUI component  
        return self.scheduler_ui._get_selected_job_from_table()

    def run_selected_job_now(self):
        """تشغيل فوري للوظيفة المحددة - يدعم الفيديو والستوري والريلز (Requirement 6)."""
        job = self._get_selected_job_from_table()
        if not job:
            QMessageBox.warning(self, 'اختيار مطلوب', 'اختر وظيفة أولاً')
            return

        # التفريق بين نوع الوظيفة
        if isinstance(job, StoryJob):
            self._run_story_job_now(job)
        elif isinstance(job, ReelsJob):
            self._run_reels_job_now(job)
        else:
            self._run_video_job_now(job)

    def _run_story_job_now(self, job: StoryJob):
        """رفع ستوري فوري للوظيفة المحددة باستخدام نظام Batch Requests."""
        try:
            folder = Path(job.folder)
            if not folder.exists():
                QMessageBox.warning(self, 'مجلد غير موجود', 'المجلد غير موجود')
                return

            # استخدام STORY_EXTENSIONS بدلاً من VIDEO_EXTENSIONS
            files = get_story_files(str(folder), job.sort_by)
            if not files:
                QMessageBox.warning(self, 'لا يوجد ملفات', 'لا توجد ملفات ستوري (صور/فيديو) في المجلد')
                return

            token = job.page_access_token or self.token_getter()
            if not token:
                QMessageBox.warning(self, 'توكن مفقود', 'لا يوجد توكن')
                return

            self._log_append(f'📱 رفع ستوري فوري: {job.page_name}')

            should_move = self.auto_move_uploaded

            # تفعيل زر الإيقاف
            self._on_upload_started()

            def worker():
                # دالة تسجيل آمنة للخيوط - تستخدم Signal بدلاً من الاستدعاء المباشر
                def thread_safe_log(msg):
                    self.ui_signals.log_signal.emit(msg)

                try:
                    if not job.lock.acquire(blocking=False):
                        thread_safe_log('رفع آخر قيد التنفيذ لهذه الوظيفة.')
                        self.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')
                        return
                    try:
                        self.ui_signals.clear_progress_signal.emit()

                        # استخدام safe_process_story_job مع دعم Batch Requests
                        result = safe_process_story_job(
                            job=job,
                            token=token,
                            log_fn=thread_safe_log,
                            auto_move=should_move,
                            stop_event=self._upload_stop_requested
                        )

                        # عرض ملخص النتائج
                        if result.get('success'):
                            thread_safe_log(f'✅ تم رفع {result.get("files_uploaded", 0)} ستوري بنجاح')
                            if result.get('saved_calls', 0) > 0:
                                thread_safe_log(f'📦 تم توفير {result.get("saved_calls", 0)} طلب API باستخدام Batch')
                        else:
                            thread_safe_log(f'⚠️ فشل: {result.get("error", "خطأ غير معروف")}')

                        if result.get('files_failed', 0) > 0:
                            thread_safe_log(f'❌ فشل رفع {result.get("files_failed", 0)} ملف')

                        job.reset_next_run_timestamp()
                        self._save_jobs()

                        # تنظيف الذاكرة
                        gc.collect()

                    except Exception as e:
                        thread_safe_log(f'❌ خطأ: {e}')
                        log_error_to_file(e, 'Story job error')
                    finally:
                        try:
                            job.lock.release()
                        except Exception:
                            pass
                except Exception as e:
                    thread_safe_log(f'❌ خطأ غير متوقع: {e}')
                    log_error_to_file(e, 'Unexpected story error')
                finally:
                    # إخفاء زر الإيقاف
                    self.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self._log_append(f'❌ خطأ: {e}')
            self._on_upload_finished()
            log_error_to_file(e, 'run_story_job_now error')

    def _run_video_job_now(self, job: PageJob):
        """رفع فيديو فوري للوظيفة المحددة (Requirement 6 - مع دعم الإيقاف)."""
        try:
            folder = Path(job.folder)
            if not folder.exists():
                QMessageBox.warning(self, 'مجلد غير موجود', 'المجلد غير موجود')
                return
            files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS])
            if not files:
                QMessageBox.warning(self, 'لا يوجد ملفات', 'لا فيديوهات في المجلد')
                return
            idx = job.next_index % len(files)
            video_path = str(files[idx])
            token = job.page_access_token or self.token_getter()
            if not token:
                QMessageBox.warning(self, 'توكن مفقود', 'لا يوجد توكن')
                return
            self._log_append(f'رفع فوري للوظيفة: {job.page_name}')

            # حفظ حالة نقل الفيديوهات محلياً للاستخدام داخل الـ worker
            should_move = self.auto_move_uploaded

            # تفعيل زر الإيقاف (Requirement 6)
            self._on_upload_started()

            # تتبع الوظيفة الحالية للإيقاف السريع
            self._current_uploading_job = job

            def worker():
                # دالة تسجيل آمنة للخيوط - تستخدم Signal بدلاً من الاستدعاء المباشر
                def thread_safe_log(msg):
                    self.ui_signals.log_signal.emit(msg)

                try:
                    if not job.lock.acquire(blocking=False):
                        thread_safe_log('رفع آخر قيد التنفيذ لهذه الوظيفة.')
                        self.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')
                        return
                    try:
                        # التحقق من طلب الإيقاف قبل البدء (Requirement 6)
                        if self._upload_stop_requested.is_set():
                            thread_safe_log('⏹️ تم إلغاء الرفع قبل البدء')
                            return

                        self.ui_signals.clear_progress_signal.emit()
                        status, body = upload_video_once(job, video_path, token, self.ui_signals,
                                                         job.title_template, job.description_template, thread_safe_log)

                        # التحقق من نجاح الرفع ونقل الفيديو إلى مجلد Uploaded
                        upload_success = is_upload_successful(status, body)
                        if upload_success:
                            thread_safe_log('اكتمل الرفع، إعادة ضبط العدّاد')
                            # بعد النجاح نضبط next_run_timestamp = الآن + الفاصل الزمني
                            job.reset_next_run_timestamp()
                            if should_move:
                                move_video_to_uploaded_folder(video_path, thread_safe_log)

                        if status in (400, 403) and isinstance(body, dict):
                            err = body.get('error', {})
                            msg = err.get('message', '')
                            code = err.get('code', '')
                            if msg and ('permission' in msg.lower() or code == 100):
                                thread_safe_log('تحذير: صلاحيات غير كافية.')
                    except Exception as e:
                        thread_safe_log(f'❌ خطأ: {e}')
                        log_error_to_file(e, 'Video job error')
                    finally:
                        try:
                            job.lock.release()
                        except Exception:
                            pass
                except Exception as e:
                    thread_safe_log(f'❌ خطأ غير متوقع: {e}')
                    log_error_to_file(e, 'Unexpected video error')
                finally:
                    # إخفاء زر الإيقاف (Requirement 6)
                    self.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self._log_append(f'❌ خطأ: {e}')
            self._on_upload_finished()
            log_error_to_file(e, 'run_video_job_now error')

    def _run_reels_job_now(self, job: ReelsJob):
        """رفع ريلز فوري للوظيفة المحددة (Requirement 6 - مع دعم الإيقاف)."""
        try:
            folder = Path(job.folder)
            if not folder.exists():
                QMessageBox.warning(self, 'مجلد غير موجود', 'المجلد غير موجود')
                return
            files = get_reels_files(str(folder), job.sort_by)
            if not files:
                QMessageBox.warning(self, 'لا يوجد ملفات', 'لا ريلز في المجلد')
                return
            idx = job.next_index % len(files)
            video_path = str(files[idx])

            # Problem 1: فحص مدة الفيديو قبل البدء بالرفع
            is_valid_duration, duration, error_msg = check_reels_duration(video_path)
            if not is_valid_duration:
                QMessageBox.warning(
                    self,
                    '⚠️ مدة الفيديو تتجاوز الحد المسموح',
                    f'{error_msg}\n\nالملف: {Path(video_path).name}'
                )
                self._log_append(f'⚠️ تم رفض الفيديو: المدة {duration:.1f} ثانية تتجاوز الحد الأقصى (60 ثانية)')
                return

            token = job.page_access_token or self.token_getter()
            if not token:
                QMessageBox.warning(self, 'توكن مفقود', 'لا يوجد توكن')
                return
            self._log_append(f'🎬 رفع ريلز فوري: {job.page_name}')
            if duration > 0:
                self._log_append(f'📊 مدة الفيديو: {duration:.1f} ثانية')

            # حفظ حالة نقل الفيديوهات محلياً للاستخدام داخل الـ worker
            should_move = self.auto_move_uploaded

            # تفعيل زر الإيقاف (Requirement 6)
            self._on_upload_started()

            # إنشاء مرجع للـ stop event للاستخدام في العامل
            stop_event = self._upload_stop_requested

            def worker():
                # دالة تسجيل آمنة للخيوط - تستخدم Signal بدلاً من الاستدعاء المباشر
                def thread_safe_log(msg):
                    self.ui_signals.log_signal.emit(msg)

                # Problem 3: دالة تحديث شريط التقدم
                def progress_callback(percent):
                    # التحقق من طلب الإيقاف أثناء تحديث التقدم
                    if stop_event.is_set():
                        return
                    self.ui_signals.progress_signal.emit(int(percent), f'رفع الريلز {int(percent)}%')

                try:
                    if not job.lock.acquire(blocking=False):
                        thread_safe_log('رفع آخر قيد التنفيذ لهذه الوظيفة.')
                        self.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')
                        return
                    try:
                        # التحقق من طلب الإيقاف قبل البدء (Requirement 6)
                        if stop_event.is_set():
                            thread_safe_log('⏹️ تم إلغاء الرفع قبل البدء')
                            return

                        self.ui_signals.clear_progress_signal.emit()

                        # استخدام دالة رفع الريلز
                        from controllers.reels_controller import upload_reels_with_retry, is_reels_upload_successful

                        # إعداد العنوان والوصف باستخدام المتغيرات الجديدة
                        title = apply_title_placeholders(job.title_template, Path(video_path).name) if job.title_template else ''
                        description = apply_title_placeholders(job.description_template, Path(video_path).name) if job.description_template else ''

                        # Problem 2 & 3: تمرير progress_callback و stop_event
                        status, body = upload_reels_with_retry(
                            page_id=job.page_id,
                            video_path=video_path,
                            token=token,
                            description=description,
                            title=title,
                            log_fn=thread_safe_log,
                            progress_callback=progress_callback,
                            stop_event=stop_event
                        )

                        # التحقق من إيقاف العملية
                        if stop_event.is_set():
                            thread_safe_log('⏹️ تم إيقاف الرفع بنجاح')
                            return

                        # التحقق من نجاح الرفع
                        upload_success = is_reels_upload_successful(status, body)
                        if upload_success:
                            thread_safe_log('✅ اكتمل رفع الريلز')
                            job.next_index = (job.next_index + 1) % len(files)
                            job.reset_next_run_timestamp()
                            if should_move:
                                move_video_to_uploaded_folder(video_path, thread_safe_log)
                        else:
                            thread_safe_log(f'❌ فشل رفع الريلز')

                    except Exception as e:
                        thread_safe_log(f'❌ خطأ: {e}')
                        log_error_to_file(e, 'Reels job error')
                    finally:
                        try:
                            job.lock.release()
                        except Exception:
                            pass
                except Exception as e:
                    thread_safe_log(f'❌ خطأ غير متوقع: {e}')
                    log_error_to_file(e, 'Unexpected reels error')
                finally:
                    # إخفاء زر الإيقاف (Requirement 6)
                    self.ui_signals.log_signal.emit('__UPLOAD_FINISHED__')

            threading.Thread(target=worker, daemon=True).start()
        except Exception as e:
            self._log_append(f'❌ خطأ: {e}')
            self._on_upload_finished()
            log_error_to_file(e, 'run_reels_job_now error')

    def start_selected_job(self):
        """تشغيل الجدولة للوظيفة المحددة - تفويض لـ SchedulerUI."""
        # Delegate to SchedulerUI component
        self.scheduler_ui.start_selected_job()

    def stop_selected_job(self):
        """إيقاف الجدولة للوظيفة المحددة - تفويض لـ SchedulerUI."""
        # Delegate to SchedulerUI component
        self.scheduler_ui.stop_selected_job()


        # التحقق من وجود وظائف (فيديو أو ستوري أو ريلز)
        if not self.jobs_map and not self.story_jobs_map and not self.reels_jobs_map:
            QMessageBox.warning(self, 'لا وظائف', 'أضف وظيفة واحدة على الأقل.')
            return

        # التحقق من وجود توكن
        video_tokens = any(j.page_access_token for j in self.jobs_map.values())
        story_tokens = any(j.page_access_token for j in self.story_jobs_map.values())
        reels_tokens = any(j.page_access_token for j in self.reels_jobs_map.values())
        any_token = video_tokens or story_tokens or reels_tokens or bool(self.token_getter())
        if not any_token:
            QMessageBox.warning(self, 'توكن مفقود', 'أدخل توكن صالح.')
            return
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            QMessageBox.information(self, 'قيد التشغيل', 'المجدول يعمل.')
            return

        # مسح جميع أحداث الإيقاف (clear all stop events)
        self.video_scheduler_stop.clear()
        self.story_scheduler_stop.clear()
        self.reels_scheduler_stop.clear()

        max_workers = self.concurrent_spin.value()

        # تشغيل مجدول الفيديوهات إذا كانت هناك وظائف فيديو
        if self.jobs_map:
            self._log_append('🎬 بدء مجدول الفيديوهات...')
            self.scheduler_thread = SchedulerThread(
                self.jobs_map, self.token_getter, self.ui_signals, self.video_scheduler_stop,
                max_workers=max_workers,
                auto_move_getter=lambda: self.auto_move_uploaded,
                validate_videos_getter=lambda: self.validate_videos,
                internet_check_getter=lambda: self.internet_check_enabled
            )
            self.scheduler_thread.start()

        # تشغيل مجدول الستوري إذا كانت هناك وظائف ستوري
        if self.story_jobs_map:
            self._log_append('📸 بدء مجدول الستوري...')
            self.story_scheduler_thread = StorySchedulerThread(
                self.story_jobs_map, self.token_getter, self.ui_signals, self.story_scheduler_stop,
                max_workers=max_workers,
                auto_move_getter=lambda: self.auto_move_uploaded,
                internet_check_getter=lambda: self.internet_check_enabled
            )
            self.story_scheduler_thread.start()

        # تشغيل مجدول الريلز إذا كانت هناك وظائف ريلز (Problem 2 fix)
        if self.reels_jobs_map:
            self._log_append('🎬 بدء مجدول الريلز...')
            self.reels_scheduler_thread = ReelsSchedulerThread(
                self.reels_jobs_map, self.token_getter, self.ui_signals, self.reels_scheduler_stop,
                max_workers=max_workers,
                auto_move_getter=lambda: self.auto_move_uploaded,
                internet_check_getter=lambda: self.internet_check_enabled
            )
            self.reels_scheduler_thread.start()

        # الرسالة ستظهر من SchedulerThread.run()
        self.countdown_timer.start()
        self.refresh_jobs_list()

    def stop_scheduler(self):
        stopped_any = False
        stopped_types = []

        # إيقاف مجدول الفيديوهات
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self._log_append('⏹️ إيقاف مجدول الفيديوهات...')
            self.video_scheduler_stop.set()
            self.scheduler_thread.join(timeout=5)
            stopped_any = True
            stopped_types.append('الفيديوهات')

        # إيقاف مجدول الستوري
        if hasattr(self, 'story_scheduler_thread') and self.story_scheduler_thread and self.story_scheduler_thread.is_alive():
            self._log_append('⏹️ إيقاف مجدول الستوري...')
            self.story_scheduler_stop.set()
            self.story_scheduler_thread.join(timeout=5)
            stopped_any = True
            stopped_types.append('الستوري')

        # إيقاف مجدول الريلز (للمستقبل)
        if hasattr(self, 'reels_scheduler_thread') and self.reels_scheduler_thread and self.reels_scheduler_thread.is_alive():
            self._log_append('⏹️ إيقاف مجدول الريلز...')
            self.reels_scheduler_stop.set()
            self.reels_scheduler_thread.join(timeout=5)
            stopped_any = True
            stopped_types.append('الريلز')

        if stopped_any:
            types_str = ' و '.join(stopped_types)
            self._log_append(f'✅ تم إيقاف مجدول {types_str}.')

        self.countdown_timer.stop()
        self.refresh_jobs_list()

    def _save_jobs(self):
        """حفظ وظائف الفيديو والستوري والريلز."""
        jobs_file = _get_jobs_file()

        # جمع وظائف الفيديو
        video_jobs = [j.to_dict() for j in self.jobs_map.values()]

        # جمع وظائف الستوري
        story_jobs = [j.to_dict() for j in self.story_jobs_map.values()]

        # جمع وظائف الريلز
        reels_jobs = [j.to_dict() for j in self.reels_jobs_map.values()]

        data = {
            'video_jobs': video_jobs,
            'story_jobs': story_jobs,
            'reels_jobs': reels_jobs
        }

        try:
            with open(jobs_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log_append('تم حفظ الوظائف.')
        except Exception as e:
            self._log_append(f'فشل حفظ الوظائف: {e}')

    def _is_valid_job_data(self, d) -> bool:
        """التحقق من صحة بيانات الوظيفة."""
        return isinstance(d, dict) and 'page_id' in d

    def _load_jobs(self):
        """تحميل وظائف الفيديو والستوري والريلز."""
        jobs_file = _get_jobs_file()
        if jobs_file.exists():
            try:
                with open(jobs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # دعم التوافق مع الملفات القديمة
                if isinstance(data, list):
                    # ملف قديم - قائمة وظائف فيديو فقط
                    self.jobs_map = {}
                    self.story_jobs_map = {}
                    self.reels_jobs_map = {}
                    for d in data:
                        try:
                            if not self._is_valid_job_data(d):
                                continue  # تخطي البيانات غير الصالحة
                            job = PageJob.from_dict(d)
                            saved_enc = getattr(self, '_saved_page_tokens_buffer', {}).get(job.page_id)
                            if saved_enc and not job.page_access_token:
                                job.page_access_token = saved_enc
                            job_key = get_job_key(job)
                            self.jobs_map[job_key] = job
                        except Exception as job_err:
                            self._log_append(f'تخطي وظيفة غير صالحة: {job_err}')
                else:
                    # ملف جديد - قاموس يحتوي على video_jobs و story_jobs و reels_jobs
                    self.jobs_map = {}
                    self.story_jobs_map = {}
                    self.reels_jobs_map = {}

                    # تحميل وظائف الفيديو
                    video_jobs = data.get('video_jobs', [])
                    if isinstance(video_jobs, list):
                        for d in video_jobs:
                            try:
                                if not self._is_valid_job_data(d):
                                    continue  # تخطي البيانات غير الصالحة
                                job = PageJob.from_dict(d)
                                saved_enc = getattr(self, '_saved_page_tokens_buffer', {}).get(job.page_id)
                                if saved_enc and not job.page_access_token:
                                    job.page_access_token = saved_enc
                                job_key = get_job_key(job)
                                self.jobs_map[job_key] = job
                            except Exception as job_err:
                                self._log_append(f'تخطي وظيفة فيديو غير صالحة: {job_err}')

                    # تحميل وظائف الستوري
                    story_jobs = data.get('story_jobs', [])
                    if isinstance(story_jobs, list):
                        for d in story_jobs:
                            try:
                                if not self._is_valid_job_data(d):
                                    continue  # تخطي البيانات غير الصالحة
                                story_job = StoryJob.from_dict(d)
                                saved_enc = getattr(self, '_saved_page_tokens_buffer', {}).get(story_job.page_id)
                                if saved_enc and not story_job.page_access_token:
                                    story_job.page_access_token = saved_enc
                                job_key = get_job_key(story_job)
                                self.story_jobs_map[job_key] = story_job
                            except Exception as job_err:
                                self._log_append(f'تخطي وظيفة ستوري غير صالحة: {job_err}')

                    # تحميل وظائف الريلز
                    reels_jobs = data.get('reels_jobs', [])
                    if isinstance(reels_jobs, list):
                        for d in reels_jobs:
                            try:
                                if not self._is_valid_job_data(d):
                                    continue  # تخطي البيانات غير الصالحة
                                reels_job = ReelsJob.from_dict(d)
                                saved_enc = getattr(self, '_saved_page_tokens_buffer', {}).get(reels_job.page_id)
                                if saved_enc and not reels_job.page_access_token:
                                    reels_job.page_access_token = saved_enc
                                job_key = get_job_key(reels_job)
                                self.reels_jobs_map[job_key] = reels_job
                            except Exception as job_err:
                                self._log_append(f'تخطي وظيفة ريلز غير صالحة: {job_err}')

                # إصلاح: إعادة ضبط الحالات والأوقات المتبقية بعد التحميل
                self._fix_job_states_after_load()

                self.refresh_jobs_list()
                self._log_append('تم تحميل الوظائف من الملف.')
            except json.JSONDecodeError as e:
                self._log_append(f'فشل تحليل ملف الوظائف: {e}')
            except Exception as e:
                self._log_append(f'فشل تحميل الوظائف: {e}')

    def _fix_job_states_after_load(self):
        """
        إصلاح حالات الوظائف بعد التحميل من الملف.

        يقوم بـ:
        1. إعادة حساب next_run_timestamp إذا كان في الماضي
        2. بدء الـ countdown timer إذا كانت هناك وظائف مجدولة
        """
        print("[Fix] بدء _fix_job_states_after_load")
        log_debug('[FixJobStates] بدء _fix_job_states_after_load')
        has_scheduled_jobs = False
        fixed_timestamps = 0
        current_time = time.time()

        # جمع جميع الوظائف من الأنواع الثلاثة بكفاءة
        from itertools import chain
        all_jobs = chain(self.jobs_map.values(), self.story_jobs_map.values(), self.reels_jobs_map.values())

        # فحص وإصلاح كل وظيفة
        for job in all_jobs:
            # التحقق من حالة الجدولة
            if job.is_scheduled:
                has_scheduled_jobs = True
                print(f"[Fix] وظيفة مجدولة: {job.page_name}")
                log_debug(f'[FixJobStates] وظيفة مجدولة: {job.page_name}')

                # قراءة ذرية واحدة للـ timestamp (تخزين مؤقت)
                next_run = job.next_run_timestamp
                if next_run < current_time:
                    # الوقت في الماضي - إعادة حسابه
                    job.reset_next_run_timestamp()
                    fixed_timestamps += 1
                    print(f"[Fix] إعادة حساب الوقت للوظيفة: {job.page_name}")
                    log_debug(f'[FixJobStates] إعادة حساب الوقت للوظيفة: {job.page_name}')

        print(f"[Fix] has_scheduled_jobs = {has_scheduled_jobs}")
        log_debug(f'[FixJobStates] has_scheduled_jobs = {has_scheduled_jobs}')

        # حفظ التغييرات إذا تم إصلاح أي أوقات
        if fixed_timestamps > 0:
            self._log_append(f'🔧 تم إصلاح {fixed_timestamps} وقت تشغيل في الماضي')
            self._save_jobs()

        # بدء الـ countdown timer إذا كانت هناك وظائف مجدولة ولم يكن يعمل بالفعل
        if has_scheduled_jobs:
            print(f"[Fix] countdown_timer موجود: {hasattr(self, 'countdown_timer') and self.countdown_timer is not None}")
            log_debug(f'[FixJobStates] countdown_timer موجود: {hasattr(self, "countdown_timer") and self.countdown_timer is not None}')
            if hasattr(self, 'countdown_timer') and self.countdown_timer:
                print(f"[Fix] countdown_timer.isActive() = {self.countdown_timer.isActive()}")
                log_debug(f'[FixJobStates] countdown_timer.isActive() = {self.countdown_timer.isActive()}')
                if not self.countdown_timer.isActive():
                    self.countdown_timer.start()  # يستخدم الفاصل الزمني المحدد مسبقاً (1000ms)
                    print("[Fix] تم بدء countdown_timer")
                    log_info('[FixJobStates] تم بدء countdown timer تلقائياً')
                else:
                    print("[Fix] countdown_timer يعمل بالفعل")
                    log_debug('[FixJobStates] countdown_timer يعمل بالفعل')
            else:
                print("[Fix] ERROR: countdown_timer غير موجود!")
                log_error('[FixJobStates] ERROR: countdown_timer غير موجود!')
        else:
            print("[Fix] لا توجد وظائف مجدولة")
            log_debug('[FixJobStates] لا توجد وظائف مجدولة')

    def _save_settings(self):
        settings_file = get_settings_file()
        # التوكن يتم إدارته الآن من خلال نظام إدارة التوكينات

        settings = {
            'theme': self.theme,
            'page_tokens_enc': {
                pid: simple_encrypt(job.page_access_token or "")
                for pid, job in self.jobs_map.items()
            },
            # إعداد نقل الفيديوهات تلقائياً بعد الرفع
            'auto_move_uploaded': self.auto_move_uploaded,
            # ساعات العمل
            'working_hours_enabled': self.working_hours_enabled,
            'working_hours_start': self.working_hours_start,
            'working_hours_end': self.working_hours_end,
            # العلامة المائية
            'watermark_enabled': self.watermark_enabled,
            'watermark_logo_path': self.watermark_logo_path,
            'watermark_position': self.watermark_position,
            'watermark_opacity': self.watermark_opacity,
            # التحقق من صحة الفيديو
            'validate_videos': self.validate_videos,
            # فحص الاتصال بالإنترنت
            'internet_check_enabled': self.internet_check_enabled,
            # إعدادات Telegram Bot
            'telegram_enabled': self.telegram_enabled,
            'telegram_bot_token_enc': simple_encrypt(self.telegram_bot_token),
            'telegram_chat_id': self.telegram_chat_id,
            'telegram_notify_success': self.telegram_notify_success,
            'telegram_notify_errors': self.telegram_notify_errors
        }
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            self._log_append('تم حفظ الإعدادات.')
        except Exception as e:
            self._log_append(f'فشل حفظ الإعدادات: {e}')

    def save_all(self):
        self._save_jobs()
        self._save_settings()

    # ==================== Schedule All / Unschedule All ====================

    def schedule_all_jobs(self):
        """جدولة جميع المهام المفعّلة - تفويض لـ SchedulerUI."""
        # Delegate to SchedulerUI component
        self.scheduler_ui.schedule_all_jobs()

    def unschedule_all_jobs(self):
        """إلغاء جدولة جميع المهام - تفويض لـ SchedulerUI."""
        # Delegate to SchedulerUI component
        self.scheduler_ui.unschedule_all_jobs()

    # ==================== Mode Tabs ====================

    def _on_mode_tab_changed(self, index):
        """معالج تغيير تبويب الوضع."""
        # تبويب الصفحات = 0، تبويب الإعدادات = 1
        pass

    def _on_job_type_changed(self, index):
        """معالج تغيير نوع المحتوى (فيديو/ستوري/ريلز)."""
        # Clear editing state when switching job types
        self._editing_job = None

        # 0 = فيديو، 1 = ستوري، 2 = ريلز
        is_story_mode = (index == 1)
        is_reels_mode = (index == 2)
        is_video_mode = (index == 0)

        # تحديث الوضع الحالي
        if is_story_mode:
            self.current_mode = 'story'
        elif is_reels_mode:
            self.current_mode = 'reels'
        else:
            self.current_mode = 'video'

        # إظهار/إخفاء لوحة إعدادات الستوري (للستوري فقط)
        self.story_panel.setVisible(is_story_mode)

        # إظهار/إخفاء خيارات خاصة بالفيديو والريلز (العنوان والوصف و Anti-Ban والعلامة المائية)
        # الريلز يستخدم نفس إعدادات الفيديو
        show_video_options = is_video_mode or is_reels_mode
        self.title_widget.setVisible(show_video_options)
        self.desc_widget.setVisible(show_video_options)
        self.jitter_widget.setVisible(show_video_options)
        self.job_watermark_group.setVisible(show_video_options)

        # تحديث نص المجلد حسب النوع (فقط إذا كان بالقيمة الافتراضية)
        current_folder = self.folder_btn.text()
        default_texts = ['اختر مجلد الفيديوهات', 'اختر مجلد الستوري', 'اختر مجلد الريلز',
                        '📁 اختر مجلد الفيديوهات', '📁 اختر مجلد الستوري', '📁 اختر مجلد الريلز']

        # فقط إذا كان النص الحالي هو قيمة افتراضية، نقوم بتحديثه
        if not current_folder or current_folder in default_texts or current_folder.startswith('📁 اختر'):
            if is_story_mode:
                self.folder_btn.setText('اختر مجلد الستوري')
            elif is_reels_mode:
                self.folder_btn.setText('اختر مجلد الريلز')
            else:
                self.folder_btn.setText('اختر مجلد الفيديوهات')

        # تحديث الأيقونة دائماً
        if HAS_QTAWESOME:
            self.folder_btn.setIcon(get_icon(ICONS['folder'], ICON_COLORS.get('folder')))

        # تحديث قائمة الوظائف حسب النوع
        self.refresh_jobs_list()

    def _choose_job_watermark(self):
        """اختيار ملف الشعار للعلامة المائية لهذه المهمة."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'اختر ملف الشعار', '',
            'صور (*.png *.jpg *.jpeg *.bmp);;جميع الملفات (*)'
        )
        if file_path:
            self.job_watermark_path_label.setText(file_path)
            self.job_watermark_path_label.setStyleSheet('')  # إزالة اللون الرمادي

    def _show_watermark_preview(self):
        """فتح نافذة معاينة العلامة المائية."""
        # الحصول على الإعدادات الحالية
        watermark_path = self.job_watermark_path_label.text()
        if watermark_path == 'لم يتم اختيار شعار':
            watermark_path = ''

        positions = ['top_left', 'top_right', 'bottom_left', 'bottom_right', 'center']
        position = positions[self.job_watermark_position_combo.currentIndex()]

        opacity = self.job_watermark_opacity_slider.value() / 100.0
        scale = self.job_watermark_size_slider.value() / 100.0

        dialog = WatermarkPreviewDialog(
            self,
            watermark_path=watermark_path,
            position=position,
            opacity=opacity,
            scale=scale
        )

        if dialog.exec() == QDialog.Accepted:
            # تطبيق الإعدادات الجديدة
            settings = dialog.get_settings()

            # تحديث الموقع
            position_index = {'top_left': 0, 'top_right': 1, 'bottom_left': 2, 'bottom_right': 3, 'center': 4}
            if settings['position'] == 'custom':
                # حفظ الموقع المخصص من السحب
                self._current_watermark_x = settings.get('custom_x')
                self._current_watermark_y = settings.get('custom_y')
                # تعيين الموقع إلى center كقيمة fallback في الواجهة
                self.job_watermark_position_combo.setCurrentIndex(4)
            else:
                self.job_watermark_position_combo.setCurrentIndex(position_index[settings['position']])
                # إعادة تعيين الإحداثيات المخصصة
                self._current_watermark_x = None
                self._current_watermark_y = None

            # تحديث الحجم
            self.job_watermark_size_slider.setValue(int(settings['scale'] * 100))

            # تحديث الشفافية
            self.job_watermark_opacity_slider.setValue(int(settings['opacity'] * 100))

    def _build_stats_tab(self, layout):
        """بناء تبويب الإحصائيات."""
        stats_group = QGroupBox('إحصائيات الرفع')
        stats_form = QFormLayout()

        # إحصائيات عامة
        self.stats_total_label = QLabel('0')
        stats_form.addRow('إجمالي الرفع:', self.stats_total_label)

        self.stats_success_label = QLabel('0')
        stats_form.addRow('الناجحة:', self.stats_success_label)

        self.stats_failed_label = QLabel('0')
        stats_form.addRow('الفاشلة:', self.stats_failed_label)

        # معدل النجاح
        self.stats_success_rate_label = QLabel('0%')
        stats_form.addRow('معدل النجاح:', self.stats_success_rate_label)

        stats_group.setLayout(stats_form)
        layout.addWidget(stats_group)

        # الرسم البياني الأسبوعي
        weekly_group = QGroupBox('الإحصائيات الأسبوعية')
        if HAS_QTAWESOME:
            weekly_group.setTitle('')
        weekly_layout = QVBoxLayout()

        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            weekly_title_row = QHBoxLayout()
            weekly_icon_label = QLabel()
            weekly_icon_label.setPixmap(get_icon(ICONS['chart'], ICON_COLORS.get('chart')).pixmap(16, 16))
            weekly_title_row.addWidget(weekly_icon_label)
            weekly_title_row.addWidget(QLabel('الإحصائيات الأسبوعية'))
            weekly_title_row.addStretch()
            weekly_layout.addLayout(weekly_title_row)

        self.weekly_chart_text = QTextEdit()
        self.weekly_chart_text.setReadOnly(True)
        self.weekly_chart_text.setMaximumHeight(200)
        self.weekly_chart_text.setStyleSheet('font-family: monospace; font-size: 12px;')
        weekly_layout.addWidget(self.weekly_chart_text)

        weekly_group.setLayout(weekly_layout)
        layout.addWidget(weekly_group)

        # جدول آخر الرفع
        recent_group = QGroupBox('آخر الفيديوهات المرفوعة')
        recent_layout = QVBoxLayout()

        self.recent_uploads_table = QTableWidget()
        self.recent_uploads_table.setColumnCount(4)
        self.recent_uploads_table.setHorizontalHeaderLabels(['الملف', 'الصفحة', 'التاريخ', 'الحالة'])
        self.recent_uploads_table.horizontalHeader().setStretchLastSection(True)
        self.recent_uploads_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        recent_layout.addWidget(self.recent_uploads_table)

        # صف الأزرار (تحديث وتصفير)
        buttons_row = QHBoxLayout()

        refresh_btn = create_icon_button('تحديث الإحصائيات', 'refresh')
        refresh_btn.clicked.connect(self._refresh_stats)
        buttons_row.addWidget(refresh_btn)

        reset_btn = create_icon_button('تصفير الإحصائيات', 'delete')
        reset_btn.clicked.connect(self._reset_stats)
        buttons_row.addWidget(reset_btn)

        recent_layout.addLayout(buttons_row)

        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)

        layout.addStretch()

    def _refresh_stats(self):
        """تحديث الإحصائيات من قاعدة البيانات."""
        stats = get_upload_stats(days=30)

        self.stats_total_label.setText(str(stats.get('total', 0)))
        self.stats_success_label.setText(str(stats.get('successful', 0)))
        self.stats_failed_label.setText(str(stats.get('failed', 0)))

        # معدل النجاح
        success_rate = stats.get('success_rate', 0)
        self.stats_success_rate_label.setText(f'{success_rate:.1f}%')

        # الرسم البياني الأسبوعي
        weekly_stats = stats.get('weekly_stats', {})
        if weekly_stats:
            chart = generate_text_chart(weekly_stats)
            self.weekly_chart_text.setText(chart)
        else:
            self.weekly_chart_text.setText('لا توجد بيانات للأسبوع الماضي')

        # تحديث جدول آخر الرفع
        recent = stats.get('recent', [])
        self.recent_uploads_table.setRowCount(len(recent))

        for row, item in enumerate(recent):
            file_name, page_name, video_url, uploaded_at, status = item
            self.recent_uploads_table.setItem(row, 0, QTableWidgetItem(file_name or ''))
            self.recent_uploads_table.setItem(row, 1, QTableWidgetItem(page_name or ''))
            self.recent_uploads_table.setItem(row, 2, QTableWidgetItem(uploaded_at or ''))
            status_text = '✅ نجح' if status == 'success' else '❌ فشل'
            self.recent_uploads_table.setItem(row, 3, QTableWidgetItem(status_text))

    def _reset_stats(self):
        """تصفير الإحصائيات بعد تأكيد المستخدم."""
        reply = QMessageBox.question(
            self,
            'تأكيد التصفير',
            'هل أنت متأكد من تصفير جميع الإحصائيات؟\nلا يمكن التراجع عن هذا الإجراء.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # تشغيل العملية في خيط منفصل لمنع تجميد الواجهة
            def do_reset():
                try:
                    if reset_upload_stats():
                        # استخدام signal لتحديث الواجهة من الخيط الرئيسي
                        self.ui_signals.log_signal.emit('✅ تم تصفير الإحصائيات بنجاح')
                        # تأخير قصير ثم تحديث العرض
                        QTimer.singleShot(100, self._refresh_stats)
                    else:
                        self.ui_signals.log_signal.emit('❌ فشل تصفير الإحصائيات')
                except Exception as e:
                    self.ui_signals.log_signal.emit(f'❌ خطأ: {e}')

            threading.Thread(target=do_reset, daemon=True).start()

    def _build_settings_tab(self, layout):
        """بناء تبويب الإعدادات المتقدمة."""
        # تم إزالة مجموعة ساعات العمل من هنا (Requirement 4)
        # لأن ساعات العمل موجودة بالفعل على الواجهة الرئيسية

        # تم إزالة مجموعة العلامة المائية من الإعدادات العامة
        # لأنها أصبحت موجودة في إعدادات كل مهمة فيديو

        # مجموعة التحقق من الفيديو
        validation_group = QGroupBox('التحقق من صحة الفيديو')
        if HAS_QTAWESOME:
            validation_group.setTitle('')
        validation_form = QFormLayout()

        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            val_title_row = QHBoxLayout()
            val_icon_label = QLabel()
            val_icon_label.setPixmap(get_icon(ICONS['warning'], ICON_COLORS.get('warning')).pixmap(16, 16))
            val_title_row.addWidget(val_icon_label)
            val_title_row.addWidget(QLabel('التحقق من صحة الفيديو'))
            val_title_row.addStretch()
            validation_form.addRow(val_title_row)

        self.validate_videos_checkbox = QCheckBox('التحقق من الفيديوهات قبل الرفع')
        self.validate_videos_checkbox.setChecked(self.validate_videos)
        self.validate_videos_checkbox.setToolTip('فحص ملفات الفيديو للتأكد من صلاحيتها قبل محاولة الرفع')
        validation_form.addRow(self.validate_videos_checkbox)

        validation_group.setLayout(validation_form)
        layout.addWidget(validation_group)

        # مجموعة فحص الاتصال بالإنترنت
        internet_group = QGroupBox('فحص الاتصال بالإنترنت')
        if HAS_QTAWESOME:
            internet_group.setTitle('')
        internet_form = QFormLayout()

        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            net_title_row = QHBoxLayout()
            net_icon_label = QLabel()
            net_icon_label.setPixmap(get_icon(ICONS['network'], ICON_COLORS.get('network')).pixmap(16, 16))
            net_title_row.addWidget(net_icon_label)
            net_title_row.addWidget(QLabel('فحص الاتصال بالإنترنت'))
            net_title_row.addStretch()
            internet_form.addRow(net_title_row)

        self.internet_check_checkbox = QCheckBox('فحص الاتصال قبل كل عملية رفع')
        if HAS_QTAWESOME:
            self.internet_check_checkbox.setIcon(get_icon(ICONS['network'], ICON_COLORS.get('network')))
        self.internet_check_checkbox.setChecked(self.internet_check_enabled)
        self.internet_check_checkbox.setToolTip('عند تفعيل هذا الخيار، سيتحقق البرنامج من الاتصال بالإنترنت قبل كل رفع.\nإذا انقطع الاتصال، سيدخل في وضع الغفوة ويعيد المحاولة كل دقيقة حتى يعود الاتصال.')
        internet_form.addRow(self.internet_check_checkbox)

        internet_group.setLayout(internet_form)
        layout.addWidget(internet_group)

        # مجموعة إشعارات Telegram Bot
        telegram_group = QGroupBox('إشعارات Telegram')
        if HAS_QTAWESOME:
            telegram_group.setTitle('')
        telegram_layout = QVBoxLayout()

        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            tg_title_row = QHBoxLayout()
            tg_icon_label = QLabel()
            tg_icon_label.setPixmap(get_icon(ICONS['telegram'], ICON_COLORS.get('telegram')).pixmap(16, 16))
            tg_title_row.addWidget(tg_icon_label)
            tg_title_row.addWidget(QLabel('إشعارات Telegram Bot'))
            tg_title_row.addStretch()
            telegram_layout.addLayout(tg_title_row)

        # تفعيل الإشعارات
        self.telegram_enabled_checkbox = QCheckBox('تفعيل إشعارات Telegram')
        self.telegram_enabled_checkbox.setChecked(self.telegram_enabled)
        self.telegram_enabled_checkbox.setToolTip('إرسال إشعارات عند نجاح أو فشل رفع الفيديو عبر Telegram Bot')
        telegram_layout.addWidget(self.telegram_enabled_checkbox)

        # خيارات أنواع الإشعارات
        notify_options_layout = QVBoxLayout()
        notify_options_layout.setContentsMargins(20, 5, 0, 5)  # إزاحة للداخل

        # خيار إرسال إشعارات النجاح
        self.telegram_notify_success_checkbox = QCheckBox('إرسال إشعارات نجاح الرفع ✅')
        self.telegram_notify_success_checkbox.setChecked(getattr(self, 'telegram_notify_success', True))
        self.telegram_notify_success_checkbox.setToolTip('إرسال إشعار عند نجاح رفع فيديو أو ستوري أو ريلز')
        notify_options_layout.addWidget(self.telegram_notify_success_checkbox)

        # خيار إرسال إشعارات الأخطاء
        self.telegram_notify_errors_checkbox = QCheckBox('إرسال إشعارات الأخطاء والفشل ❌')
        self.telegram_notify_errors_checkbox.setChecked(getattr(self, 'telegram_notify_errors', True))
        self.telegram_notify_errors_checkbox.setToolTip('إرسال إشعار عند فشل الرفع أو حدوث أي خطأ في البرنامج')
        notify_options_layout.addWidget(self.telegram_notify_errors_checkbox)

        telegram_layout.addLayout(notify_options_layout)

        # حقول الإعدادات
        telegram_form = QFormLayout()

        # توكن البوت
        self.telegram_bot_token_input = QLineEdit()
        self.telegram_bot_token_input.setPlaceholderText('أدخل توكن البوت من @BotFather')
        self.telegram_bot_token_input.setText(self.telegram_bot_token)
        self.telegram_bot_token_input.setEchoMode(QLineEdit.Password)
        telegram_form.addRow('توكن البوت:', self.telegram_bot_token_input)

        # معرّف المحادثة
        self.telegram_chat_id_input = QLineEdit()
        self.telegram_chat_id_input.setPlaceholderText('معرّف المحادثة أو القناة (مثل: -1001234567890)')
        self.telegram_chat_id_input.setText(self.telegram_chat_id)
        telegram_form.addRow('معرّف المحادثة:', self.telegram_chat_id_input)

        telegram_layout.addLayout(telegram_form)

        # صف أزرار Telegram
        telegram_buttons_row = QHBoxLayout()

        # زر اختبار الاتصال
        self.telegram_test_btn = create_icon_button('اختبار الاتصال', 'telegram')
        self.telegram_test_btn.clicked.connect(self._test_telegram_connection)
        telegram_buttons_row.addWidget(self.telegram_test_btn)

        # تعليمات الحصول على التوكن
        telegram_help_btn = create_icon_button('كيفية الإعداد؟', 'info')
        telegram_help_btn.clicked.connect(self._show_telegram_help)
        telegram_buttons_row.addWidget(telegram_help_btn)

        telegram_layout.addLayout(telegram_buttons_row)

        # رسالة الحالة
        self.telegram_status_label = QLabel('')
        self.telegram_status_label.setAlignment(Qt.AlignCenter)
        self.telegram_status_label.setWordWrap(True)
        telegram_layout.addWidget(self.telegram_status_label)

        telegram_group.setLayout(telegram_layout)
        layout.addWidget(telegram_group)

        # مجموعة تحديث المكتبات
        updates_group = QGroupBox('تحديث المكتبات')
        if HAS_QTAWESOME:
            updates_group.setTitle('')
        updates_layout = QVBoxLayout()

        # عنوان المجموعة مع أيقونة
        if HAS_QTAWESOME:
            updates_title_row = QHBoxLayout()
            updates_icon_label = QLabel()
            updates_icon_label.setPixmap(get_icon(ICONS['update'], ICON_COLORS.get('update')).pixmap(16, 16))
            updates_title_row.addWidget(updates_icon_label)
            updates_title_row.addWidget(QLabel('تحديث المكتبات'))
            updates_title_row.addStretch()
            updates_layout.addLayout(updates_title_row)

        # جدول المكتبات
        self.updates_table = QTableWidget()
        self.updates_table.setColumnCount(4)
        self.updates_table.setHorizontalHeaderLabels(['المكتبة', 'الحالي', 'المتاح', 'الحالة'])
        self.updates_table.horizontalHeader().setStretchLastSection(True)
        self.updates_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.updates_table.setMaximumHeight(150)
        updates_layout.addWidget(self.updates_table)

        # رسالة الحالة
        self.update_status_label = QLabel('اضغط على "البحث عن تحديثات" للتحقق')
        self.update_status_label.setAlignment(Qt.AlignCenter)
        updates_layout.addWidget(self.update_status_label)

        # أزرار التحديث
        update_buttons_row = QHBoxLayout()

        self.check_updates_btn = create_icon_button('البحث عن تحديثات', 'search')
        self.check_updates_btn.clicked.connect(self._check_for_updates)
        update_buttons_row.addWidget(self.check_updates_btn)

        self.update_all_btn = create_icon_button('تحديث الكل', 'update', color=COUNTDOWN_COLOR_GREEN)
        self.update_all_btn.clicked.connect(self._run_updates)
        self.update_all_btn.setVisible(False)  # يظهر فقط عند وجود تحديثات
        self.update_all_btn.setStyleSheet(f'background-color: {COUNTDOWN_COLOR_GREEN}; color: white; font-weight: bold;')
        update_buttons_row.addWidget(self.update_all_btn)

        updates_layout.addLayout(update_buttons_row)
        updates_group.setLayout(updates_layout)
        layout.addWidget(updates_group)

        # تخزين قائمة التحديثات المتاحة
        self._available_updates = []

        # زر حفظ الإعدادات
        save_settings_btn = create_icon_button('حفظ الإعدادات', 'save')
        save_settings_btn.clicked.connect(self._save_advanced_settings)
        layout.addWidget(save_settings_btn)

        layout.addStretch()

    def _save_advanced_settings(self):
        """حفظ الإعدادات المتقدمة."""
        # التحقق من الفيديو
        self.validate_videos = self.validate_videos_checkbox.isChecked()

        # فحص الاتصال بالإنترنت
        self.internet_check_enabled = self.internet_check_checkbox.isChecked()

        # إعدادات Telegram Bot
        self.telegram_enabled = self.telegram_enabled_checkbox.isChecked()
        self.telegram_bot_token = self.telegram_bot_token_input.text().strip()
        self.telegram_chat_id = self.telegram_chat_id_input.text().strip()
        self.telegram_notify_success = self.telegram_notify_success_checkbox.isChecked()
        self.telegram_notify_errors = self.telegram_notify_errors_checkbox.isChecked()

        # تحديث مثيل TelegramNotifier
        telegram_notifier.enabled = self.telegram_enabled
        telegram_notifier.bot_token = self.telegram_bot_token
        telegram_notifier.chat_id = self.telegram_chat_id
        telegram_notifier.notify_success = self.telegram_notify_success
        telegram_notifier.notify_errors = self.telegram_notify_errors

        self._save_settings()
        self._log_append('تم حفظ الإعدادات المتقدمة.')

    def _test_telegram_connection(self):
        """اختبار الاتصال بـ Telegram Bot."""
        # حفظ الإعدادات المؤقتة
        bot_token = self.telegram_bot_token_input.text().strip()
        chat_id = self.telegram_chat_id_input.text().strip()

        if not bot_token or not chat_id:
            self.telegram_status_label.setText('❌ يرجى إدخال توكن البوت ومعرّف المحادثة')
            self.telegram_status_label.setStyleSheet('color: #F44336;')
            return

        self.telegram_test_btn.setEnabled(False)
        self.telegram_test_btn.setText('جاري الاختبار...')
        self.telegram_status_label.setText('⏳ جاري اختبار الاتصال...')
        self.telegram_status_label.setStyleSheet('')

        def test_worker():
            # إنشاء مثيل مؤقت للاختبار
            test_notifier = TelegramNotifier(bot_token, chat_id, enabled=True)
            success, message = test_notifier.test_connection()

            # استخدام Signal بدلاً من QTimer لضمان تحديث الواجهة من الخيط الرئيسي
            self.ui_signals.telegram_test_result.emit(success, message)

        threading.Thread(target=test_worker, daemon=True).start()

    def _update_telegram_test_result(self, success: bool, message: str):
        """تحديث نتيجة اختبار Telegram."""
        self.telegram_test_btn.setEnabled(True)
        self.telegram_test_btn.setText('اختبار الاتصال')
        if HAS_QTAWESOME:
            self.telegram_test_btn.setIcon(get_icon(ICONS['telegram'], ICON_COLORS.get('telegram')))

        if success:
            self.telegram_status_label.setText(f'✅ {message}')
            self.telegram_status_label.setStyleSheet('color: #4CAF50;')
            # حفظ الإعدادات تلقائياً عند نجاح اختبار الاتصال
            self.telegram_bot_token = self.telegram_bot_token_input.text().strip()
            self.telegram_chat_id = self.telegram_chat_id_input.text().strip()
            self.telegram_enabled = self.telegram_enabled_checkbox.isChecked()
            self.telegram_notify_success = self.telegram_notify_success_checkbox.isChecked()
            self.telegram_notify_errors = self.telegram_notify_errors_checkbox.isChecked()
            # تحديث مثيل TelegramNotifier
            telegram_notifier.enabled = self.telegram_enabled
            telegram_notifier.bot_token = self.telegram_bot_token
            telegram_notifier.chat_id = self.telegram_chat_id
            telegram_notifier.notify_success = self.telegram_notify_success
            telegram_notifier.notify_errors = self.telegram_notify_errors
            # حفظ الإعدادات
            self._save_settings()
            self._log_append('✅ تم حفظ إعدادات Telegram بنجاح بعد اختبار الاتصال')
        else:
            self.telegram_status_label.setText(f'❌ {message}')
            self.telegram_status_label.setStyleSheet('color: #F44336;')
            # إظهار نافذة منبثقة عند فشل الاتصال
            QMessageBox.warning(
                self,
                'فشل الاتصال بـ Telegram',
                f'لم يتم الاتصال بالبوت:\n\n{message}\n\n'
                'تأكد من:\n'
                '• صحة التوكن\n'
                '• صحة معرّف المحادثة\n'
                '• اتصالك بالإنترنت'
            )

    def _show_telegram_help(self):
        """عرض تعليمات إعداد Telegram Bot."""
        help_text = '''
<h3>كيفية إعداد إشعارات Telegram Bot</h3>

<h4>1. إنشاء بوت جديد:</h4>
<ol>
<li>افتح تطبيق Telegram وابحث عن <b>@BotFather</b></li>
<li>أرسل الأمر <code>/newbot</code></li>
<li>اختر اسماً للبوت (مثل: My Upload Notifier)</li>
<li>اختر username للبوت (يجب أن ينتهي بـ bot)</li>
<li>ستحصل على <b>توكن البوت</b> - انسخه</li>
</ol>

<h4>2. الحصول على معرّف المحادثة (Chat ID):</h4>
<p><b>للمحادثة الشخصية:</b></p>
<ol>
<li>ابحث عن <b>@userinfobot</b> في Telegram</li>
<li>اضغط Start</li>
<li>سيظهر لك الـ <b>Id</b> الخاص بك</li>
</ol>

<p><b>للمجموعة أو القناة:</b></p>
<ol>
<li>أضف البوت للمجموعة/القناة كمشرف</li>
<li>أرسل رسالة في المجموعة</li>
<li>افتح الرابط: <code>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</code></li>
<li>ابحث عن "chat":{"id": وانسخ الرقم (يبدأ عادة بـ -100)</li>
</ol>

<h4>3. ملاحظات:</h4>
<ul>
<li>تأكد من بدء محادثة مع البوت أولاً (اضغط /start)</li>
<li>معرّف القنوات يبدأ عادة بـ <code>-100</code></li>
<li>يمكن استخدام @username بدلاً من الـ ID للقنوات العامة</li>
</ul>
'''
        QMessageBox.information(self, 'تعليمات Telegram Bot', help_text)

    def _check_for_updates(self):
        """
        Check for library updates.
        التحقق من وجود تحديثات للمكتبات.
        """
        self.check_updates_btn.setEnabled(False)
        self.check_updates_btn.setText('جاري البحث...')
        self.update_status_label.setText('جاري التحقق من التحديثات...')
        self.updates_table.setRowCount(0)
        self.update_all_btn.setVisible(False)
        self._available_updates = []

        # استخدام متغير للتخزين المؤقت
        self._update_check_result = {'installed': {}, 'updates': [], 'error': None}

        def check_worker():
            try:
                self.ui_signals.log_signal.emit('🔍 جاري التحقق من التحديثات...')

                # الحصول على الإصدارات المثبتة
                installed = get_installed_versions()
                self._update_check_result['installed'] = installed

                # الحصول على التحديثات المتاحة
                updates = check_for_updates(None)  # بدون log لتجنب مشاكل الخيوط
                self._update_check_result['updates'] = updates

                self.ui_signals.log_signal.emit(f'✅ تم التحقق - وُجدت {len(updates)} تحديثات')

            except Exception as e:
                self._update_check_result['error'] = str(e)
                self.ui_signals.log_signal.emit(f'❌ خطأ في التحقق: {e}')
            finally:
                # استخدام Signal بدلاً من QTimer لضمان تحديث الواجهة من الخيط الرئيسي
                self.ui_signals.update_check_finished.emit()

        threading.Thread(target=check_worker, daemon=True).start()

    def _finish_update_check(self):
        """إنهاء عملية التحقق من التحديثات وتحديث الواجهة."""
        try:
            result = getattr(self, '_update_check_result', {})

            if result.get('error'):
                self._handle_update_check_error(result['error'])
                return

            installed = result.get('installed', {})
            updates = result.get('updates', [])

            self._populate_updates_table(installed, updates)

        except Exception as e:
            self._handle_update_check_error(str(e))

    def _handle_update_check_error(self, error_msg: str):
        """معالجة خطأ التحقق من التحديثات."""
        self.check_updates_btn.setEnabled(True)
        self.check_updates_btn.setText('البحث عن تحديثات')
        if HAS_QTAWESOME:
            self.check_updates_btn.setIcon(get_icon(ICONS.get('search', 'fa5s.search'), ICON_COLORS.get('search')))
        self.update_status_label.setText(f'❌ خطأ في التحقق: {error_msg[:80]}')
        self._log_append(f'❌ فشل التحقق من التحديثات: {error_msg}')

        # إظهار نافذة منبثقة للخطأ مع تفاصيل الخطأ
        error_detail = error_msg[:200] if len(error_msg) > 200 else error_msg
        QMessageBox.warning(
            self,
            '❌ خطأ في التحقق',
            f'تعذر التحقق من التحديثات.\nتأكد من اتصالك بالإنترنت.\n\nتفاصيل الخطأ:\n{error_detail}',
            QMessageBox.Ok
        )

    def _populate_updates_table(self, installed: dict, updates: list):
        """ملء جدول التحديثات بالبيانات."""
        try:
            # إنشاء قاموس التحديثات المتاحة
            updates_dict = {pkg[0].lower(): (pkg[1], pkg[2]) for pkg in updates}
            self._available_updates = [pkg[0] for pkg in updates]

            # ملء الجدول
            self.updates_table.setRowCount(len(UPDATE_PACKAGES))

            for row, pkg_name in enumerate(UPDATE_PACKAGES):
                # اسم المكتبة
                self.updates_table.setItem(row, 0, QTableWidgetItem(pkg_name))

                # الإصدار الحالي
                current_version = installed.get(pkg_name, 'غير مثبت')
                # البحث بغض النظر عن حالة الأحرف
                for key, value in installed.items():
                    if key.lower() == pkg_name.lower():
                        current_version = value
                        break
                self.updates_table.setItem(row, 1, QTableWidgetItem(current_version))

                # الإصدار المتاح والحالة
                if pkg_name.lower() in updates_dict:
                    _, latest_version = updates_dict[pkg_name.lower()]
                    self.updates_table.setItem(row, 2, QTableWidgetItem(latest_version))
                    status_item = QTableWidgetItem('تحديث متاح')
                    status_item.setForeground(QColor(COUNTDOWN_COLOR_YELLOW))  # أصفر/برتقالي
                    self.updates_table.setItem(row, 3, status_item)
                else:
                    self.updates_table.setItem(row, 2, QTableWidgetItem(current_version))
                    status_item = QTableWidgetItem('محدث')
                    status_item.setForeground(QColor(COUNTDOWN_COLOR_GREEN))  # أخضر
                    self.updates_table.setItem(row, 3, status_item)

            # تحديث رسالة الحالة وزر التحديث
            if updates:
                self.update_status_label.setText(f'⚠️ يوجد {len(updates)} تحديثات متاحة')
                self.update_all_btn.setVisible(True)

                # إنشاء قائمة التحديثات للعرض في الرسالة
                updates_list = '\n'.join([
                    f'• {pkg[0]}: {pkg[1]} → {pkg[2]}'
                    for pkg in updates
                ])

                # إظهار نافذة منبثقة تسأل المستخدم إذا أراد التحديث الآن
                # ملاحظة: يتم تضمين تحذير إغلاق البرنامج في هذه الرسالة
                reply = QMessageBox.question(
                    self,
                    '⚠️ تحديثات متاحة',
                    f'يوجد {len(updates)} تحديثات للمكتبات التالية:\n\n{updates_list}\n\n'
                    'سيتم إغلاق البرنامج لإتمام التحديث.\nهل تريد التحديث الآن؟',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    # تشغيل التحديث مباشرة (بدون نافذة تأكيد إضافية)
                    self._run_updates(skip_confirmation=True)
            else:
                self.update_status_label.setText('✅ جميع المكتبات محدثة - لا توجد تحديثات متاحة')
                self.update_all_btn.setVisible(False)

                # إظهار نافذة منبثقة عند عدم وجود تحديثات
                QMessageBox.information(
                    self,
                    '✅ لا توجد تحديثات',
                    'جميع المكتبات محدثة!\nأنت تستخدم أحدث الإصدارات.',
                    QMessageBox.Ok
                )
        except Exception as e:
            self.update_status_label.setText(f'❌ خطأ: {str(e)[:80]}')
        finally:
            # دائماً إعادة الزر للحالة الطبيعية
            self.check_updates_btn.setEnabled(True)
            self.check_updates_btn.setText('البحث عن تحديثات')
            if HAS_QTAWESOME:
                self.check_updates_btn.setIcon(get_icon(ICONS.get('search', 'fa5s.search'), ICON_COLORS.get('search')))

    def _reset_update_ui(self):
        """إعادة تعيين واجهة التحديث عند حدوث خطأ."""
        self.check_updates_btn.setEnabled(True)
        if HAS_QTAWESOME:
            self.check_updates_btn.setIcon(get_icon(ICONS.get('search', 'fa5s.search'), ICON_COLORS.get('search')))
        self.check_updates_btn.setText('البحث عن تحديثات')
        self.update_status_label.setText('حدث خطأ أثناء التحقق من التحديثات')

    def _run_updates(self, skip_confirmation: bool = False):
        """
        تشغيل عملية التحديث باستخدام updater.py المنفصل.

        Args:
            skip_confirmation: إذا كانت True، يتم تخطي نافذة التأكيد
                              (مستخدمة عندما يتم استدعاء الدالة من نافذة منبثقة أكدت التحديث مسبقاً)
        """
        if not self._available_updates:
            QMessageBox.information(self, 'لا توجد تحديثات', 'جميع المكتبات محدثة بالفعل.')
            return

        # نافذة تأكيد (يتم تخطيها إذا تم التأكيد مسبقاً)
        if not skip_confirmation:
            reply = QMessageBox.question(
                self,
                'تأكيد التحديث',
                'سيتم إغلاق البرنامج لإتمام التحديث. هل تريد المتابعة؟\n\n'
                f'المكتبات التي سيتم تحديثها:\n{", ".join(self._available_updates)}',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

        # حفظ جميع الإعدادات قبل الإغلاق
        self._log_append('جاري حفظ الإعدادات قبل التحديث...')
        self.save_all()

        # إيقاف المجدول إذا كان يعمل
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self._log_append('جاري إيقاف المجدول...')
            self.stop_scheduler()

        self._log_append('جاري بدء عملية التحديث...')

        # استخدام نظام التحديث الجديد مع updater.py
        try:
            # حفظ معلومات التحديث في ملف JSON
            update_info = {
                'packages': self._available_updates,
                'app_path': os.path.abspath(sys.argv[0]),
                'app_pid': os.getpid()
            }

            update_info_path = _get_appdata_folder() / 'update_info.json'
            with open(update_info_path, 'w', encoding='utf-8') as f:
                json.dump(update_info, f, ensure_ascii=False, indent=2)

            # البحث عن مسار updater.py
            updater_path = get_resource_path('updater.py')
            if not os.path.exists(updater_path):
                # محاولة البحث بجانب الملف الحالي
                updater_path = Path(__file__).parent / 'updater.py'

            if not os.path.exists(updater_path):
                self._log_append('❌ ملف updater.py غير موجود')
                QMessageBox.warning(self, 'خطأ', 'ملف التحديث غير موجود.\nسيتم استخدام الطريقة القديمة.')
                run_update_and_restart(self._available_updates)
                return

            # تشغيل updater.py كعملية منفصلة
            if sys.platform == 'win32':
                # في Windows، استخدم start لفتح نافذة جديدة
                subprocess.Popen(
                    ['start', 'cmd', '/k', sys.executable, str(updater_path)],
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # في Linux/Mac
                subprocess.Popen(
                    [sys.executable, str(updater_path)],
                    start_new_session=True
                )

            # إغلاق التطبيق
            self._log_append('جاري إغلاق التطبيق للتحديث...')
            QApplication.quit()

        except Exception as e:
            self._log_append(f'❌ خطأ في بدء التحديث: {e}')
            QMessageBox.warning(self, 'خطأ', f'فشل بدء عملية التحديث:\n{e}')
            # Fallback للطريقة القديمة
            run_update_and_restart(self._available_updates)

    # ==================== Hashtag Manager ====================

    def _open_schedule_templates_dialog(self):
        """فتح نافذة إدارة قوالب الجداول الذكية."""
        dialog = ScheduleTemplatesDialog(self)
        dialog.exec()

    def _show_hashtag_manager(self):
        """عرض نافذة مدير الهاشتاجات."""
        dialog = HashtagManagerDialog(self)
        if dialog.exec() == QDialog.Accepted:
            selected_hashtags = dialog.get_selected_hashtags()
            if selected_hashtags:
                current_desc = self.page_desc_input.text()
                if current_desc:
                    self.page_desc_input.setText(f'{current_desc} {selected_hashtags}')
                else:
                    self.page_desc_input.setText(selected_hashtags)

    def _cleanup_threads(self):
        """
        تنظيف جميع الـ Threads النشطة بشكل آمن.
        يتم استدعاؤها قبل إغلاق التطبيق لتجنب crash.
        """
        threads_to_cleanup = []

        # 1. تنظيف threads لوحة الصفحات
        self.pages_panel.cleanup()

        # 2. Threads جلب التوكن
        if hasattr(self, '_active_token_threads'):
            for thread in self._active_token_threads:
                if thread and thread.isRunning():
                    threads_to_cleanup.append(('TokenExchangeThread', thread))

        # إيقاف جميع الـ threads
        for name, thread in threads_to_cleanup:
            if thread.isRunning():
                try:
                    # طلب إيقاف الـ thread
                    thread.quit()
                    # انتظار للإنهاء
                    if not thread.wait(THREAD_QUIT_TIMEOUT_MS):
                        # إذا لم ينتهِ، إجبار الإنهاء
                        thread.terminate()
                        thread.wait(THREAD_TERMINATE_TIMEOUT_MS)
                except (RuntimeError, AttributeError) as e:
                    # RuntimeError: قد يحدث إذا كان الـ thread قد انتهى بالفعل
                    # AttributeError: قد يحدث إذا كان الـ thread قد تم حذفه
                    log_debug(f'خطأ في تنظيف {name}: {e}')

        # تنظيف المراجع
        if hasattr(self, '_active_token_threads'):
            self._active_token_threads.clear()

    def closeEvent(self, event):
        """معالج إغلاق النافذة - الإخفاء إلى Tray دائماً."""
        if self.tray_icon:
            # إخفاء النافذة والاستمرار في الخلفية
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                APP_TITLE,
                'البرنامج يعمل في الخلفية. انقر على الأيقونة لإظهار النافذة.',
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            # الإغلاق النهائي (فقط إذا لم يكن System Tray متوفراً)
            # تنظيف الـ Threads النشطة قبل الإغلاق لتجنب crash
            self._cleanup_threads()
            self.stop_scheduler()
            self.save_all()
            event.accept()

