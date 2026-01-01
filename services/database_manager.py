"""
وحدة إدارة قاعدة البيانات - Database Manager Module

هذه الوحدة توفر فئة DatabaseManager للتعامل مع قاعدة بيانات SQLite
بشكل موحد مع دعم:
- اتصال مستمر واحد مع وضع WAL للأداء الأفضل
- نظام ترحيل تلقائي للهيكل
- إدراج القوالب الافتراضية
- تسجيل مفصل لجميع عمليات قاعدة البيانات

# TODO: Future improvements
# - UI separation: Move all database operations to background threads
# - Worker threads: Implement async database operations
# - Configuration management: Add support for external config files
"""

import os
import sys
import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional, List, Tuple, Any

from core.logger import log_info, log_error, log_warning, log_debug


# ==================== Constants ====================

APP_DATA_FOLDER = "Page management"

# [DB] قائمة جميع أيام الأسبوع للقوالب الافتراضية
ALL_WEEKDAYS = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"]

# Default schedule templates to insert if table is empty
# [DB] تم تحديث القوالب لتشمل عمود days مع جميع أيام الأسبوع
DEFAULT_SCHEDULE_TEMPLATES = [
    {
        'name': 'default',
        'times': '["08:00","12:00","18:00","22:00"]',
        'days': json.dumps(ALL_WEEKDAYS)
    },
    {
        'name': 'morning',
        'times': '["06:00","07:00","08:00","09:00"]',
        'days': json.dumps(ALL_WEEKDAYS)
    },
    {
        'name': 'night',
        'times': '["20:00","22:00","00:00"]',
        'days': json.dumps(ALL_WEEKDAYS)
    },
    {
        'name': 'heavy',
        'times': '["06:00","07:00","08:00","09:00","12:00","15:00","18:00","22:00"]',
        'days': json.dumps(ALL_WEEKDAYS)
    }
]


def _get_appdata_folder() -> Path:
    """
    Get the application data folder path.
    
    Returns:
        Path to AppData/Roaming (Windows) or ~/.config (Linux/Mac)
    """
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            return Path(appdata) / APP_DATA_FOLDER
    # Fallback for other systems
    home = Path.home()
    return home / '.config' / APP_DATA_FOLDER


def _get_database_file() -> Path:
    """Get the path to the SQLite database file."""
    folder = _get_appdata_folder()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "page_management.db"


