"""
وحدة الوصول إلى البيانات - Data Access Module

This module provides functions for accessing and managing data in the database.
Moved from ui/main_window.py as part of Phase 6 refactoring.

Functions moved:
- Hashtag groups management
- Template management  
- Upload statistics
- Working hours (legacy)
- Settings file paths
"""

import os
import sys
import json
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

from core.logger import log_info, log_error, log_warning, log_debug


# ==================== Path Management ====================

APP_DATA_FOLDER = "Page management"


def _get_appdata_folder() -> Path:
    """
    الحصول على مسار مجلد AppData للتطبيق.
    Get the application data folder path.

    العائد / Returns:
        مسار المجلد في AppData/Roaming (ويندوز) أو ~/.config (لينكس/ماك)
        Path to AppData/Roaming (Windows) or ~/.config (Linux/Mac)
    """
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            return Path(appdata) / APP_DATA_FOLDER
    # Fallback لأنظمة أخرى
    home = Path.home()
    return home / '.config' / APP_DATA_FOLDER


def get_settings_file() -> Path:
    """الحصول على مسار ملف الإعدادات في AppData."""
    folder = _get_appdata_folder()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "fb_scheduler_settings.json"


def get_jobs_file() -> Path:
    """الحصول على مسار ملف الوظائف في AppData."""
    folder = _get_appdata_folder()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "fb_scheduler_jobs.json"


def get_database_file() -> Path:
    """الحصول على مسار قاعدة بيانات SQLite."""
    folder = _get_appdata_folder()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "page_management.db"


def migrate_old_files():
    """
    ترحيل الملفات القديمة (بجانب exe/السكربت) إلى AppData.
    Migrate old files (next to exe/script) to AppData.

    يتم نسخ الملفات مرة واحدة فقط إذا كانت موجودة في الموقع القديم
    ولم تكن موجودة في الموقع الجديد.
    Files are copied once if they exist in the old location and don't exist in new location.
    """
    # Get script directory (where the script is located)
    import __main__
    if hasattr(__main__, '__file__'):
        script_dir = Path(__main__.__file__).parent.resolve()
    else:
        script_dir = Path.cwd()
    
    old_settings = script_dir / "fb_scheduler_settings.json"
    old_jobs = script_dir / "fb_scheduler_jobs.json"

    new_settings = get_settings_file()
    new_jobs = get_jobs_file()

    # ترحيل ملف الإعدادات
    if old_settings.exists() and not new_settings.exists():
        try:
            shutil.copy2(old_settings, new_settings)
            log_info(f'[Migration] Settings migrated from {old_settings} to {new_settings}')
        except Exception as e:
            log_error(f'[Migration] Failed to migrate settings: {e}')

    # ترحيل ملف الوظائف
    if old_jobs.exists() and not new_jobs.exists():
        try:
            shutil.copy2(old_jobs, new_jobs)
            log_info(f'[Migration] Jobs migrated from {old_jobs} to {new_jobs}')
        except Exception as e:
            log_error(f'[Migration] Failed to migrate jobs: {e}')


# ==================== Hashtag Groups ====================

