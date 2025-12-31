"""
UI Helper Functions for Page Management Application

This module provides utility functions for creating UI elements,
managing icons, and other UI-related helper functions.
"""

import os
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


__all__ = [
    'create_fallback_icon',
    'load_app_icon',
    'get_icon',
    'create_icon_button',
    'create_icon_action',
    'ICONS',
    'ICON_COLORS',
    'HAS_QTAWESOME',
]
