"""
لوحة الفيديو - Video Panel
تحتوي على واجهة إدارة رفع الفيديوهات والعلامة المائية
Contains the interface for managing video uploads and watermark
"""

import os
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import (
    QWidget, QLabel, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QFileDialog
)

from core import run_subprocess, VIDEO_EXTENSIONS
from ui.widgets import NoScrollComboBox, NoScrollSlider
from ui.helpers import (
    create_icon_button, get_icon,
    ICONS, ICON_COLORS, HAS_QTAWESOME
)


# ==================== DraggablePreviewLabel ====================

class DraggablePreviewLabel(QLabel):
    """
    ويدجت عرض الصورة مع دعم سحب العلامة المائية بالماوس.
    يتتبع موقع العلامة المائية ويسمح بتحريكها عند السحب.
    """

    # إشارة عند تغيير موقع العلامة المائية
    watermark_moved = Signal(int, int)  # x, y

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._dragging = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._watermark_x = 0
        self._watermark_y = 0
        self._watermark_width = 0
        self._watermark_height = 0
        self._preview_scale = 1.0  # نسبة التصغير للمعاينة
        self._preview_offset_x = 0  # إزاحة المعاينة داخل الـ Label
        self._preview_offset_y = 0

    def set_watermark_rect(self, x: int, y: int, width: int, height: int,
                          preview_scale: float, offset_x: int, offset_y: int):
        """تعيين مستطيل العلامة المائية (بإحداثيات المعاينة)."""
        self._watermark_x = x
        self._watermark_y = y
        self._watermark_width = width
        self._watermark_height = height
        self._preview_scale = preview_scale
        self._preview_offset_x = offset_x
        self._preview_offset_y = offset_y

    def get_watermark_position(self) -> tuple:
        """الحصول على موقع العلامة المائية (بإحداثيات الصورة الأصلية)."""
        return (self._watermark_x, self._watermark_y)

    def _is_point_in_watermark(self, mouse_x: int, mouse_y: int) -> bool:
        """التحقق مما إذا كانت نقطة الماوس داخل مستطيل العلامة المائية."""
        # تحويل إحداثيات الماوس إلى إحداثيات المعاينة
        preview_x = mouse_x - self._preview_offset_x
        preview_y = mouse_y - self._preview_offset_y

        # التحقق من أن النقطة داخل مستطيل العلامة المائية
        wm_x = int(self._watermark_x * self._preview_scale)
        wm_y = int(self._watermark_y * self._preview_scale)
        wm_w = int(self._watermark_width * self._preview_scale)
        wm_h = int(self._watermark_height * self._preview_scale)

        return (wm_x <= preview_x <= wm_x + wm_w and
                wm_y <= preview_y <= wm_y + wm_h)

    def mousePressEvent(self, event):
        """معالج ضغط الماوس - بدء السحب إذا كان الضغط على العلامة المائية."""
        if event.button() == Qt.LeftButton and self._watermark_width > 0:
            # تحويل إحداثيات الماوس إلى int بشكل صريح
            mouse_x = int(event.position().x()) if hasattr(event, 'position') else event.x()
            mouse_y = int(event.position().y()) if hasattr(event, 'position') else event.y()

            if self._is_point_in_watermark(mouse_x, mouse_y):
                self._dragging = True
                # حساب الإزاحة بين موقع الماوس وركن العلامة المائية
                preview_x = mouse_x - self._preview_offset_x
                preview_y = mouse_y - self._preview_offset_y
                wm_x = int(self._watermark_x * self._preview_scale)
                wm_y = int(self._watermark_y * self._preview_scale)
                self._drag_offset_x = preview_x - wm_x
                self._drag_offset_y = preview_y - wm_y
                self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """معالج حركة الماوس - تحديث موقع العلامة المائية أثناء السحب."""
        # تحويل إحداثيات الماوس إلى int بشكل صريح
        mouse_x = int(event.position().x()) if hasattr(event, 'position') else event.x()
        mouse_y = int(event.position().y()) if hasattr(event, 'position') else event.y()

        if self._dragging:
            # حساب الموقع الجديد للعلامة المائية
            preview_x = mouse_x - self._preview_offset_x - self._drag_offset_x
            preview_y = mouse_y - self._preview_offset_y - self._drag_offset_y

            # تحويل إلى إحداثيات الصورة الأصلية
            new_x = int(preview_x / self._preview_scale) if self._preview_scale > 0 else 0
            new_y = int(preview_y / self._preview_scale) if self._preview_scale > 0 else 0

            # تحديث الموقع وإرسال الإشارة
            self._watermark_x = new_x
            self._watermark_y = new_y
            self.watermark_moved.emit(new_x, new_y)
        elif self._is_point_in_watermark(mouse_x, mouse_y):
            self.setCursor(Qt.OpenHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """معالج رفع الماوس - إنهاء السحب."""
        if event.button() == Qt.LeftButton:
            self._dragging = False
            # تحويل إحداثيات الماوس إلى int بشكل صريح
            mouse_x = int(event.position().x()) if hasattr(event, 'position') else event.x()
            mouse_y = int(event.position().y()) if hasattr(event, 'position') else event.y()

            if self._is_point_in_watermark(mouse_x, mouse_y):
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)


