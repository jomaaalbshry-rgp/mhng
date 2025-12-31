"""
الخدمات - طبقة الخدمات والـ APIs
Services - Services and APIs layer
"""

# استيراد الخدمات - Import services
from .facebook_api import FacebookAPIService
from .upload_service import UploadService
from .database_manager import DatabaseManager, get_database_manager, initialize_database
from .token_manager import (
    TokenManager, get_pages, PageFetchWorker, 
    TokenExchangeWorker, AllPagesFetchWorker, get_token_manager
)
from .updater import *

# استيراد وحدة الوصول إلى البيانات - Import data access module
from .data_access import (
    get_settings_file, get_jobs_file, get_database_file, migrate_old_files,
    save_hashtag_group, get_hashtag_groups, delete_hashtag_group,
    is_within_working_hours, calculate_time_to_working_hours_start,
    log_upload, get_upload_stats, reset_upload_stats, generate_text_chart,
    init_default_templates, ensure_default_templates,
    get_all_templates, get_template_by_id, save_template, delete_template,
    get_default_template, set_default_template, get_schedule_times_for_template,
    migrate_json_to_sqlite
)

# تصدير الخدمات - Export services
__all__ = [
    'FacebookAPIService',
    'UploadService',
    'DatabaseManager',
    'get_database_manager',
    'initialize_database',
    'TokenManager',
    'get_pages',
    'PageFetchWorker',
    'TokenExchangeWorker',
    'AllPagesFetchWorker',
    'get_token_manager',
    # Data access functions
    'get_settings_file',
    'get_jobs_file', 
    'get_database_file',
    'migrate_old_files',
    'save_hashtag_group',
    'get_hashtag_groups',
    'delete_hashtag_group',
    'is_within_working_hours',
    'calculate_time_to_working_hours_start',
    'log_upload',
    'get_upload_stats',
    'reset_upload_stats',
    'generate_text_chart',
    'init_default_templates',
    'ensure_default_templates',
    'get_all_templates',
    'get_template_by_id',
    'save_template',
    'delete_template',
    'get_default_template',
    'set_default_template',
    'get_schedule_times_for_template',
    'migrate_json_to_sqlite',
]
