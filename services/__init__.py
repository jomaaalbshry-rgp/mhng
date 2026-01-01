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

# استيراد خدمة إدارة التوكينات - Import token service
from .token_service import (
    get_all_app_tokens, save_app_token, delete_app_token,
    exchange_token_for_long_lived, get_all_long_lived_tokens
)

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

# تأخير استيراد upload_helpers لتجنب circular import
# Delay upload_helpers import to avoid circular import using lazy imports
_upload_helpers_cache = {}

def __getattr__(name):
    """استيراد مؤجل للدوال من upload_helpers - Lazy import for upload_helpers functions"""
    if name in ('resumable_upload', 'apply_watermark_to_video', 
                'cleanup_temp_watermark_file', 'upload_video_once', 'move_video_to_uploaded_folder'):
        if name not in _upload_helpers_cache:
            from . import upload_helpers
            _upload_helpers_cache['resumable_upload'] = upload_helpers.resumable_upload
            _upload_helpers_cache['apply_watermark_to_video'] = upload_helpers.apply_watermark_to_video
            _upload_helpers_cache['cleanup_temp_watermark_file'] = upload_helpers.cleanup_temp_watermark_file
            _upload_helpers_cache['upload_video_once'] = upload_helpers.upload_video_once
            _upload_helpers_cache['move_video_to_uploaded_folder'] = upload_helpers.move_video_to_uploaded_folder
        return _upload_helpers_cache[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

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
    # Upload helpers
    'resumable_upload',
    'apply_watermark_to_video',
    'cleanup_temp_watermark_file',
    'upload_video_once',
    'move_video_to_uploaded_folder',
    # Token service functions
    'get_all_app_tokens',
    'save_app_token',
    'delete_app_token',
    'exchange_token_for_long_lived',
    'get_all_long_lived_tokens',
]