# ==================== WatermarkPreviewDialog ====================

class WatermarkPreviewDialog(QDialog):
    """نافذة معاينة العلامة المائية مع دعم السحب والإفلات."""

    def __init__(self, parent=None, watermark_path='', position='bottom_right',
                 opacity=0.8, scale=0.15):
        super().__init__(parent)
        self.setWindowTitle('👁️ معاينة العلامة المائية (اسحب الشعار لتحريكه)')
        self.setMinimumSize(800, 650)
        self.setModal(True)

        self.watermark_path = watermark_path
        self.position = position
        self.opacity = opacity
        self.scale = scale
        self.video_path = ''
        self.video_frame = None

        # إحداثيات العلامة المائية المخصصة (بإحداثيات الصورة الأصلية)
        self._custom_x = -1  # -1 يعني استخدام الموقع المحدد مسبقاً
        self._custom_y = -1
        self._use_custom_position = False

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # منطقة العرض مع دعم السحب
        self.preview_label = DraggablePreviewLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(640, 360)
        self.preview_label.setStyleSheet('background-color: #1a1a1a; border: 1px solid #333;')
        self.preview_label.setText('اختر فيديو للمعاينة\n(يمكنك سحب الشعار بالماوس لتحريكه)')
        self.preview_label.watermark_moved.connect(self._on_watermark_dragged)
        layout.addWidget(self.preview_label)

        # عرض إحداثيات X و Y
        coords_row = QHBoxLayout()
        coords_row.addWidget(QLabel('📍 إحداثيات العلامة المائية:'))
        self.coord_x_label = QLabel('X: --')
        self.coord_x_label.setStyleSheet('font-weight: bold; color: #88c0d0;')
        coords_row.addWidget(self.coord_x_label)
        self.coord_y_label = QLabel('Y: --')
        self.coord_y_label.setStyleSheet('font-weight: bold; color: #88c0d0;')
        coords_row.addWidget(self.coord_y_label)
        coords_row.addStretch()

        # زر إعادة تعيين الموقع
        reset_pos_btn = create_icon_button('إعادة تعيين الموقع', 'reset')
        reset_pos_btn.setToolTip('إعادة تعيين موقع العلامة المائية إلى الموقع المحدد في القائمة')
        reset_pos_btn.clicked.connect(self._reset_position)
        coords_row.addWidget(reset_pos_btn)
        layout.addLayout(coords_row)

        # اختيار الفيديو
        video_row = QHBoxLayout()
        video_label = QLabel('فيديو للمعاينة:')
        if HAS_QTAWESOME:
            video_icon = QLabel()
            video_icon.setPixmap(get_icon(ICONS['folder'], ICON_COLORS.get('folder')).pixmap(16, 16))
            video_row.addWidget(video_icon)
        video_row.addWidget(video_label)
        self.video_path_label = QLabel('لم يتم اختيار فيديو')
        self.video_path_label.setStyleSheet('color: #888;')
        video_row.addWidget(self.video_path_label, 1)
        browse_btn = create_icon_button('استعراض', 'folder')
        browse_btn.clicked.connect(self._choose_video)
        video_row.addWidget(browse_btn)
        layout.addLayout(video_row)

        # إعدادات المعاينة
        settings_group = QGroupBox('إعدادات المعاينة')
        settings_layout = QFormLayout()

        # الموقع
        self.position_combo = NoScrollComboBox()
        self.position_combo.addItems(['أعلى يسار', 'أعلى يمين', 'أسفل يسار', 'أسفل يمين', 'وسط', 'مخصص (سحب)'])
        position_index = {'top_left': 0, 'top_right': 1, 'bottom_left': 2, 'bottom_right': 3, 'center': 4, 'custom': 5}
        self.position_combo.setCurrentIndex(position_index.get(self.position, 3))
        self.position_combo.currentIndexChanged.connect(self._on_position_changed)
        settings_layout.addRow('الموقع:', self.position_combo)

        # الحجم
        size_row = QHBoxLayout()
        self.size_slider = NoScrollSlider(Qt.Horizontal)
        self.size_slider.setRange(10, 100)
        self.size_slider.setValue(int(self.scale * 100))
        self.size_label = QLabel(f'{int(self.scale * 100)}%')
        self.size_slider.valueChanged.connect(self._on_size_changed)
        size_row.addWidget(self.size_slider, 4)
        size_row.addWidget(self.size_label, 1)
        settings_layout.addRow('الحجم:', size_row)

        # الشفافية
        opacity_row = QHBoxLayout()
        self.opacity_slider = NoScrollSlider(Qt.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(self.opacity * 100))
        self.opacity_label = QLabel(f'{int(self.opacity * 100)}%')
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_row.addWidget(self.opacity_slider, 4)
        opacity_row.addWidget(self.opacity_label, 1)
        settings_layout.addRow('الشفافية:', opacity_row)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # أزرار
        buttons_row = QHBoxLayout()
        apply_btn = create_icon_button('تطبيق', 'check')
        apply_btn.clicked.connect(self._apply_and_close)
        buttons_row.addWidget(apply_btn)

        close_btn = create_icon_button('إغلاق', 'close')
        close_btn.clicked.connect(self.reject)
        buttons_row.addWidget(close_btn)

        layout.addLayout(buttons_row)

    def _on_watermark_dragged(self, x: int, y: int):
        """معالج سحب العلامة المائية - تحديث الموقع والإحداثيات."""
        self._custom_x = x
        self._custom_y = y
        self._use_custom_position = True

        # تحديث عرض الإحداثيات
        self.coord_x_label.setText(f'X: {x}')
        self.coord_y_label.setText(f'Y: {y}')

        # تغيير القائمة إلى "مخصص"
        if self.position_combo.currentIndex() != 5:
            self.position_combo.blockSignals(True)
            self.position_combo.setCurrentIndex(5)
            self.position_combo.blockSignals(False)

        # تحديث المعاينة
        self._update_preview()

    def _on_position_changed(self, index):
        """معالج تغيير الموقع من القائمة."""
        if index < 5:  # ليس مخصص
            self._use_custom_position = False
            self.coord_x_label.setText('X: --')
            self.coord_y_label.setText('Y: --')
        self._update_preview()

    def _reset_position(self):
        """إعادة تعيين الموقع إلى القيمة الافتراضية."""
        self._use_custom_position = False
        self._custom_x = -1
        self._custom_y = -1
        self.coord_x_label.setText('X: --')
        self.coord_y_label.setText('Y: --')
        if self.position_combo.currentIndex() == 5:
            self.position_combo.setCurrentIndex(3)  # أسفل يمين
        else:
            self._update_preview()

    def _choose_video(self):
        """اختيار فيديو للمعاينة."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'اختر فيديو للمعاينة', '',
            'ملفات الفيديو (*.mp4 *.mov *.avi *.mkv)'
        )
        if path:
            self.video_path = path
            self.video_path_label.setText(os.path.basename(path))
            self._extract_frame_and_update()

    def _extract_frame_and_update(self):
        """استخراج إطار من الفيديو وتحديث المعاينة."""
        try:
            # استخراج إطار من الثانية الأولى
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name

            cmd = [
                'ffmpeg', '-i', self.video_path,
                '-ss', '00:00:01',
                '-vframes', '1',
                '-y', tmp_path
            ]
            run_subprocess(cmd, timeout=30)

            if os.path.exists(tmp_path):
                self.video_frame = QPixmap(tmp_path)
                os.remove(tmp_path)
                self._update_preview()
        except Exception as e:
            self.preview_label.setText(f'خطأ في استخراج الإطار: {e}')

    def _update_preview(self):
        """تحديث صورة المعاينة مع العلامة المائية."""
        if not self.video_frame or self.video_frame.isNull():
            return

        if not self.watermark_path or not os.path.exists(self.watermark_path):
            scaled = self.video_frame.scaled(
                640, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
            return

        # تحميل الشعار
        watermark = QPixmap(self.watermark_path)
        if watermark.isNull():
            return

        # حساب حجم الشعار
        scale = self.size_slider.value() / 100.0
        wm_width = int(self.video_frame.width() * scale)
        wm_height = int(watermark.height() * wm_width / watermark.width()) if watermark.width() > 0 else 0
        watermark = watermark.scaled(wm_width, wm_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # إنشاء صورة مدمجة
        result = QPixmap(self.video_frame.size())
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.drawPixmap(0, 0, self.video_frame)

        # تحديد الموقع
        margin = 20
        if self._use_custom_position and self._custom_x >= 0 and self._custom_y >= 0:
            # استخدام الموقع المخصص من السحب
            x, y = self._custom_x, self._custom_y
            # التأكد من أن الشعار داخل حدود الصورة
            max_x = max(0, result.width() - watermark.width())
            max_y = max(0, result.height() - watermark.height())
            x = max(0, min(x, max_x))
            y = max(0, min(y, max_y))
        else:
            positions = ['top_left', 'top_right', 'bottom_left', 'bottom_right', 'center', 'custom']
            pos = positions[min(self.position_combo.currentIndex(), 4)]

            if pos == 'top_left':
                x, y = margin, margin
            elif pos == 'top_right':
                x, y = max(margin, result.width() - watermark.width() - margin), margin
            elif pos == 'bottom_left':
                x, y = margin, max(margin, result.height() - watermark.height() - margin)
            elif pos == 'bottom_right':
                x, y = max(margin, result.width() - watermark.width() - margin), max(margin, result.height() - watermark.height() - margin)
            else:  # center
                x = max(0, (result.width() - watermark.width()) // 2)
                y = max(0, (result.height() - watermark.height()) // 2)

        # تحديث عرض الإحداثيات
        self.coord_x_label.setText(f'X: {x}')
        self.coord_y_label.setText(f'Y: {y}')

        # رسم الشعار مع الشفافية
        painter.setOpacity(self.opacity_slider.value() / 100.0)
        painter.drawPixmap(x, y, watermark)
        painter.end()

        # عرض النتيجة مع حساب نسبة التصغير
        preview_width = 640
        preview_height = 360
        scaled = result.scaled(preview_width, preview_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(scaled)

        # حساب نسبة التصغير والإزاحة لـ DraggablePreviewLabel
        preview_scale = scaled.width() / result.width() if result.width() > 0 else 1.0

        # حساب إزاحة المعاينة داخل الـ Label (للتوسيط)
        label_width = self.preview_label.width()
        label_height = self.preview_label.height()
        offset_x = (label_width - scaled.width()) // 2
        offset_y = (label_height - scaled.height()) // 2

        # تحديث معلومات العلامة المائية في DraggablePreviewLabel
        self.preview_label.set_watermark_rect(
            x, y, watermark.width(), watermark.height(),
            preview_scale, offset_x, offset_y
        )

    def _on_size_changed(self, value):
        self.size_label.setText(f'{value}%')
        self._update_preview()

    def _on_opacity_changed(self, value):
        self.opacity_label.setText(f'{value}%')
        self._update_preview()

    def _apply_and_close(self):
        """تطبيق الإعدادات وإغلاق النافذة."""
        self.scale = self.size_slider.value() / 100.0
        self.opacity = self.opacity_slider.value() / 100.0

        # تحديد الموقع
        if self._use_custom_position:
            self.position = 'custom'
        else:
            positions = ['top_left', 'top_right', 'bottom_left', 'bottom_right', 'center']
            idx = min(self.position_combo.currentIndex(), 4)
            self.position = positions[idx]

        self.accept()

    def get_settings(self):
        """الحصول على الإعدادات المحدثة."""
        settings = {
            'position': self.position,
            'opacity': self.opacity,
            'scale': self.scale
        }
        # إضافة الإحداثيات المخصصة إذا كان الموقع مخصصاً
        if self._use_custom_position and self._custom_x >= 0 and self._custom_y >= 0:
            settings['custom_x'] = self._custom_x
            settings['custom_y'] = self._custom_y
        return settings
