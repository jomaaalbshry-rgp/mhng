"""
Core Constants for Page Management Application

This module contains all the constants used throughout the application.
"""

# ==================== Single Instance ====================
SINGLE_INSTANCE_BASE_NAME = "FacebookPageManagementSingleInstance"

# ==================== Application Info ====================
APP_TITLE = "Page management"
APP_DATA_FOLDER = "Page management"

# ==================== Upload Constants ====================
RESUMABLE_THRESHOLD_BYTES = 50 * 1024 * 1024
# حجم الجزء الافتراضي 32MB - زيادة من 8MB لتحسين الأداء مع الملفات الكبيرة
# القيمة الأكبر تقلل عدد الطلبات ولكن تزيد استخدام الذاكرة
CHUNK_SIZE_DEFAULT = 32 * 1024 * 1024

# قيم timeout لعمليات الرفع (بالثواني)
UPLOAD_TIMEOUT_START = 60    # timeout لبدء جلسة الرفع
UPLOAD_TIMEOUT_TRANSFER = 300  # timeout لنقل كل جزء (5 دقائق للأجزاء الكبيرة)
UPLOAD_TIMEOUT_FINISH = 180   # timeout لإنهاء الرفع (3 دقائق للمعالجة)
# اسم المجلد الفرعي الذي ستُنقل إليه الفيديوهات المرفوعة بنجاح
UPLOADED_FOLDER_NAME = "Uploaded"

# ==================== Watermark Constants ====================
WATERMARK_FFMPEG_TIMEOUT = 600  # مهلة إضافة العلامة المائية (10 دقائق)
WATERMARK_MIN_OUTPUT_RATIO = 0.1  # الحد الأدنى لنسبة حجم الملف الناتج (10%)
WATERMARK_CLEANUP_DELAY = 1  # تأخير قبل حذف الملف المؤقت بالثواني
WATERMARK_FILE_CLOSE_DELAY = 0.5  # تأخير بعد FFmpeg للتأكد من إغلاق الملف

# ==================== File Extensions ====================
# الامتدادات المدعومة للصور (للستوري)
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
# الامتدادات المدعومة للفيديوهات
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv')
# جميع الامتدادات المدعومة للستوري (صور + فيديوهات)
STORY_EXTENSIONS = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS

# ==================== Video Constants ====================
# الحد الأقصى لمدة الفيديو بالثواني (4 ساعات - حد فيسبوك)
MAX_VIDEO_DURATION_SECONDS = 4 * 60 * 60  # 14400 ثانية

# ==================== Internet Check Constants ====================
INTERNET_CHECK_INTERVAL = 60  # الفاصل الزمني بين المحاولات بالثواني
INTERNET_CHECK_MAX_ATTEMPTS = 60  # الحد الأقصى للمحاولات (ساعة واحدة)

# ==================== Facebook API Constants ====================
PAGES_FETCH_LIMIT = 100  # الحد الأقصى للصفحات لكل طلب API
PAGES_FETCH_MAX_ITERATIONS = 50  # الحد الأقصى للتكرارات لتجنب الحلقات اللانهائية
PAGES_CACHE_DURATION_SECONDS = 3600  # مدة التخزين المؤقت للصفحات (ساعة واحدة)

# ثوابت التوكن
DEFAULT_TOKEN_EXPIRY_SECONDS = 5184000  # 60 يوم (60 * 24 * 60 * 60)

# إصدار Facebook Graph API
FACEBOOK_API_VERSION = "v20.0"

# مهلة طلبات API بالثواني
FACEBOOK_API_TIMEOUT = 30

# ==================== Thread Management Constants ====================
THREAD_QUIT_TIMEOUT_MS = 3000  # مهلة انتظار إيقاف الـ Thread (3 ثوانٍ)
THREAD_TERMINATE_TIMEOUT_MS = 1000  # مهلة انتظار الإنهاء الإجباري (ثانية واحدة)

# ==================== Encryption ====================
SECRET_KEY = b'\x93\x1f\x52\xaa\x09\x77\x2c\x5d\xee\x11\x23\x48\x9b\xcc\x07'
