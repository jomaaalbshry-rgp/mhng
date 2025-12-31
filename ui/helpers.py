"""
UI Helper Functions for Page Management Application

This module provides utility functions for creating UI elements,
managing icons, and other UI-related helper functions.

Functions added in Phase 6:
- Formatting functions (format_remaining_time, format_time_12h, etc.)
- Token utility (mask_token)
"""

import os
from datetime import datetime, timedelta
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QFont, QAction
from PySide6.QtWidgets import QPushButton
from core import get_resource_path


def create_fallback_icon() -> QIcon:
    """
    إنشاء أيقونة افتراضية (حرف P في مربع أزرق) للاستخدام عند عدم توفر ملف أيقونة.
    
    العائد:
        QIcon يحتوي على الأيقونة الافتراضية.
    """
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(52, 152, 219)))  # لون أزرق
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(8, 8, 48, 48, 8, 8)
        # رسم حرف P في المنتصف
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "P")
    finally:
        painter.end()
    return QIcon(pixmap)


def load_app_icon() -> QIcon:
    """
    تحميل أيقونة التطبيق من مسارات محددة بالترتيب.
    يدعم كل من وضع التطوير والتشغيل بعد التجميع بـ PyInstaller.
    
    المسارات التي يتم البحث فيها:
        1. assets/favicon.ico (عبر get_resource_path)
        2. assets/favicon-32x32.png (عبر get_resource_path)
        3. assets/android-chrome-192x192.png (عبر get_resource_path)
        4. favicon.ico بجوار الملف التنفيذي
    
    العائد:
        QIcon يحتوي على الأيقونة إذا وُجدت، وإلا يتم إرجاع الأيقونة الافتراضية.
    """
    # قائمة المسارات النسبية للبحث عن الأيقونة
    relative_paths = [
        'assets/favicon.ico',
        'assets/icon.ico',
        'assets/favicon-32x32.png',
        'assets/android-chrome-192x192.png',
        'favicon.ico',
        'icon.ico',
    ]
    
    # البحث باستخدام get_resource_path
    for rel_path in relative_paths:
        icon_path = get_resource_path(rel_path)
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            if not icon.isNull():
                return icon
    
    # إذا لم يتم العثور على أي أيقونة، استخدم الأيقونة الافتراضية
    return create_fallback_icon()


# محاولة استيراد qtawesome للأيقونات الاحترافية
HAS_QTAWESOME = False
try:
    import qtawesome as qta
    HAS_QTAWESOME = True
except ImportError:
    HAS_QTAWESOME = False


def get_icon(icon_name: str, color: str = None, fallback_text: str = '') -> QIcon:
    """
    الحصول على أيقونة qtawesome أو أيقونة فارغة كبديل.
    
    المعاملات:
        icon_name: اسم الأيقونة من Font Awesome (مثل 'fa5s.save')
        color: لون الأيقونة (اختياري)
        fallback_text: نص بديل إذا لم تتوفر الأيقونة
    
    العائد:
        QIcon الأيقونة المطلوبة أو أيقونة فارغة
    """
    if HAS_QTAWESOME:
        try:
            if color:
                return qta.icon(icon_name, color=color)
            return qta.icon(icon_name)
        except Exception:
            pass
    return QIcon()