class DatabaseManager:
    """
    Unified database manager for SQLite operations.
    
    Provides:
    - Single persistent connection with WAL mode
    - Thread-safe operations
    - Automatic schema migrations
    - Default template insertion
    - Detailed logging with [DB] prefix
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database manager.
        
        Args:
            db_path: Optional path to the database file.
                     If not provided, uses the default application database path.
        """
        if db_path is None:
            self._db_path = str(_get_database_file())
        else:
            self._db_path = str(db_path)
        
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        
        # Open the connection
        self._connect()
    
    def _connect(self):
        """
        Open the database connection with WAL mode for better concurrency.
        """
        try:
            log_info(f"[DB] Opening database connection: {self._db_path}")
            
            # Ensure the directory exists
            db_dir = os.path.dirname(self._db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            self._conn = sqlite3.connect(
                self._db_path,
                check_same_thread=False,  # Allow multi-threaded access
                timeout=30.0  # Wait up to 30 seconds for locks
            )
            
            # Enable WAL mode for better concurrency
            self._conn.execute("PRAGMA journal_mode=WAL;")
            
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys=ON;")
            
            log_info("[DB] Database connection established with WAL mode")
            
        except sqlite3.Error as e:
            log_error(f"[DB] Failed to open database connection: {e}")
            raise
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> sqlite3.Cursor:
        """
        Execute a single SQL statement.
        
        Args:
            sql: The SQL statement to execute
            params: Optional tuple of parameters for the SQL statement
        
        Returns:
            The cursor after executing the statement
        """
        with self._lock:
            if self._conn is None:
                self._connect()
            
            try:
                cursor = self._conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                self._conn.commit()
                return cursor
            except sqlite3.Error as e:
                log_error(f"[DB] SQL execution failed: {e}")
                log_error(f"[DB] SQL: {sql}")
                raise
    
    def executemany(self, sql: str, params_list: List[Tuple]) -> sqlite3.Cursor:
        """
        Execute SQL with multiple parameter sets.
        
        Args:
            sql: The SQL statement to execute
            params_list: List of parameter tuples
        
        Returns:
            The cursor after executing the statements
        """
        with self._lock:
            if self._conn is None:
                self._connect()
            
            try:
                cursor = self._conn.cursor()
                cursor.executemany(sql, params_list)
                self._conn.commit()
                return cursor
            except sqlite3.Error as e:
                log_error(f"[DB] SQL executemany failed: {e}")
                log_error(f"[DB] SQL: {sql}")
                raise
    
    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Tuple]:
        """
        Execute SQL and fetch one result.
        
        Args:
            sql: The SQL statement to execute
            params: Optional tuple of parameters
        
        Returns:
            A single row or None
        """
        with self._lock:
            if self._conn is None:
                self._connect()
            
            try:
                cursor = self._conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                return cursor.fetchone()
            except sqlite3.Error as e:
                log_error(f"[DB] SQL fetchone failed: {e}")
                raise
    
    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """
        Execute SQL and fetch all results.
        
        Args:
            sql: The SQL statement to execute
            params: Optional tuple of parameters
        
        Returns:
            List of rows
        """
        with self._lock:
            if self._conn is None:
                self._connect()
            
            try:
                cursor = self._conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                return cursor.fetchall()
            except sqlite3.Error as e:
                log_error(f"[DB] SQL fetchall failed: {e}")
                raise
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.
        
        Args:
            table_name: Name of the table to check
        
        Returns:
            True if the table exists, False otherwise
        """
        result = self.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return result is not None
    
    def get_table_columns(self, table_name: str) -> List[str]:
        """
        Get list of column names for a table using PRAGMA table_info.
        
        Args:
            table_name: Name of the table
        
        Returns:
            List of column names
        """
        # Validate table name to prevent SQL injection
        # Only allow alphanumeric characters and underscores
        if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
            log_error(f"[DB] Invalid table name: {table_name}")
            return []
        
        with self._lock:
            if self._conn is None:
                self._connect()
            
            try:
                cursor = self._conn.cursor()
                # PRAGMA doesn't support parameterized queries.
                # SQL injection is prevented by table name validation above (alphanumeric + underscore only).
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
                return [col[1] for col in columns]
            except sqlite3.Error as e:
                log_error(f"[DB] Failed to get columns for table {table_name}: {e}")
                return []
    
    def _add_column_if_missing(self, table_name: str, column_name: str, 
                                column_def: str, columns: List[str],
                                update_sql: Optional[str] = None,
                                update_params: Optional[Tuple] = None) -> bool:
        """
        Helper method to add a column if it doesn't exist.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column to add
            column_def: Column definition (e.g., "TEXT DEFAULT '[]'")
            columns: Current list of column names
            update_sql: Optional SQL to run after adding column (for updating existing rows)
            update_params: Optional tuple of parameters for the update SQL (for parameterized queries)
        
        Returns:
            True if column was added or already exists, False on error
        
        Note:
            table_name and column_name are validated to contain only alphanumeric
            characters and underscores to prevent SQL injection.
        """
        if column_name in columns:
            log_debug(f"[DB] Column '{column_name}' already exists")
            return True
        
        # Validate table and column names (alphanumeric + underscore only)
        if not table_name or not all(c.isalnum() or c == '_' for c in table_name):
            log_error(f"[DB] Invalid table name: {table_name}")
            return False
        if not column_name or not all(c.isalnum() or c == '_' for c in column_name):
            log_error(f"[DB] Invalid column name: {column_name}")
            return False
        
        log_info(f"[DB] Column '{column_name}' missing from {table_name} - adding it")
        try:
            self.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def};")
            log_info(f"[DB] Migration complete: Added '{column_name}' column")
            
            if update_sql:
                self.execute(update_sql, update_params)
                log_info(f"[DB] Updated existing rows for '{column_name}' column")
            
            return True
        except sqlite3.Error as e:
            log_error(f"[DB] Failed to add '{column_name}' column: {e}")
            if "no column named" in str(e).lower():
                log_error(f"[DB] Table schema issue - column '{column_name}' migration failed")
            raise
    
    def _migrate_legacy_schedule_data_column(self, columns: List[str]) -> bool:
        """
        Handle migration from legacy schema that had a 'schedule_data' column.
        
        Old schema had a NOT NULL 'schedule_data' column that stored JSON data.
        This method recreates the table without that column while preserving data.
        
        Args:
            columns: Current list of column names in schedule_templates table
        
        Returns:
            True if migration was successful or not needed, False on error
        """
        if 'schedule_data' not in columns:
            # No legacy column, nothing to do
            return True
        
        log_info("[DB] Detected legacy 'schedule_data' column - starting migration")
        
        try:
            # Define the new schema columns
            all_days_json = json.dumps(ALL_WEEKDAYS)
            
            # Step 1: Create a new table with correct schema
            self.execute(f'''
                CREATE TABLE IF NOT EXISTS schedule_templates_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    times TEXT DEFAULT '[]',
                    days TEXT DEFAULT '{all_days_json}',
                    random_offset INTEGER DEFAULT 15,
                    is_default INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            log_debug("[DB] Created temporary table schedule_templates_new")
            
            # Step 2: Copy data from old table, mapping old columns to new ones
            # We need to handle the case where old columns might not exist
            old_columns = set(columns)
            
            # Build the INSERT statement dynamically based on available columns
            select_parts = ['id', 'name']
            
            # Handle times column - might be in schedule_data JSON or as separate column
            if 'times' in old_columns:
                select_parts.append('times')
            else:
                select_parts.append("'[]'")  # Default empty JSON array string
            
            # Handle days column
            if 'days' in old_columns:
                select_parts.append('days')
            else:
                select_parts.append(f"'{all_days_json}'")
            
            # Handle random_offset column
            if 'random_offset' in old_columns:
                select_parts.append('random_offset')
            else:
                select_parts.append('15')
            
            # Handle is_default column
            if 'is_default' in old_columns:
                select_parts.append('is_default')
            else:
                select_parts.append('0')
            
            # Handle created_at column
            if 'created_at' in old_columns:
                select_parts.append('created_at')
            else:
                select_parts.append('CURRENT_TIMESTAMP')
            
            select_clause = ', '.join(select_parts)
            
            self.execute(f'''
                INSERT INTO schedule_templates_new (id, name, times, days, random_offset, is_default, created_at)
                SELECT {select_clause}
                FROM schedule_templates;
            ''')
            log_debug("[DB] Copied data to new table")
            
            # Step 3: Drop the old table
            self.execute('DROP TABLE schedule_templates;')
            log_debug("[DB] Dropped old schedule_templates table")
            
            # Step 4: Rename the new table
            self.execute('ALTER TABLE schedule_templates_new RENAME TO schedule_templates;')
            log_info("[DB] Migration complete: Removed legacy 'schedule_data' column")
            
            return True
            
        except sqlite3.Error as e:
            log_error(f"[DB] Failed to migrate legacy schedule_data column: {e}")
            # Try to clean up the temporary table if it exists
            try:
                self.execute('DROP TABLE IF EXISTS schedule_templates_new;')
            except sqlite3.Error:
                pass
            return False
    
    def ensure_migrations(self):
        """
        Run all necessary migrations automatically.
        
        This method:
        1. Checks if schedule_templates table exists
        2. If exists with legacy 'schedule_data' column, migrates to new schema
        3. If exists but missing required columns, adds them
        4. If table doesn't exist, creates it with correct schema
        5. Logs each migration step with [DB] prefix
        """
        log_info("[DB] Checking database schema...")
        
        # Check schedule_templates table
        if self.table_exists('schedule_templates'):
            log_info("[DB] Table 'schedule_templates' exists")
            
            # Get current columns
            columns = self.get_table_columns('schedule_templates')
            log_debug(f"[DB] Current columns: {columns}")
            
            # First, handle legacy 'schedule_data' column migration
            # This column had a NOT NULL constraint that causes errors
            if 'schedule_data' in columns:
                if self._migrate_legacy_schedule_data_column(columns):
                    # Re-fetch columns after migration
                    columns = self.get_table_columns('schedule_templates')
                    log_debug(f"[DB] Updated columns after migration: {columns}")
            
            # Add missing columns using helper method
            self._add_column_if_missing(
                'schedule_templates', 'times', "TEXT DEFAULT '[]'", columns
            )
            
            # For 'days' column, we need to update existing rows with all weekdays
            all_days_json = json.dumps(ALL_WEEKDAYS)
            self._add_column_if_missing(
                'schedule_templates', 'days', f"TEXT DEFAULT '{all_days_json}'", columns,
                update_sql="UPDATE schedule_templates SET days = ? WHERE days IS NULL OR days = '[]';",
                update_params=(all_days_json,)
            )
            
            self._add_column_if_missing(
                'schedule_templates', 'random_offset', "INTEGER DEFAULT 15", columns
            )
            
            self._add_column_if_missing(
                'schedule_templates', 'is_default', "INTEGER DEFAULT 0", columns
            )
            
            # For 'created_at', SQLite doesn't allow CURRENT_TIMESTAMP as default for ALTER TABLE
            self._add_column_if_missing(
                'schedule_templates', 'created_at', "TIMESTAMP", columns,
                update_sql="UPDATE schedule_templates SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL;"
            )
        else:
            # Create the table with correct schema
            # [DB] إنشاء الجدول مع عمود days بقيمة افتراضية جميع الأيام
            log_info("[DB] Table 'schedule_templates' does not exist - creating it")
            try:
                all_days_json = json.dumps(ALL_WEEKDAYS)
                self.execute(f'''
                    CREATE TABLE IF NOT EXISTS schedule_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        times TEXT DEFAULT '[]',
                        days TEXT DEFAULT '{all_days_json}',
                        random_offset INTEGER DEFAULT 15,
                        is_default INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')
                log_info("[DB] schedule_templates table created with all required columns (including days, random_offset, is_default)")
            except sqlite3.Error as e:
                log_error(f"[DB] Failed to create schedule_templates table: {e}")
                log_error(f"[DB] This may cause 'table schedule_templates has no column named days' errors")
                raise
        
        # Check app_tokens table - إنشاء جدول التوكينات إذا لم يكن موجوداً
        if not self.table_exists('app_tokens'):
            log_info("[DB] Table 'app_tokens' does not exist - creating it")
            try:
                self.execute('''
                    CREATE TABLE IF NOT EXISTS app_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        app_name TEXT NOT NULL,
                        app_id TEXT NOT NULL,
                        app_secret TEXT,
                        short_lived_token TEXT,
                        long_lived_token TEXT,
                        token_expires_at TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')
                log_info("[DB] app_tokens table created with all required columns")
            except sqlite3.Error as e:
                log_error(f"[DB] Failed to create app_tokens table: {e}")
                raise
        else:
            log_info("[DB] Table 'app_tokens' exists")
        
        log_info("[DB] Schema migration complete")
    
    def ensure_default_templates(self, templates_list: Optional[List[dict]] = None):
        """
        Insert default templates only if the table is empty.
        
        [DB] تم تحديث الدالة لتدعم عمود days, random_offset, is_default
        
        Args:
            templates_list: Optional list of template dictionaries with 'name', 'times', 'days',
                           'random_offset', and 'is_default' keys.
                           If not provided, uses DEFAULT_SCHEDULE_TEMPLATES.
        """
        if templates_list is None:
            templates_list = DEFAULT_SCHEDULE_TEMPLATES
        
        # Check if table has any rows
        result = self.fetchone("SELECT COUNT(*) FROM schedule_templates")
        count = result[0] if result else 0
        
        if count > 0:
            log_debug(f"[DB] schedule_templates already has {count} templates, skipping default insertion")
            return
        
        log_info("[DB] Inserting default schedule templates...")
        
        try:
            for idx, template in enumerate(templates_list):
                name = template.get('name')
                times = template.get('times', '[]')
                days = template.get('days', json.dumps(ALL_WEEKDAYS))
                random_offset = template.get('random_offset', 15)
                # First template is default by convention
                is_default = template.get('is_default', idx == 0)
                
                # Ensure times is a string
                if isinstance(times, list):
                    times = json.dumps(times)
                
                # [DB] تأكد من أن days سلسلة JSON
                if isinstance(days, list):
                    days = json.dumps(days)
                
                self.execute(
                    "INSERT OR IGNORE INTO schedule_templates (name, times, days, random_offset, is_default) VALUES (?, ?, ?, ?, ?)",
                    (name, times, days, random_offset, 1 if is_default else 0)
                )
            
            log_info(f"[DB] Default schedule templates inserted ({len(templates_list)} templates)")
        except sqlite3.Error as e:
            log_error(f"[DB] Failed to insert default templates: {e}")
            if "no column named days" in str(e).lower():
                log_error(f"[DB] The 'days' column is missing from schedule_templates. Run ensure_migrations() first.")
            raise
    
    # ==================== [DB] دوال إدارة قوالب الجدولة ====================
    
    def get_schedule_templates(self) -> List[dict]:
        """
        [DB] الحصول على قائمة جميع قوالب الجدولة.
        
        Returns:
            قائمة من القواميس تحتوي على (id, name, times[], days[], random_offset, is_default, created_at)
        """
        try:
            rows = self.fetchall(
                "SELECT id, name, times, days, random_offset, is_default, created_at FROM schedule_templates ORDER BY is_default DESC, id"
            )
            
            templates = []
            for row in rows:
                # [DB] التعامل مع حالات days الفارغة للتوافق مع الإصدارات السابقة
                days_value = row[3]
                if days_value and days_value != '[]':
                    try:
                        days = json.loads(days_value)
                    except json.JSONDecodeError:
                        days = ALL_WEEKDAYS
                else:
                    days = ALL_WEEKDAYS
                
                template = {
                    'id': row[0],
                    'name': row[1],
                    'times': json.loads(row[2]) if row[2] else [],
                    'days': days,
                    'random_offset': row[4] if row[4] is not None else 15,
                    'is_default': bool(row[5]) if row[5] is not None else False,
                    'created_at': row[6]
                }
                templates.append(template)
            
            log_debug(f"[DB] Retrieved {len(templates)} schedule templates")
            return templates
        except sqlite3.Error as e:
            log_error(f"[DB] خطأ في قاعدة البيانات عند جلب القوالب: {e}")
            # [DB] Log specific error for missing 'days' column
            if "no column named days" in str(e).lower():
                log_error(f"[DB] The 'days' column is missing from schedule_templates table. Run ensure_migrations() to fix.")
            return []
        except json.JSONDecodeError as e:
            log_error(f"[DB] خطأ في تحليل JSON للقوالب: {e}")
            return []
    
    def get_template_by_id(self, template_id: int) -> Optional[dict]:
        """
        [DB] الحصول على قالب جدولة بواسطة المعرف.
        
        Args:
            template_id: معرف القالب
        
        Returns:
            قاموس يحتوي على بيانات القالب أو None إذا لم يُعثر عليه
        """
        try:
            row = self.fetchone(
                "SELECT id, name, times, days, random_offset, is_default, created_at FROM schedule_templates WHERE id = ?",
                (template_id,)
            )
            
            if row is None:
                log_debug(f"[DB] Template with id {template_id} not found")
                return None
            
            # [DB] التعامل مع حالات days الفارغة للتوافق مع الإصدارات السابقة
            days_value = row[3]
            if days_value and days_value != '[]':
                try:
                    days = json.loads(days_value)
                except json.JSONDecodeError:
                    days = ALL_WEEKDAYS
            else:
                days = ALL_WEEKDAYS
            
            template = {
                'id': row[0],
                'name': row[1],
                'times': json.loads(row[2]) if row[2] else [],
                'days': days,
                'random_offset': row[4] if row[4] is not None else 15,
                'is_default': bool(row[5]) if row[5] is not None else False,
                'created_at': row[6]
            }
            
            log_debug(f"[DB] Retrieved template: {template['name']}")
            return template
        except sqlite3.Error as e:
            log_error(f"[DB] خطأ في قاعدة البيانات عند جلب القالب {template_id}: {e}")
            if "no column named days" in str(e).lower():
                log_error(f"[DB] The 'days' column is missing. Run ensure_migrations() to fix.")
            return None
        except json.JSONDecodeError as e:
            log_error(f"[DB] خطأ في تحليل JSON للقالب {template_id}: {e}")
            return None
    
    def save_schedule_template(
        self, 
        name: str, 
        times_list: List[str], 
        days_list: List[str], 
        template_id: Optional[int] = None,
        random_offset: int = 15,
        is_default: bool = False
    ) -> Optional[int]:
        """
        [DB] حفظ قالب جدولة (إضافة جديد أو تعديل موجود).
        
        Args:
            name: اسم القالب
            times_list: قائمة الأوقات (مثل ["08:00", "12:00", "18:00"])
            days_list: قائمة الأيام (مثل ["sat", "sun", "mon"])
            template_id: معرف القالب للتعديل (None للإضافة الجديدة)
            random_offset: التوزيع العشوائي بالدقائق (افتراضي 15)
            is_default: هل هذا القالب الافتراضي (افتراضي False)
        
        Returns:
            معرف القالب المحفوظ أو None في حالة الفشل
        """
        try:
            # تحويل القوائم إلى JSON
            times_json = json.dumps(times_list) if isinstance(times_list, list) else times_list
            days_json = json.dumps(days_list) if isinstance(days_list, list) else days_list
            
            if template_id is not None:
                # تحديث قالب موجود
                # التحقق من عدم وجود قالب آخر بنفس الاسم (باستثناء القالب الحالي)
                existing = self.fetchone(
                    "SELECT id FROM schedule_templates WHERE name = ? AND id != ?",
                    (name, template_id)
                )
                if existing:
                    log_warning(f"[DB] الاسم مستخدم مسبقاً بواسطة قالب آخر: {name}")
                    return None
                
                self.execute(
                    "UPDATE schedule_templates SET name = ?, times = ?, days = ?, random_offset = ?, is_default = ? WHERE id = ?",
                    (name, times_json, days_json, random_offset, 1 if is_default else 0, template_id)
                )
                log_info(f"[DB] تم تحديث القالب: {name} (id: {template_id})")
                return template_id
            else:
                # إضافة قالب جديد
                # التحقق من عدم وجود قالب بنفس الاسم
                existing = self.fetchone(
                    "SELECT id FROM schedule_templates WHERE name = ?",
                    (name,)
                )
                if existing:
                    log_warning(f"[DB] الاسم مستخدم مسبقاً: {name}")
                    return None
                
                cursor = self.execute(
                    "INSERT INTO schedule_templates (name, times, days, random_offset, is_default) VALUES (?, ?, ?, ?, ?)",
                    (name, times_json, days_json, random_offset, 1 if is_default else 0)
                )
                new_id = cursor.lastrowid
                log_info(f"[DB] تم إضافة قالب جديد: {name} (id: {new_id})")
                return new_id
        except sqlite3.IntegrityError as e:
            log_error(f"[DB] خطأ في قاعدة البيانات عند حفظ القالب: اسم القالب '{name}' موجود مسبقاً")
            return None
        except sqlite3.Error as e:
            log_error(f"[DB] خطأ في قاعدة البيانات عند حفظ القالب: {e}")
            if "no column named days" in str(e).lower():
                log_error(f"[DB] The 'days' column is missing. Run ensure_migrations() to fix.")
            return None
    
    def delete_schedule_template(self, template_id: int) -> bool:
        """
        [DB] حذف قالب جدولة.
        
        Args:
            template_id: معرف القالب المراد حذفه
        
        Returns:
            True إذا تم الحذف بنجاح، False خلاف ذلك
        """
        try:
            cursor = self.execute(
                "DELETE FROM schedule_templates WHERE id = ?",
                (template_id,)
            )
            
            if cursor.rowcount > 0:
                log_info(f"[DB] تم حذف القالب بمعرف: {template_id}")
                return True
            else:
                log_warning(f"[DB] لم يتم العثور على قالب بمعرف: {template_id}")
                return False
        except sqlite3.Error as e:
            log_error(f"[DB] خطأ في قاعدة البيانات عند حذف القالب: {e}")
            return False
    
    def close(self):
        """Close the database connection."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                    log_debug("[DB] Database connection closed")
                except sqlite3.Error as e:
                    log_error(f"[DB] Error closing connection: {e}")
                finally:
                    self._conn = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
    
    def __del__(self):
        """Destructor to ensure connection is closed."""
        try:
            self.close()
        except Exception:
            pass


# ==================== Global Instance ====================

# Global database manager instance (singleton pattern)
_global_db_manager: Optional[DatabaseManager] = None
_db_init_lock = threading.Lock()


def get_database_manager() -> DatabaseManager:
    """
    Get the global database manager instance (singleton).
    
    Thread-safe initialization.
    
    Returns:
        DatabaseManager instance
    """
    global _global_db_manager
    
    if _global_db_manager is None:
        with _db_init_lock:
            # Double-check locking pattern
            if _global_db_manager is None:
                _global_db_manager = DatabaseManager()
    
    return _global_db_manager


def initialize_database():
    """
    Initialize the database, run migrations, and insert default templates.
    
    This should be called at application startup before any UI loads.
    """
    log_info("[DB] Initializing database...")
    db = get_database_manager()
    db.ensure_migrations()
    db.ensure_default_templates()
    log_info("[DB] Database initialization complete")
    return db
