"""
المتحكمات - طبقة التحكم في المنطق
Controllers - Business logic layer

Note: This module exports both VideoJob and PageJob. PageJob is a backward-compatible
alias for VideoJob, provided to support older code that imports PageJob from 
controllers.video_controller. Both names refer to the same class.
"""

# Export controllers
from .video_controller import VideoController
from .story_controller import StoryController
from .reels_controller import ReelsController
from .scheduler_controller import SchedulerController
from .upload_controller import UploadController

# Export Job classes and utility functions from controllers
# For backward compatibility with code that imports directly
from .video_controller import (
    VideoJob, PageJob, get_video_files, count_video_files,
    validate_video_file, upload_video, upload_video_with_retry,
    is_upload_successful, log_error_to_file as log_video_error
)
from .story_controller import (
    StoryJob, get_story_files, count_story_files,
    upload_story, is_story_upload_successful,
    safe_process_story_job,
    DEFAULT_STORIES_PER_SCHEDULE, DEFAULT_RANDOM_DELAY_MIN, DEFAULT_RANDOM_DELAY_MAX
)
from .reels_controller import (
    ReelsJob, get_reels_files, count_reels_files,
    upload_reels, upload_reels_with_retry,
    is_reels_upload_successful, check_reels_duration
)

__all__ = [
    # Controllers
    'VideoController',
    'StoryController',
    'ReelsController',
    'SchedulerController',
    'UploadController',
    # Job classes
    'VideoJob',
    'PageJob',  # Backward compatibility alias for VideoJob
    'StoryJob',
    'ReelsJob',
    # Utility functions
    'get_video_files',
    'count_video_files',
    'validate_video_file',
    'upload_video',
    'upload_video_with_retry',
    'is_upload_successful',
    'get_story_files',
    'count_story_files',
    'upload_story',
    'is_story_upload_successful',
    'safe_process_story_job',
    'get_reels_files',
    'count_reels_files',
    'upload_reels',
    'upload_reels_with_retry',
    'is_reels_upload_successful',
    'check_reels_duration',
    # Constants
    'DEFAULT_STORIES_PER_SCHEDULE',
    'DEFAULT_RANDOM_DELAY_MIN',
    'DEFAULT_RANDOM_DELAY_MAX',
]