# قاموس الأيقونات المستخدمة في التطبيق
ICONS = {
    # أيقونات الإجراءات العامة
    'refresh': 'fa5s.sync-alt',
    'save': 'fa5s.save',
    'delete': 'fa5s.trash-alt',
    'folder': 'fa5s.folder-open',
    'add': 'fa5s.plus-circle',
    'play': 'fa5s.play-circle',
    'stop': 'fa5s.stop-circle',
    'pause': 'fa5s.pause-circle',
    'check': 'fa5s.check-circle',
    'close': 'fa5s.times-circle',
    'warning': 'fa5s.exclamation-triangle',
    'info': 'fa5s.info-circle',
    'error': 'fa5s.times-circle',
    'upload': 'fa5s.cloud-upload-alt',
    'download': 'fa5s.cloud-download-alt',
    'update': 'fa5s.arrow-circle-up',
    'search': 'fa5s.search',
    'settings': 'fa5s.cog',
    'eye': 'fa5s.eye',
    'hashtag': 'fa5s.hashtag',
    'watermark': 'fa5s.paint-brush',
    'reset': 'fa5s.undo-alt',
    'shield': 'fa5s.shield-alt',
    'chart': 'fa5s.chart-bar',
    'network': 'fa5s.wifi',
    'moon': 'fa5s.moon',
    'sun': 'fa5s.sun',
    'video': 'fa5s.video',
    'image': 'fa5s.image',
    'story': 'fa5s.mobile-alt',
    'reels': 'fa5s.film',
    'schedule': 'fa5s.calendar-alt',
    'time': 'fa5s.clock',
    'success': 'fa5s.check',
    'fail': 'fa5s.times',
    'pending': 'fa5s.hourglass-half',
    'telegram': 'fa5b.telegram-plane',
    'bell': 'fa5s.bell',
    'pages': 'fa5s.file-alt',
}


# ألوان الأيقونات حسب الوظيفة
ICON_COLORS = {
    # 🟢 إجراءات إيجابية - أخضر
    'play': '#4CAF50',
    'add': '#4CAF50',
    'check': '#4CAF50',
    'save': '#4CAF50',
    'success': '#4CAF50',
    
    # 🔴 إجراءات سلبية - أحمر
    'stop': '#F44336',
    'delete': '#F44336',
    'close': '#F44336',
    'error': '#F44336',
    'fail': '#F44336',
    
    # 🟠 تحذيرات/مجلدات - برتقالي
    'folder': '#FF9800',
    'warning': '#FF9800',
    'bell': '#FF9800',
    
    # 🔵 إجراءات عامة - أزرق
    'refresh': '#2196F3',
    'search': '#2196F3',
    'update': '#2196F3',
    'download': '#2196F3',
    'upload': '#2196F3',
    'info': '#2196F3',
    'pages': '#2196F3',
    
    # 🟣 إعدادات - بنفسجي
    'settings': '#9C27B0',
    'watermark': '#9C27B0',
    
    # 🔵 Telegram - أزرق تليجرام
    'telegram': '#0088CC',
    
    # 📊 إحصائيات - أخضر فاتح
    'chart': '#00BCD4',
    
    # 📶 شبكة - أخضر
    'network': '#4CAF50',
    
    # 🌙 ثيمات
    'moon': '#5C6BC0',
    'sun': '#FFC107',
    
    # 📱 وسائط
    'video': '#E91E63',
    'image': '#9C27B0',
    'story': '#FF5722',
    'reels': '#673AB7',
    
    # ⏰ جدولة
    'schedule': '#009688',
    'time': '#607D8B',
    'pause': '#FF9800',
    'pending': '#FF9800',
    
    # 🔐 حماية
    'shield': '#4CAF50',
    'reset': '#607D8B',
    
    # #️⃣ هاشتاج
    'hashtag': '#2196F3',
    
    # 👁️ عرض
    'eye': '#607D8B',
}


def create_icon_button(text: str, icon_key: str, color: str = None) -> QPushButton:
    """
    إنشاء زر مع أيقونة qtawesome.
    
    المعاملات:
        text: نص الزر
        icon_key: مفتاح الأيقونة من قاموس ICONS
        color: لون الأيقونة (اختياري) - إذا لم يُحدد سيتم استخدام اللون من ICON_COLORS
    
    العائد:
        QPushButton زر مع أيقونة
    """
    btn = QPushButton(text)
    if HAS_QTAWESOME and icon_key in ICONS:
        # استخدام اللون المحدد أو اللون الافتراضي من ICON_COLORS
        icon_color = color or ICON_COLORS.get(icon_key)
        icon = get_icon(ICONS[icon_key], icon_color)
        if not icon.isNull():
            btn.setIcon(icon)
    return btn