def save_hashtag_group(name: str, hashtags: str):
    """حفظ مجموعة هاشتاجات."""
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO hashtag_groups (name, hashtags)
            VALUES (?, ?)
        ''', (name, hashtags))
        conn.commit()
        conn.close()
    except Exception as e:
        log_error(f'[DataAccess] Failed to save hashtag group: {e}')


def get_hashtag_groups() -> list:
    """الحصول على جميع مجموعات الهاشتاجات."""
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        cursor.execute('SELECT name, hashtags FROM hashtag_groups ORDER BY name')
        groups = cursor.fetchall()
        conn.close()
        return groups
    except Exception as e:
        log_error(f'[DataAccess] Failed to get hashtag groups: {e}')
        return []


def delete_hashtag_group(name: str):
    """حذف مجموعة هاشتاجات."""
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        cursor.execute('DELETE FROM hashtag_groups WHERE name = ?', (name,))
        conn.commit()
        conn.close()
    except Exception as e:
        log_error(f'[DataAccess] Failed to delete hashtag group: {e}')


# ==================== Working Hours (Legacy) ====================

def is_within_working_hours(page_id: str = None) -> bool:
    """
    التحقق مما إذا كان الوقت الحالي ضمن ساعات العمل.
    Check if current time is within working hours.

    ملاحظة: تم إزالة نظام ساعات العمل. هذه الدالة تُرجع True دائماً للتوافقية.
    Note: Working hours system removed. This function always returns True for compatibility.
    استخدم نظام قوالب الجداول الذكية بدلاً من ذلك.
    Use smart schedule templates system instead.
    """
    return True  # السماح دائماً - تم إزالة نظام ساعات العمل


def calculate_time_to_working_hours_start(start_time: str, end_time: str) -> int:
    """
    حساب الوقت المتبقي لبداية ساعات العمل (بالثواني).
    Calculate time remaining until working hours start (in seconds).
    
    ملاحظة: تم إزالة نظام ساعات العمل. هذه الدالة تُرجع 0 دائماً للتوافقية.
    Note: Working hours system removed. This function always returns 0 for compatibility.
    
    المعاملات / Args:
        start_time: وقت البداية (مثل "09:00") - Start time (e.g., "09:00")
        end_time: وقت النهاية (مثل "23:00") - End time (e.g., "23:00")
    
    العائد / Returns:
        0 دائماً (تم إزالة النظام) - Always 0 (system removed)
    """
    return 0


# ==================== Upload Statistics ====================

def log_upload(page_id: str, page_name: str, file_path: str, file_name: str,
               upload_type: str = 'video', video_id: str = '', video_url: str = '',
               status: str = 'success', error_message: str = ''):
    """
    تسجيل عملية رفع في قاعدة البيانات.
    Log an upload operation to the database.
    
    المعاملات / Args:
        page_id: معرف الصفحة - Page ID
        page_name: اسم الصفحة - Page name
        file_path: مسار الملف - File path
        file_name: اسم الملف - File name
        upload_type: نوع الرفع ('video', 'story', 'reels') - Upload type
        video_id: معرف الفيديو من فيسبوك - Video ID from Facebook
        video_url: رابط الفيديو - Video URL
        status: الحالة ('success', 'failed') - Status
        error_message: رسالة الخطأ إن وجدت - Error message if any
    """
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO upload_history
            (page_id, page_name, file_path, file_name, upload_type,
             video_id, video_url, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (page_id, page_name, file_path, file_name, upload_type,
              video_id, video_url, status, error_message))
        conn.commit()
        conn.close()
    except Exception as e:
        log_error(f'[DataAccess] Failed to log upload: {e}')


def get_upload_stats(page_id: str = None, days: int = 30) -> dict:
    """
    الحصول على إحصائيات الرفع.
    Get upload statistics.
    
    المعاملات / Args:
        page_id: معرف الصفحة (None لكل الصفحات) - Page ID (None for all pages)
        days: عدد الأيام الأخيرة - Number of recent days
    
    العائد / Returns:
        قاموس يحتوي على الإحصائيات - Dictionary containing statistics
    """
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        
        # حساب تاريخ البداية
        start_date = datetime.now() - timedelta(days=days)
        start_timestamp = start_date.strftime('%Y-%m-%d %H:%M:%S')
        
        # استعلام أساسي
        if page_id:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    upload_type
                FROM upload_history
                WHERE page_id = ? AND uploaded_at >= ?
                GROUP BY upload_type
            ''', (page_id, start_timestamp))
        else:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    upload_type
                FROM upload_history
                WHERE uploaded_at >= ?
                GROUP BY upload_type
            ''', (start_timestamp,))
        
        results = cursor.fetchall()
        conn.close()
        
        # تنظيم النتائج
        stats = {
            'video': {'total': 0, 'successful': 0, 'failed': 0},
            'story': {'total': 0, 'successful': 0, 'failed': 0},
            'reels': {'total': 0, 'successful': 0, 'failed': 0},
        }
        
        for row in results:
            total, successful, failed, upload_type = row
            if upload_type in stats:
                stats[upload_type] = {
                    'total': total,
                    'successful': successful or 0,
                    'failed': failed or 0
                }
        
        # إضافة المجموع الكلي - Calculate totals before adding 'overall' key
        total_overall = sum(s['total'] for k, s in stats.items() if k != 'overall' and isinstance(s, dict))
        successful_overall = sum(s['successful'] for k, s in stats.items() if k != 'overall' and isinstance(s, dict))
        failed_overall = sum(s['failed'] for k, s in stats.items() if k != 'overall' and isinstance(s, dict))
        
        stats['overall'] = {
            'total': total_overall,
            'successful': successful_overall,
            'failed': failed_overall
        }
        
        return stats
        
    except Exception as e:
        log_error(f'[DataAccess] Failed to get upload stats: {e}')
        return {
            'video': {'total': 0, 'successful': 0, 'failed': 0},
            'story': {'total': 0, 'successful': 0, 'failed': 0},
            'reels': {'total': 0, 'successful': 0, 'failed': 0},
            'overall': {'total': 0, 'successful': 0, 'failed': 0}
        }


def reset_upload_stats():
    """
    إعادة تعيين إحصائيات الرفع (حذف كل السجلات).
    Reset upload statistics (delete all records).
    """
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        cursor.execute('DELETE FROM upload_history')
        conn.commit()
        conn.close()
        log_info('[DataAccess] Upload statistics reset successfully')
    except Exception as e:
        log_error(f'[DataAccess] Failed to reset upload stats: {e}')


def generate_text_chart(data: dict) -> str:
    """
    إنشاء مخطط نصي من البيانات.
    Generate a text chart from data.
    
    المعاملات / Args:
        data: قاموس يحتوي على البيانات - Dictionary containing data
    
    العائد / Returns:
        نص المخطط - Chart text
    """
    if not data:
        return "لا توجد بيانات"
    
    max_value = max(data.values()) if data.values() else 1
    chart_lines = []
    
    for label, value in data.items():
        # حساب عرض الشريط (بحد أقصى 50 حرف)
        bar_width = int((value / max_value) * 50) if max_value > 0 else 0
        bar = '█' * bar_width
        chart_lines.append(f"{label:15s} {bar} {value}")
    
    return '\n'.join(chart_lines)


# ==================== Schedule Templates ====================

# [DB] قائمة أيام الأسبوع بصيغة نصية للتوافق مع database_manager.py
ALL_WEEKDAYS_STR = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]

# القوالب الافتراضية مع إيموجي
DEFAULT_TEMPLATES = [
    {
        'name': '⭐ الافتراضي',
        'times': ['08:00', '12:00', '18:00', '22:00'],
        'days': ALL_WEEKDAYS_STR,
        'is_default': True
    },
    {
        'name': '🌅 صباحي',
        'times': ['06:00', '07:00', '08:00', '09:00'],
        'days': ALL_WEEKDAYS_STR,
        'is_default': False
    },
    {
        'name': '🌙 ليلي',
        'times': ['20:00', '22:00', '00:00'],
        'days': ALL_WEEKDAYS_STR,
        'is_default': False
    },
    {
        'name': '📱 مكثف',
        'times': ['08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
        'days': ALL_WEEKDAYS_STR,
        'is_default': False
    }
]


def _parse_days_from_db(days_raw: str) -> list:
    """
    Parse days value from database, handling both numeric and string formats.

    Args:
        days_raw: Raw days value from database (JSON string or None)

    Returns:
        List of day strings (e.g., ["sat", "sun", "mon", ...])
    """
    if not days_raw:
        return ALL_WEEKDAYS_STR

    try:
        days = json.loads(days_raw)
        # If parsed successfully, return as-is (could be strings or numbers)
        return days if days else ALL_WEEKDAYS_STR
    except json.JSONDecodeError:
        return ALL_WEEKDAYS_STR


def _ensure_schedule_templates_table(cursor):
    """
    التأكد من وجود جدول القوالب (دالة مساعدة لتجنب التكرار).
    Ensure schedule templates table exists (helper function to avoid repetition).

    المعاملات / Args:
        cursor: مؤشر قاعدة البيانات SQLite - SQLite database cursor

    العائد / Returns:
        True إذا نجح الإنشاء أو كان الجدول موجوداً مسبقاً
        True if creation succeeded or table already exists

    الاستثناءات / Exceptions:
        يرمي الاستثناء للأعلى في حالة فشل الإنشاء
        Throws exception upwards if creation fails
    """
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                times TEXT NOT NULL,
                days TEXT DEFAULT '["sat", "sun", "mon", "tue", "wed", "thu", "fri"]',
                random_offset INTEGER DEFAULT 15,
                is_default BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        return True
    except Exception as e:
        log_error(f'[DataAccess] Failed to create schedule_templates table: {e}')
        raise


def init_default_templates():
    """
    إنشاء القوالب الافتراضية إذا لم تكن موجودة.
    Create default templates if they don't exist.

    تقوم هذه الدالة بإنشاء جدول القوالب إذا لم يكن موجوداً،
    ثم تضيف القوالب الافتراضية إذا كان الجدول فارغاً.
    This function creates the templates table if it doesn't exist,
    then adds default templates if the table is empty.

    العائد / Returns:
        True إذا نجحت العملية، False خلاف ذلك
        True if operation succeeded, False otherwise
    """
    try:
        log_debug('[DataAccess] Starting default templates initialization...')
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()

        # التأكد من وجود الجدول
        _ensure_schedule_templates_table(cursor)
        conn.commit()

        # التحقق من وجود قوالب
        cursor.execute('SELECT COUNT(*) FROM schedule_templates')
        count = cursor.fetchone()[0]

        if count == 0:
            log_info('[DataAccess] No templates found - adding default templates...')
            # إضافة القوالب الافتراضية
            for template in DEFAULT_TEMPLATES:
                try:
                    cursor.execute('''
                        INSERT INTO schedule_templates (name, times, days, is_default)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        template['name'],
                        json.dumps(template['times']),
                        json.dumps(template['days']),
                        1 if template['is_default'] else 0
                    ))
                    log_debug(f'[DataAccess] Added template: {template["name"]}')
                except sqlite3.IntegrityError:
                    # القالب موجود بالفعل - تخطي
                    log_debug(f'[DataAccess] Template already exists: {template["name"]}')
                    continue
            log_info(f'[DataAccess] Added {len(DEFAULT_TEMPLATES)} default templates')
        else:
            log_debug(f'[DataAccess] Found {count} existing templates')

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log_error(f'[DataAccess] Failed to initialize default templates: {e}')
        return False


