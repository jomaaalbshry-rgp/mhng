"""
Core module for Page Management Application

This module provides core functionality including:
- SingleInstanceManager: Ensures only one instance of the app runs
- Constants: Application-wide constants
- Thread classes: Background threads for non-blocking operations
- Notification systems: Telegram and general notifications
- Logger: Unified logging system
- BaseJob: Base class for job management
- Utils: Utility functions
"""

from .single_instance import SingleInstanceManager
from .threads import TokenExchangeThread, FetchPagesThread
from .notifications import TelegramNotifier, NotificationSystem
from .constants import (
    SINGLE_INSTANCE_BASE_NAME,
    APP_TITLE,
    APP_DATA_FOLDER,
    RESUMABLE_THRESHOLD_BYTES,
    CHUNK_SIZE_DEFAULT,
    UPLOAD_TIMEOUT_START,
    UPLOAD_TIMEOUT_TRANSFER,
    UPLOAD_TIMEOUT_FINISH,
    UPLOADED_FOLDER_NAME,
    WATERMARK_FFMPEG_TIMEOUT,
    WATERMARK_MIN_OUTPUT_RATIO,
    WATERMARK_CLEANUP_DELAY,
    WATERMARK_FILE_CLOSE_DELAY,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    STORY_EXTENSIONS,
    MAX_VIDEO_DURATION_SECONDS,
    INTERNET_CHECK_INTERVAL,
    INTERNET_CHECK_MAX_ATTEMPTS,
    PAGES_FETCH_LIMIT,
    PAGES_FETCH_MAX_ITERATIONS,
    PAGES_CACHE_DURATION_SECONDS,
    DEFAULT_TOKEN_EXPIRY_SECONDS,
    FACEBOOK_API_VERSION,
    FACEBOOK_API_TIMEOUT,
    THREAD_QUIT_TIMEOUT_MS,
    THREAD_TERMINATE_TIMEOUT_MS,
    SECRET_KEY,
)
from .logger import (
    get_logger, log_debug, log_info, log_warning, log_error, 
    log_critical, log_exception, log_error_to_file, UnifiedLogger, ErrorCodes,
    UploadError, NetworkError, APIError, FileError
)
from .base_job import BaseJob
from .jobs import PageJob
from .utils import (
    get_resource_path, check_internet_connection, wait_for_internet,
    validate_token, get_token_expiry, get_long_lived_token,
    get_available_disk_space, check_disk_space, get_disk_space_for_file,
    get_temp_directory, cleanup_temp_files, create_temp_file,
    RateLimiter, handle_rate_limit, normalize_path, safe_filename,
    ensure_utf8_path, validate_file_path, retry_with_backoff,
    validate_file_extension, get_file_info, SmartUploadScheduler,
    APIUsageTracker, APIWarningSystem, get_api_tracker, 
    get_api_warning_system, calculate_next_run_timestamp,
    API_CALLS_PER_STORY, get_date_placeholder, apply_title_placeholders,
    get_subprocess_args, run_subprocess, create_popen
)
from .job_keys import make_job_key, get_job_key
from .video_utils import (
    validate_video, clean_filename_for_title, calculate_jitter_interval,
    sort_video_files, apply_template, TITLE_CLEANUP_WORDS, TITLE_CLEANUP_PATTERNS
)
from .updater_utils import (
    check_for_updates, get_installed_versions, create_update_script,
    run_update_and_restart, UPDATE_PACKAGES
)

# تأخير استيراد المجدولات لتجنب circular import
# Delay scheduler imports to avoid circular import
# المجدولات تعتمد على ui.signals والتي يمكن أن تستورد من ui.main_window
# لذا نستوردها في النهاية بعد تعريف كل الوحدات الأساسية
from .schedulers import SchedulerThread, StorySchedulerThread, ReelsSchedulerThread

__all__ = [
    'SingleInstanceManager',
    'TokenExchangeThread',
    'FetchPagesThread',
    'TelegramNotifier',
    'NotificationSystem',
    'SchedulerThread',
    'StorySchedulerThread',
    'ReelsSchedulerThread',
    'SINGLE_INSTANCE_BASE_NAME',
    'APP_TITLE',
    'APP_DATA_FOLDER',
    'RESUMABLE_THRESHOLD_BYTES',
    'CHUNK_SIZE_DEFAULT',
    'UPLOAD_TIMEOUT_START',
    'UPLOAD_TIMEOUT_TRANSFER',
    'UPLOAD_TIMEOUT_FINISH',
    'UPLOADED_FOLDER_NAME',
    'WATERMARK_FFMPEG_TIMEOUT',
    'WATERMARK_MIN_OUTPUT_RATIO',
    'WATERMARK_CLEANUP_DELAY',
    'WATERMARK_FILE_CLOSE_DELAY',
    'IMAGE_EXTENSIONS',
    'VIDEO_EXTENSIONS',
    'STORY_EXTENSIONS',
    'MAX_VIDEO_DURATION_SECONDS',
    'INTERNET_CHECK_INTERVAL',
    'INTERNET_CHECK_MAX_ATTEMPTS',
    'PAGES_FETCH_LIMIT',
    'PAGES_FETCH_MAX_ITERATIONS',
    'PAGES_CACHE_DURATION_SECONDS',
    'DEFAULT_TOKEN_EXPIRY_SECONDS',
    'FACEBOOK_API_VERSION',
    'FACEBOOK_API_TIMEOUT',
    'THREAD_QUIT_TIMEOUT_MS',
    'THREAD_TERMINATE_TIMEOUT_MS',
    'SECRET_KEY',
    'get_logger',
    'log_debug',
    'log_info',
    'log_warning',
    'log_error',
    'log_critical',
    'log_exception',
    'log_error_to_file',
    'UnifiedLogger',
    'ErrorCodes',
    'UploadError',
    'NetworkError',
    'APIError',
    'FileError',
    'BaseJob',
    'PageJob',
    'get_resource_path',
    'check_internet_connection',
    'wait_for_internet',
    'validate_token',
    'get_token_expiry',
    'get_long_lived_token',
    'get_available_disk_space',
    'check_disk_space',
    'get_disk_space_for_file',
    'get_temp_directory',
    'cleanup_temp_files',
    'create_temp_file',
    'RateLimiter',
    'handle_rate_limit',
    'normalize_path',
    'safe_filename',
    'ensure_utf8_path',
    'validate_file_path',
    'retry_with_backoff',
    'validate_file_extension',
    'get_file_info',
    'SmartUploadScheduler',
    'APIUsageTracker',
    'APIWarningSystem',
    'get_api_tracker',
    'get_api_warning_system',
    'calculate_next_run_timestamp',
    'API_CALLS_PER_STORY',
    'get_date_placeholder',
    'apply_title_placeholders',
    'get_subprocess_args',
    'run_subprocess',
    'create_popen',
    'make_job_key',
    'get_job_key',
    # Video utils
    'validate_video',
    'clean_filename_for_title',
    'calculate_jitter_interval',
    'sort_video_files',
    'apply_template',
    'TITLE_CLEANUP_WORDS',
    'TITLE_CLEANUP_PATTERNS',
    # Updater utils
    'check_for_updates',
    'get_installed_versions',
    'create_update_script',
    'run_update_and_restart',
    'UPDATE_PACKAGES',
]
