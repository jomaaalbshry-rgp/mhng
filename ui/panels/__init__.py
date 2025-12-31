"""
لوحات واجهة المستخدم
Panels for the user interface

الهيكلة - Structure:
====================
✅ video_panel.py - يحتوي على عناصر مساعدة للفيديو والريلز (DraggablePreviewLabel, WatermarkPreviewDialog)
                    Contains helper widgets for video and reels

✅ story_panel.py - يحتوي على StoryPanel(QWidget) بإعدادات خاصة بالستوري فقط
                    Contains StoryPanel(QWidget) with story-specific settings

❌ reels_panel.py - ملف توثيقي فقط - لا يحتوي على ReelsPanel class
                    Documentation file only - does NOT contain a ReelsPanel class
                    
    السبب: الريلز يستخدم نفس واجهة الفيديو بالضبط
    Reason: Reels use the EXACT SAME UI as video
    
    الواجهة المشتركة موجودة في: main_window.py
    Shared UI is located in: main_window.py
    
    المنطق الخاص بالريلز موجود في: controllers/reels_controller.py
    Reels-specific logic is in: controllers/reels_controller.py
"""

# استيراد عناصر الفيديو المساعدة - Import video helper widgets
# هذه العناصر مشتركة بين الفيديو والريلز
# These widgets are shared between video and reels
from .video_panel import DraggablePreviewLabel, WatermarkPreviewDialog

# استيراد لوحة الستوري - Import story panel
# الستوري له إعدادات خاصة فريدة، لذا له لوحة منفصلة
# Story has unique settings, so it has a separate panel
from .story_panel import StoryPanel

# استيراد لوحة الصفحات - Import pages panel
from .pages_panel import PagesPanel

# ملاحظة عن الريلز - Note about Reels:
# reels_panel.py موجود كملف توثيقي فقط
# reels_panel.py exists as documentation only
# الريلز يستخدم نفس واجهة الفيديو (لا يحتاج لوحة منفصلة)
# Reels use the same video UI (no separate panel needed)
# لمزيد من التفاصيل، راجع reels_panel.py
# For more details, see reels_panel.py

# سيتم تفعيل هذه الـ imports بعد نقل الكود من main_window.py
# These imports will be activated after moving code from main_window.py
# from .settings_panel import *
# ملاحظة مهمة عن الريلز - IMPORTANT Note about Reels:
# =====================================================
# ⚠️ لا يوجد ReelsPanel class - There is NO ReelsPanel class ⚠️
# 
# السبب: الريلز يستخدم نفس واجهة الفيديو (العنوان، الوصف، Anti-Ban، العلامة المائية)
# Reason: Reels use the same UI as video (title, description, Anti-Ban, watermark)
#
# على عكس الستوري الذي له إعدادات خاصة (عدد الستوريات، التأخير)،
# Unlike story which has unique settings (stories per schedule, delay),
# الريلز ليس له أي إعدادات واجهة فريدة.
# reels has NO unique UI settings.
#
# الفرق الوحيد هو في Backend (نوع الوظيفة وطريقة الرفع)
# The only difference is in the backend (job type and upload method)
#
# لمزيد من التفاصيل، راجع: reels_panel.py
# For more details, see: reels_panel.py

# Exports
__all__ = [
    'DraggablePreviewLabel',
    'WatermarkPreviewDialog', 
    'StoryPanel',
    # Note: ReelsPanel is intentionally NOT exported because it doesn't exist
]