def ensure_default_templates():
    """
    ضمان وجود القوالب الافتراضية في قاعدة البيانات.
    Ensure default templates exist in the database.

    تستخدم هذه الدالة للتأكد من أن القوالب الافتراضية موجودة
    بعد الترقية أو إعادة التثبيت. تضيف القوالب المفقودة فقط
    دون التأثير على القوالب الموجودة.
    This function ensures default templates exist after upgrade or reinstall.
    Adds only missing templates without affecting existing ones.

    العائد / Returns:
        عدد القوالب المضافة - Number of templates added
    """
    added_count = 0
    try:
        log_debug('[DataAccess] Checking for default templates...')
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()

        # التأكد من وجود الجدول
        _ensure_schedule_templates_table(cursor)
        conn.commit()

        # الحصول على أسماء القوالب الموجودة
        cursor.execute('SELECT name FROM schedule_templates')
        existing_names = {row[0] for row in cursor.fetchall()}

        # إضافة القوالب المفقودة فقط
        for template in DEFAULT_TEMPLATES:
            if template['name'] not in existing_names:
                try:
                    cursor.execute('''
                        INSERT INTO schedule_templates (name, times, days, is_default)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        template['name'],
                        json.dumps(template['times']),
                        json.dumps(template['days']),
                        1 if template['is_default'] else 0
                    ))
                    added_count += 1
                    log_info(f'[DataAccess] Added missing template: {template["name"]}')
                except sqlite3.IntegrityError:
                    # القالب موجود بالفعل (ربما تم إضافته بين الاستعلامين)
                    continue

        conn.commit()
        conn.close()

        if added_count > 0:
            log_info(f'[DataAccess] Added {added_count} missing default templates')

        return added_count
    except Exception as e:
        log_error(f'[DataAccess] Failed to ensure default templates: {e}')
        return 0


def get_all_templates() -> list:
    """
    الحصول على جميع قوالب الجداول.
    Get all schedule templates.

    العائد / Returns:
        قائمة من القواميس تحتوي على بيانات القوالب
        List of dictionaries containing template data
    """
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, times, days, random_offset, is_default, created_at
            FROM schedule_templates
            ORDER BY is_default DESC, name
        ''')
        rows = cursor.fetchall()
        conn.close()

        templates = []
        for row in rows:
            templates.append({
                'id': row[0],
                'name': row[1],
                'times': json.loads(row[2]) if row[2] else [],
                'days': _parse_days_from_db(row[3]),
                'random_offset': row[4] or 15,
                'is_default': bool(row[5]),
                'created_at': row[6]
            })
        return templates
    except sqlite3.Error as e:
        log_error(f'[DataAccess] Database error when fetching templates: {e}')
        if "no column named days" in str(e).lower():
            log_error('[DataAccess] The days column is missing. Run database migrations first.')
        return []
    except Exception as e:
        log_error(f'[DataAccess] Unexpected error when fetching templates: {e}')
        return []