def create_icon_action(text: str, icon_key: str, parent=None, color: str = None) -> QAction:
    """
    إنشاء QAction مع أيقونة qtawesome.
    
    المعاملات:
        text: نص الإجراء
        icon_key: مفتاح الأيقونة من قاموس ICONS
        parent: الأب (QWidget)
        color: لون الأيقونة (اختياري) - إذا لم يُحدد سيتم استخدام اللون من ICON_COLORS
    
    العائد:
        QAction إجراء مع أيقونة
    """
    action = QAction(text, parent)
    if HAS_QTAWESOME and icon_key in ICONS:
        # استخدام اللون المحدد أو اللون الافتراضي من ICON_COLORS
        icon_color = color or ICON_COLORS.get(icon_key)
        icon = get_icon(ICONS[icon_key], icon_color)
        if not icon.isNull():
            action.setIcon(icon)
    return action


# ==================== Formatting Functions ====================

def mask_token(t: str) -> str:
    """
    إخفاء التوكن للعرض الآمن.
    Mask token for safe display.
    
    المعاملات / Args:
        t: التوكن - Token
    
    العائد / Returns:
        التوكن المخفي - Masked token
    """
    if not t:
        return "(لا يوجد)"
    if len(t) <= 12:
        return t
    return t[:8] + '...' + t[-4:]


def seconds_to_value_unit(secs: int) -> tuple:
    """
    تحويل الثواني إلى قيمة ووحدة مناسبة.
    Convert seconds to appropriate value and unit.
    
    المعاملات / Args:
        secs: عدد الثواني - Number of seconds
    
    العائد / Returns:
        tuple: (القيمة، الوحدة) - (value, unit)
    """
    if secs < 60:
        return (secs, 'ثانية')
    elif secs < 3600:
        return (secs // 60, 'دقيقة')
    elif secs < 86400:
        return (secs // 3600, 'ساعة')
    else:
        return (secs // 86400, 'يوم')


def format_remaining_time(seconds: int) -> str:
    """
    تنسيق الوقت المتبقي بشكل قابل للقراءة.
    Format remaining time in a readable format.
    
    المعاملات / Args:
        seconds: عدد الثواني - Number of seconds
    
    العائد / Returns:
        نص منسق - Formatted text
    """
    if seconds < 0:
        return 'منتهي'
    
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f'{days}ي')
    if hours > 0:
        parts.append(f'{hours}س')
    if minutes > 0:
        parts.append(f'{minutes}د')
    if secs > 0 and days == 0:  # Only show seconds if less than a day
        parts.append(f'{secs}ث')
    
    return ' '.join(parts) if parts else '0ث'


def format_time_12h(time_str: str = None) -> str:
    """
    تحويل الوقت إلى صيغة 12 ساعة مع AM/PM.
    Convert time to 12-hour format with AM/PM.
    
    المعاملات / Args:
        time_str: وقت بصيغة 24 ساعة (HH:MM) أو None للوقت الحالي
                 Time in 24-hour format (HH:MM) or None for current time
    
    العائد / Returns:
        وقت بصيغة 12 ساعة - Time in 12-hour format
    """
    try:
        if time_str:
            # تحليل الوقت المعطى
            time_obj = datetime.strptime(time_str, '%H:%M').time()
        else:
            # استخدام الوقت الحالي
            time_obj = datetime.now().time()
        
        hour = time_obj.hour
        minute = time_obj.minute
        
        # تحديد AM أو PM
        period = 'ص' if hour < 12 else 'م'  # ص للصباح، م للمساء
        
        # تحويل إلى صيغة 12 ساعة
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12
        
        return f'{hour_12:02d}:{minute:02d} {period}'
    except Exception:
        return time_str or ''


def format_datetime_12h() -> str:
    """
    تنسيق التاريخ والوقت الحالي بصيغة 12 ساعة.
    Format current date and time in 12-hour format.
    
    العائد / Returns:
        نص منسق - Formatted text
    """
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = format_time_12h()
    return f'{date_str} {time_str}'


__all__ = [
    'create_fallback_icon',
    'load_app_icon',
    'get_icon',
    'create_icon_button',
    'create_icon_action',
    'ICONS',
    'ICON_COLORS',
    'HAS_QTAWESOME',
    # Formatting functions
    'mask_token',
    'seconds_to_value_unit',
    'format_remaining_time',
    'format_time_12h',
    'format_datetime_12h',
]
