"""
ويدجت التقدم - Progress Widget
يعرض تقدم عمليات الرفع والتحميل
Displays progress of upload and download operations
"""

from PySide6.QtWidgets import QWidget, QProgressBar, QLabel, QHBoxLayout
from PySide6.QtCore import Signal


class ProgressWidget(QWidget):
    """
    ويدجت عرض تقدم العمليات
    Widget for displaying operation progress
    """
    
    # Signals
    cancelled = Signal()  # عند إلغاء العملية - When operation is cancelled
    
    def __init__(self, parent=None, show_label: bool = True):
        """
        Initialize progress widget
        
        Args:
            parent: Parent widget
            show_label: Whether to show status label (default: True)
        """
        super().__init__(parent)
        self._show_label = show_label
        self._setup_ui()
    
    def _setup_ui(self):
        """إعداد الواجهة - Setup UI elements"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)
        
        # Status label (optional)
        if self._show_label:
            self.status_label = QLabel('جاهز.')
            layout.addWidget(self.status_label)
        else:
            self.status_label = None
    
    def set_progress(self, value: int, maximum: int = 100):
        """
        تعيين التقدم - Set progress value
        
        Args:
            value: Current progress value
            maximum: Maximum progress value (default: 100)
        """
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)
    
    def set_status(self, status: str):
        """
        تعيين حالة النص - Set status text
        
        Args:
            status: Status text to display
        """
        if self.status_label:
            self.status_label.setText(status)
    
    def update(self, value: int, status: str = None, maximum: int = 100):
        """
        تحديث التقدم والحالة معاً
        Update both progress and status
        
        Args:
            value: Current progress value
            status: Status text (optional)
            maximum: Maximum progress value (default: 100)
        """
        self.set_progress(value, maximum)
        if status and self.status_label:
            self.set_status(status)
    
    def reset(self):
        """إعادة تعيين - Reset progress"""
        self.progress_bar.setValue(0)
        if self.status_label:
            self.status_label.setText('جاهز.')
    
    def get_value(self) -> int:
        """
        الحصول على القيمة الحالية
        Get current progress value
        
        Returns:
            Current progress value
        """
        return self.progress_bar.value()
    
    def get_maximum(self) -> int:
        """
        الحصول على القيمة القصوى
        Get maximum progress value
        
        Returns:
            Maximum progress value
        """
        return self.progress_bar.maximum()
    
    def is_complete(self) -> bool:
        """
        التحقق من اكتمال التقدم
        Check if progress is complete
        
        Returns:
            True if progress is at maximum
        """
        return self.progress_bar.value() >= self.progress_bar.maximum()