def get_template_by_id(template_id: int) -> Optional[dict]:
    """
    الحصول على قالب بالمعرف.
    Get template by ID.

    المعاملات / Args:
        template_id: معرف القالب - Template ID

    العائد / Returns:
        بيانات القالب أو None - Template data or None
    """
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, times, days, random_offset, is_default
            FROM schedule_templates
            WHERE id = ?
        ''', (template_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'name': row[1],
                'times': json.loads(row[2]) if row[2] else [],
                'days': _parse_days_from_db(row[3]),
                'random_offset': row[4] or 15,
                'is_default': bool(row[5])
            }
        return None
    except sqlite3.Error as e:
        log_error(f'[DataAccess] Database error when fetching template {template_id}: {e}')
        if "no column named days" in str(e).lower():
            log_error('[DataAccess] The days column is missing. Run database migrations first.')
        return None
    except Exception as e:
        log_error(f'[DataAccess] Unexpected error when fetching template {template_id}: {e}')
        return None


def save_template(name: str, times: list, days: list = None, random_offset: int = 15, 
                  template_id: int = None) -> Tuple[bool, Optional[str]]:
    """
    حفظ قالب جديد أو تحديث موجود.
    Save a new template or update existing one.

    المعاملات / Args:
        name: اسم القالب - Template name
        times: قائمة الأوقات (مثل ["08:00", "12:00"]) - List of times
        days: قائمة الأيام - List of days
        random_offset: التوزيع العشوائي بالدقائق - Random offset in minutes
        template_id: معرف القالب للتحديث (None لإنشاء جديد) - Template ID to update (None for new)

    العائد / Returns:
        tuple: (نجاح: bool, رسالة: str) - (success: bool, message: str)
    """
    # Import send_telegram_error locally to avoid circular import
    from core.notifications import NotificationSystem
    notification_system = NotificationSystem.get_instance()
    
    # التحقق من صحة المدخلات
    if not name or not name.strip():
        log_warning('[DataAccess] Attempted to save template without name')
        return (False, 'validation_error')
    if not times or len(times) == 0:
        log_warning('[DataAccess] Attempted to save template without times')
        return (False, 'validation_error')

    # استخدام صيغة الأيام النصية للتوافق
    if days is None:
        days = ALL_WEEKDAYS_STR

    conn = None
    try:
        log_debug(f'[DataAccess] Saving template: {name}')
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()

        # التأكد من وجود الجدول
        try:
            _ensure_schedule_templates_table(cursor)
            conn.commit()
        except sqlite3.Error as e:
            log_error(f'[DataAccess] Failed to create templates table: {e}')
            return (False, 'table_error')

        if template_id is not None:
            # تحديث قالب موجود
            log_debug(f'[DataAccess] Updating template #{template_id}')

            # التحقق من عدم وجود قالب آخر بنفس الاسم
            cursor.execute(
                'SELECT id FROM schedule_templates WHERE name = ? AND id != ?',
                (name.strip(), template_id)
            )
            if cursor.fetchone():
                log_warning(f'[DataAccess] Name already used by another template: {name}')
                return (False, 'duplicate_name')

            cursor.execute('''
                UPDATE schedule_templates
                SET name = ?, times = ?, days = ?, random_offset = ?
                WHERE id = ?
            ''', (name.strip(), json.dumps(times, ensure_ascii=False), 
                  json.dumps(days), random_offset, template_id))

            if cursor.rowcount == 0:
                log_warning(f'[DataAccess] Template #{template_id} not found for update')
                return (False, 'not_found')
        else:
            # إنشاء قالب جديد
            log_debug(f'[DataAccess] Creating new template: {name}')

            # التحقق من عدم وجود قالب بنفس الاسم
            cursor.execute(
                'SELECT id FROM schedule_templates WHERE name = ?',
                (name.strip(),)
            )
            if cursor.fetchone():
                log_warning(f'[DataAccess] Name already used: {name}')
                return (False, 'duplicate_name')

            try:
                cursor.execute('''
                    INSERT INTO schedule_templates (name, times, days, random_offset)
                    VALUES (?, ?, ?, ?)
                ''', (name.strip(), json.dumps(times, ensure_ascii=False), 
                      json.dumps(days), random_offset))
            except sqlite3.IntegrityError as e:
                error_str = str(e).lower()
                if 'unique constraint' in error_str or 'unique' in error_str:
                    log_warning(f'[DataAccess] Name already used: {name}')
                    return (False, 'duplicate_name')
                elif 'not null constraint' in error_str:
                    log_error(f'[DataAccess] Missing required field in templates table - {e}')
                    notification_system.send_error('Database Error', 
                                                   f'Missing required field in templates table: {e}')
                    return (False, 'database_error')
                else:
                    log_error(f'[DataAccess] Database error: {e}')
                    notification_system.send_error('Database Error', 
                                                   f'Error saving template: {e}')
                    return (False, 'database_error')

        conn.commit()
        log_info(f'[DataAccess] Template saved successfully: {name}')
        return (True, None)

    except sqlite3.Error as e:
        log_error(f'[DataAccess] Database error when saving template: {e}')
        if "no column named days" in str(e).lower():
            log_error('[DataAccess] The days column is missing. Run database migrations first.')
        notification_system.send_error('Database Error', 
                                       f'Error saving template "{name}": {e}')
        return (False, 'database_error')
    except Exception as e:
        log_error(f'[DataAccess] Unexpected error when saving template: {e}')
        notification_system.send_error('Unexpected Error', 
                                       f'Error saving template "{name}": {e}')
        return (False, 'unexpected_error')
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def delete_template(template_id: int) -> bool:
    """
    حذف قالب.
    Delete a template.

    المعاملات / Args:
        template_id: معرف القالب - Template ID

    العائد / Returns:
        True إذا نجح الحذف - True if deletion succeeded
    """
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        # لا يمكن حذف القالب الافتراضي
        cursor.execute('SELECT is_default FROM schedule_templates WHERE id = ?', (template_id,))
        row = cursor.fetchone()
        if row and row[0]:
            conn.close()
            log_warning(f'[DataAccess] Cannot delete default template #{template_id}')
            return False  # لا يمكن حذف القالب الافتراضي

        cursor.execute('DELETE FROM schedule_templates WHERE id = ?', (template_id,))
        conn.commit()
        conn.close()
        log_info(f'[DataAccess] Template #{template_id} deleted successfully')
        return True
    except Exception as e:
        log_error(f'[DataAccess] Failed to delete template #{template_id}: {e}')
        return False


def get_default_template() -> dict:
    """
    الحصول على القالب الافتراضي.
    Get the default template.

    العائد / Returns:
        بيانات القالب الافتراضي - Default template data
    """
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, times, days, random_offset, is_default
            FROM schedule_templates
            WHERE is_default = 1
            LIMIT 1
        ''')
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'id': row[0],
                'name': row[1],
                'times': json.loads(row[2]) if row[2] else [],
                'days': json.loads(row[3]) if row[3] else [0, 1, 2, 3, 4, 5, 6],
                'random_offset': row[4] or 15,
                'is_default': bool(row[5])
            }
        # إذا لم يوجد قالب افتراضي، أنشئ القوالب الافتراضية
        init_default_templates()
        return get_default_template()
    except Exception as e:
        log_error(f'[DataAccess] Failed to get default template: {e}')
        return {
            'id': 0, 
            'name': 'الافتراضي', 
            'times': ['08:00', '12:00', '18:00', '22:00'],
            'days': [0, 1, 2, 3, 4, 5, 6], 
            'random_offset': 15, 
            'is_default': True
        }


