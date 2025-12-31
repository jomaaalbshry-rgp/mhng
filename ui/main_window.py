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
    get_default_template, set_default_template, get_schedule_times_for_template,
    migrate_json_to_sqlite
)
from secure_utils import encrypt_text as secure_encrypt, decrypt_text as secure_decrypt

# استيراد الوحدات المنفصلة للفيديو والستوري والريلز
from core import BaseJob
from core.jobs import PageJob
from controllers.video_controller import VideoJob, get_video_files, count_video_files
from controllers.story_controller import (
    StoryJob, get_story_files, count_story_files, get_next_story_batch,
    DEFAULT_STORIES_PER_SCHEDULE, DEFAULT_RANDOM_DELAY_MIN, DEFAULT_RANDOM_DELAY_MAX,
    upload_story, is_story_upload_successful, translate_fb_error,
    get_random_delay, simulate_human_behavior, log_error_to_file,
    safe_process_story_job
)
from controllers.reels_controller import ReelsJob, get_reels_files, count_reels_files, check_reels_duration
from services import get_pages, PageFetchWorker, TokenExchangeWorker, AllPagesFetchWorker
from services import (
    resumable_upload, apply_watermark_to_video,
    cleanup_temp_watermark_file, upload_video_once
)
from core import (
    get_resource_path, get_subprocess_args, run_subprocess, create_popen, SmartUploadScheduler,
    APIUsageTracker, APIWarningSystem, get_api_tracker, get_api_warning_system,
    API_CALLS_PER_STORY, get_date_placeholder, apply_title_placeholders,
    make_job_key, get_job_key,
    # Video utils
    validate_video, clean_filename_for_title, calculate_jitter_interval,
    sort_video_files, apply_template, get_random_emoji,
    # Updater utils
    check_for_updates, get_installed_versions, create_update_script,
    run_update_and_restart, UPDATE_PACKAGES
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
# استيراد المجدولات مباشرة لتجنب circular import
# Import schedulers directly to avoid circular import
from core.schedulers import SchedulerThread, StorySchedulerThread, ReelsSchedulerThread
from ui.widgets import NoScrollComboBox, NoScrollSpinBox, NoScrollDoubleSpinBox, NoScrollSlider, JobListItemWidget
from ui.dialogs import (
    HashtagManagerDialog as HashtagManagerDialogBase,
    ScheduleTemplatesDialog,
    TokenManagementDialog
)
from ui.helpers import (
    create_fallback_icon, load_app_icon, get_icon,
    create_icon_button, create_icon_action,
    ICONS, ICON_COLORS, HAS_QTAWESOME, HAS_QDARKTHEME,
    # Import formatting functions
    mask_token, seconds_to_value_unit, format_remaining_time,
    format_time_12h, format_datetime_12h,
    # Import helper functions (Phase 7 Refactoring)
    _set_windows_app_id, simple_encrypt, simple_decrypt,
    check_ffmpeg_available, add_watermark
)
from ui.components import JobsTable, LogViewer, LogLevel, ProgressWidget

# استيراد المتحكمات - Import Controllers
from controllers import VideoController, StoryController, ReelsController, SchedulerController

# استيراد فئات الفيديو من video_panel - Import video classes from video_panel
from ui.panels import DraggablePreviewLabel, WatermarkPreviewDialog, StoryPanel, PagesPanel

# استيراد التبويبات - Import Tabs
from ui.tabs import SettingsTab

# استيراد إشارات الواجهة - Import UI signals
from ui.signals import UiSignals

# استيراد واجهة المجدول - Import Scheduler UI
from ui.scheduler_ui import SchedulerUI

# استيراد الثيمات - Import Themes
from ui.themes import LIGHT_THEME_FALLBACK, DARK_THEME_CUSTOM

# استيراد معالجات الأحداث - Import Event Handlers
from ui.handlers import TelegramHandlers, UpdateHandlers, JobHandlers


# ==================== Fallback Protection for qdarktheme ====================
# Ensure HAS_QDARKTHEME is always defined even if import fails
# التأكد من أن HAS_QDARKTHEME معرّف دائماً حتى لو فشل الاستيراد
try:
    # Already imported from ui.helpers, but verify it exists
    _ = HAS_QDARKTHEME
except NameError:
    HAS_QDARKTHEME = False

# Import qdarktheme module if available (for apply_theme function)
# استيراد وحدة qdarktheme إذا كانت متاحة (لدالة apply_theme)
qdarktheme = None
if HAS_QDARKTHEME:
    try:
        import qdarktheme
    except ImportError:
        pass  # qdarktheme remains None



# ==================== Constants and Module Initialization ====================


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


# ==================== Module Initialization ====================
# تهيئة قاعدة البيانات عند تحميل الوحدة
# Database is initialized in admin.py before this module is imported
# تنفيذ الترحيل عند تحميل الوحدة - Execute migration when module loads
migrate_old_files()

# Step 1: Run legacy database initialization for other tables
migrate_json_to_sqlite()

# Step 2: Run legacy template initialization (for backwards compatibility)
init_default_templates()  # إنشاء قوالب الجداول الافتراضية
ensure_default_templates()  # ضمان وجود القوالب الافتراضية (للترقية)


# ==================== Notification Systems ====================
# TelegramNotifier and NotificationSystem have been moved to core/notifications.py
# They are imported above from core

# مثيل عام لنظام إشعارات Telegram
telegram_notifier = TelegramNotifier()


# ألوان العدّاد الزمني للوظائف
COUNTDOWN_COLOR_GREEN = '#27ae60'   # أخضر: ≥5 دقائق
COUNTDOWN_COLOR_YELLOW = '#f39c12'  # أصفر: 1-5 دقائق
COUNTDOWN_COLOR_RED = '#e74c3c'     # أحمر: <1 دقيقة
COUNTDOWN_COLOR_GRAY = '#808080'    # رمادي: معطّل

# نصوص الوقت المتبقي
REMAINING_TIME_RUNNING = "⏰ جاري التشغيل..."  # نص يظهر عند تشغيل الوظيفة
REMAINING_TIME_NOT_SCHEDULED = "---"  # نص يظهر للوظائف غير المجدولة


# ==================== Data Access Helpers ====================

def _get_jobs_file() -> Path:
    """
    Helper wrapper for get_jobs_file() from services.
    Provides backward compatibility for code using the underscore-prefixed name.
    
    Returns:
        Path: Path to the jobs file in AppData
    """
    return get_jobs_file()


# ==================== Module Initialization ====================
# تهيئة قاعدة البيانات عند تحميل الوحدة
# Database is initialized in admin.py before this module is imported
# تنفيذ الترحيل عند تحميل الوحدة - Execute migration when module loads
migrate_old_files()

# Step 1: Run legacy database initialization for other tables
migrate_json_to_sqlite()

# Step 2: Run legacy template initialization (for backwards compatibility)
init_default_templates()  # إنشاء قوالب الجداول الافتراضية
ensure_default_templates()  # ضمان وجود القوالب الافتراضية (للترقية)


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





# ==================== Main Window Class ====================
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

        # تهيئة معالجات الأحداث - Initialize Event Handlers
        self.telegram_handlers = TelegramHandlers(self)
        self.update_handlers = UpdateHandlers(self, current_version="1.0.0")
        self.job_handlers = JobHandlers(self)

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
        """
        تطبيق الثيم على التطبيق
        Apply theme to the application
        
        المعاملات / Args:
            theme: اسم الثيم ('dark' أو 'light') - Theme name ('dark' or 'light')
            announce: إظهار إشعار بتطبيق الثيم - Show notification when applying theme
        """
        self.theme = "dark" if theme == "dark" else "light"
        app = QApplication.instance()
        
        # محاولة تطبيق الثيم باستخدام qdarktheme إن كان متاحاً
        # Try to apply theme using qdarktheme if available
        css = ""
        if HAS_QDARKTHEME and qdarktheme is not None:
            try:
                css = qdarktheme.load_stylesheet(self.theme)
            except Exception as e:
                # إذا فشل تطبيق الثيم، استخدم الثيم الافتراضي
                # If theme application fails, use default theme
                log_warning(f'فشل تحميل qdarktheme stylesheet: {e}')
                css = ""
        
        # إذا لم يتم تحميل CSS من qdarktheme، استخدم fallback يدوي
        # If CSS was not loaded from qdarktheme, use manual fallback
        if not css:
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
            app.setStyleSheet(css + DARK_THEME_CUSTOM)
        else:
            # للوضع الفاتح، نستخدم الستايل الفاتح فقط (بدون DARK_THEME_CUSTOM الداكن)
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

        # تبويب الإعدادات المتقدمة - Settings Tab
        # إضافة QScrollArea لدعم التمرير بعجلة الماوس (Issue #2)
        settings_tab_container = QWidget()
        settings_tab_layout = QVBoxLayout(settings_tab_container)
        settings_tab_layout.setContentsMargins(0, 0, 0, 0)

        # إنشاء منطقة التمرير
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        settings_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        settings_scroll.setFrameShape(QFrame.NoFrame)

        # استخدام SettingsTab الجديد
        self.settings_tab = SettingsTab(self)
        settings_scroll.setWidget(self.settings_tab)
        settings_tab_layout.addWidget(settings_scroll)

        if HAS_QTAWESOME:
            self.mode_tabs.addTab(settings_tab_container, get_icon(ICONS['settings'], ICON_COLORS.get('settings')), 'إعدادات')
        else:
            self.mode_tabs.addTab(settings_tab_container, 'إعدادات')

        self.mode_tabs.currentChanged.connect(self._on_mode_tab_changed)
        
        # Connect settings tab signals
        self.settings_tab.settings_changed.connect(self._on_settings_tab_changed)
        self.settings_tab.log_message.connect(self._log_append)
        self.settings_tab.telegram_test_result.connect(self._update_telegram_test_result)
        self.settings_tab.update_check_finished.connect(self._finish_update_check)
        # Connect update button to run updates
        self.settings_tab.update_all_btn.clicked.connect(self._run_updates_from_tab)
        
        # Load settings into settings tab
        self.settings_tab.set_settings({
            'validate_videos': self.validate_videos,
            'internet_check_enabled': self.internet_check_enabled,
            'telegram_enabled': self.telegram_enabled,
            'telegram_bot_token': self.telegram_bot_token,
            'telegram_chat_id': self.telegram_chat_id,
            'telegram_notify_success': self.telegram_notify_success,
            'telegram_notify_errors': self.telegram_notify_errors,
        })
        
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
        dialog = TokenManagementDialog(
            self,
            get_all_app_tokens_func=get_all_app_tokens,
            save_app_token_func=save_app_token,
            delete_app_token_func=delete_app_token
        )
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

    def start_scheduler(self):
        """
        تشغيل المجدول - Start the scheduler threads.
        
        This method starts the scheduler threads for video, story, and reels jobs.
        It prefers delegating to scheduler_ui.start_scheduler() if available,
        otherwise uses the direct implementation for backward compatibility.
        """
        # Check if scheduler_ui has a start_scheduler method (future compatibility)
        if hasattr(self.scheduler_ui, 'start_scheduler') and callable(getattr(self.scheduler_ui, 'start_scheduler', None)):
            self.scheduler_ui.start_scheduler()
            return
        
        # Fallback: Direct implementation for starting scheduler threads
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
        """
        إيقاف المجدول - Stop the scheduler threads.
        
        This method stops all running scheduler threads.
        It prefers delegating to scheduler_ui.stop_scheduler() if available,
        otherwise uses the direct implementation for backward compatibility.
        """
        # Check if scheduler_ui has a stop_scheduler method (future compatibility)
        if hasattr(self.scheduler_ui, 'stop_scheduler') and callable(getattr(self.scheduler_ui, 'stop_scheduler', None)):
            self.scheduler_ui.stop_scheduler()
            return
        
        # Fallback: Direct implementation for stopping scheduler threads
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

    def _run_updates_from_tab(self):
        """Run updates requested from settings tab"""
        self._available_updates = self.settings_tab.get_available_updates()
        self._run_updates()
    
    def _on_settings_tab_changed(self):
        """معالج تغيير إعدادات من تبويب الإعدادات"""
        # Get settings from the tab
        settings = self.settings_tab.get_settings()
        
        # Update main window attributes
        self.validate_videos = settings['validate_videos']
        self.internet_check_enabled = settings['internet_check_enabled']
        self.telegram_enabled = settings['telegram_enabled']
        self.telegram_bot_token = settings['telegram_bot_token']
        self.telegram_chat_id = settings['telegram_chat_id']
        self.telegram_notify_success = settings['telegram_notify_success']
        self.telegram_notify_errors = settings['telegram_notify_errors']
        
        # تحديث مثيل TelegramNotifier
        telegram_notifier.enabled = self.telegram_enabled
        telegram_notifier.bot_token = self.telegram_bot_token
        telegram_notifier.chat_id = self.telegram_chat_id
        telegram_notifier.notify_success = self.telegram_notify_success
        telegram_notifier.notify_errors = self.telegram_notify_errors
        
        # Save settings
        self._save_settings()
    
    def _update_telegram_test_result(self, success: bool, message: str):
        """تحديث نتيجة اختبار Telegram - delegates to SettingsTab"""
        # The SettingsTab has its own handler connected to its own signal
        # This is just a stub for any legacy code that might still use the old signal
        pass
    
    def _finish_update_check(self):
        """إنهاء عملية التحقق من التحديثات وتحديث الواجهة - delegates to SettingsTab"""
        # The actual work is done in SettingsTab's _finish_update_check
        # This is just a passthrough since the signal is connected here
        pass
    
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

