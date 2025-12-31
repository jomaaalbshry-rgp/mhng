"""
Job List Item Widget for displaying jobs in the UI.

هذا الملف يحتوي على ويدجت JobListItemWidget لعرض الوظائف في القائمة.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QFontMetrics

# استيراد دوال التنسيق من helpers
from ui.helpers import seconds_to_value_unit, format_remaining_time
from services import get_template_by_id

# ألوان العد التنازلي
COUNTDOWN_COLOR_GREEN = '#27ae60'   # أخضر: ≥5 دقائق
COUNTDOWN_COLOR_YELLOW = '#f39c12'  # أصفر: 1-5 دقائق
COUNTDOWN_COLOR_RED = '#e74c3c'     # أحمر: <1 دقيقة
COUNTDOWN_COLOR_GRAY = '#808080'    # رمادي: معطّل


class JobListItemWidget(QWidget):
    """ويدجت مخصص لعنصر الوظيفة في القائمة مع عدّاد ملوّن في مكان ثابت."""

    # ثوابت لعرض الأعمدة الثابتة
    COUNTDOWN_WIDTH = 120
    STATUS_WIDTH = 80
    MARGINS_WIDTH = 40  # الهوامش والمسافات

    def __init__(self, job, parent=None):  # يقبل PageJob أو StoryJob
        super().__init__(parent)
        self.job = job
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        # ترتيب الأعمدة بحيث يظهر العدّاد أولاً (أقصى اليسار في LTR = أقصى اليمين في RTL)
        # ثم الحالة، ثم معلومات الوظيفة

        # عدّاد الوقت المتبقي (عرض ثابت مع خلفية مميزة)
        self.countdown_label = QLabel()
        self.countdown_label.setFixedWidth(self.COUNTDOWN_WIDTH)
        self.countdown_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.countdown_label)

        # مؤشر حالة الوظيفة (مفعّلة/معطّلة + مجدولة/غير مجدولة) - عمود ثابت
        self.status_label = QLabel()
        self.status_label.setFixedWidth(self.STATUS_WIDTH)
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # معلومات الوظيفة (تأخذ المساحة المتبقية مع اقتطاع النص الطويل)
        self.info_label = QLabel()
        self.info_label.setMinimumWidth(100)
        self.info_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # محاذاة النص لليمين
        layout.addWidget(self.info_label, 1)  # stretch=1 للتمدد

        self.update_display()

    def _elide_text(self, text: str, max_width: int) -> str:
        """اقتطاع النص مع إضافة ... إذا تجاوز العرض المحدد."""
        fm = QFontMetrics(self.info_label.font())
        return fm.elidedText(text, Qt.ElideMiddle, max_width)

    def update_display(self, remaining_seconds=None, outside_working_hours=False, time_to_working_hours=0):
        """تحديث عرض معلومات الوظيفة والعدّاد (Requirement 1 - العداد الذكي)."""

        # التحقق من نظام الجدولة المستخدم (ذكي أو فاصل زمني)
        use_smart_schedule = getattr(self.job, 'use_smart_schedule', False)
        template_id = getattr(self.job, 'template_id', None)

        if use_smart_schedule and template_id:
            # عرض اسم القالب عند استخدام الجدولة الذكية
            template = get_template_by_id(template_id)
            if template:
                schedule_info = f"📅 {template['name']}"
            else:
                # القالب غير موجود - العودة للفاصل الزمني
                val, unit = seconds_to_value_unit(self.job.interval_seconds)
                schedule_info = f"كل {val} {unit}"
        else:
            # نظام الفاصل الزمني
            val, unit = seconds_to_value_unit(self.job.interval_seconds)
            schedule_info = f"كل {val} {unit}"

        # عرض اسم التطبيق إذا كان موجوداً
        app_name = getattr(self.job, 'app_name', '')
        if app_name:
            info_text = f"{self.job.page_name} | {app_name} | ID: {self.job.page_id} - مجلد: {self.job.folder} - {schedule_info}"
        else:
            info_text = f"{self.job.page_name} | ID: {self.job.page_id} - مجلد: {self.job.folder} - {schedule_info}"

        # حساب العرض المتاح لنص المعلومات (العرض الكلي - عرض الحالة والعدّاد - الهوامش)
        available_width = self.width() - self.COUNTDOWN_WIDTH - self.STATUS_WIDTH - self.MARGINS_WIDTH
        if available_width > 100:
            elided_text = self._elide_text(info_text, available_width)
            self.info_label.setText(elided_text)
            # عرض النص الكامل كتلميح فقط إذا تم اقتطاع النص
            if elided_text != info_text:
                self.info_label.setToolTip(info_text)
            else:
                self.info_label.setToolTip('')
        else:
            self.info_label.setText(info_text)
            self.info_label.setToolTip('')

        # تحديث حالة الوظيفة
        if not self.job.enabled:
            self.status_label.setText('معطّل')
            self.status_label.setStyleSheet(f'color: {COUNTDOWN_COLOR_GRAY}; font-weight: bold;')
            self.countdown_label.setText('--:--:--')
        elif self.job.is_scheduled:
            if outside_working_hours:
                # خارج ساعات العمل - عرض الوقت المتبقي لبداية ساعات العمل (Requirement 1)
                self.status_label.setText('خارج ساعات العمل')
                self.status_label.setStyleSheet(f'color: {COUNTDOWN_COLOR_YELLOW}; font-weight: bold;')
                self.countdown_label.setText(f'⏳ تبدأ بعد: {format_remaining_time(time_to_working_hours)}')
            else:
                self.status_label.setText('مجدول')
                self.status_label.setStyleSheet(f'color: {COUNTDOWN_COLOR_GREEN}; font-weight: bold;')
                if remaining_seconds is not None:
                    self.countdown_label.setText(format_remaining_time(remaining_seconds))
                else:
                    self.countdown_label.setText('--:--:--')
        else:
            # مفعّل لكن غير مجدول
            self.status_label.setText('مفعّل')
            self.status_label.setStyleSheet(f'color: {COUNTDOWN_COLOR_YELLOW}; font-weight: bold;')
            self.countdown_label.setText('غير مجدول')

        self.update_countdown_style(remaining_seconds, outside_working_hours)

    def update_countdown_style(self, remaining_seconds=None, outside_working_hours=False):
        """تحديث لون العدّاد بناءً على الوقت المتبقي مع خلفية مميزة (Requirement 1)."""
        # ستايل أساسي للعدّاد مع خلفية داكنة وزوايا مستديرة
        base_style = 'font-weight: bold; padding: 4px 8px; border-radius: 4px;'

        if not self.job.enabled:
            # رمادي داكن للوظائف المعطّلة
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_GRAY}; background-color: #1a1d23; {base_style}'
            )
        elif outside_working_hours:
            # برتقالي لخارج ساعات العمل (Requirement 1)
            self.countdown_label.setStyleSheet(
                f'color: #FF9800; background-color: #2a1f10; {base_style}'
            )
        elif not self.job.is_scheduled:
            # أصفر للوظائف المفعّلة لكن غير المجدولة
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_YELLOW}; background-color: #2a2510; {base_style}'
            )
        elif remaining_seconds is None:
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_GRAY}; background-color: #1a1d23; {base_style}'
            )
        elif remaining_seconds >= 300:  # أخضر: ≥5 دقائق
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_GREEN}; background-color: #0d2818; {base_style}'
            )
        elif remaining_seconds >= 60:  # أصفر: 1-5 دقائق
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_YELLOW}; background-color: #2a2510; {base_style}'
            )
        else:  # أحمر: <1 دقيقة
            self.countdown_label.setStyleSheet(
                f'color: {COUNTDOWN_COLOR_RED}; background-color: #2a1010; {base_style}'
            )