def set_default_template(template_id: int) -> bool:
    """
    تعيين قالب كافتراضي.
    Set a template as default.

    المعاملات / Args:
        template_id: معرف القالب - Template ID

    العائد / Returns:
        True إذا نجح التعيين - True if setting succeeded
    """
    try:
        conn = sqlite3.connect(str(get_database_file()))
        cursor = conn.cursor()

        # إزالة علامة الافتراضي من جميع القوالب
        cursor.execute('UPDATE schedule_templates SET is_default = 0')

        # تعيين القالب المحدد كافتراضي
        cursor.execute('UPDATE schedule_templates SET is_default = 1 WHERE id = ?', (template_id,))

        conn.commit()
        conn.close()
        log_info(f'[DataAccess] Template #{template_id} set as default')
        return True
    except Exception as e:
        log_error(f'[DataAccess] Failed to set default template #{template_id}: {e}')
        return False


def get_schedule_times_for_template(template_id: int = None) -> list:
    """
    الحصول على أوقات الجدولة من القالب.
    Get schedule times from template.

    المعاملات / Args:
        template_id: معرف القالب (None للحصول على القالب الافتراضي)
                    Template ID (None to get default template)

    العائد / Returns:
        قائمة الأوقات - List of times
    """
    if template_id:
        template = get_template_by_id(template_id)
    else:
        template = get_default_template()

    if template:
        return template.get('times', [])
    return ['08:00', '12:00', '18:00', '22:00']
