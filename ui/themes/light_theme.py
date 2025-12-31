"""
Light theme fallback stylesheet.
Used when qdarktheme library is not available.
"""

LIGHT_THEME_FALLBACK = """
QWidget {
    background-color: #f5f5f5;
    color: #333333;
    font-family: 'Segoe UI', Arial, sans-serif;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #ddd;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 15px;
    color: #333333;
}

QGroupBox::title {
    color: #333333;
    background-color: #ffffff;
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}

QPushButton {
    background-color: #e0e0e0;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #d0d0d0;
}

QPushButton:pressed {
    background-color: #c0c0c0;
}

QPushButton:disabled {
    background-color: #f0f0f0;
    color: #999999;
    border-color: #ddd;
}

QLineEdit, QSpinBox, QComboBox, QTimeEdit, QDateEdit {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px;
}

QListWidget {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ddd;
}

QListWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QTextEdit {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ddd;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: #ffffff;
}

QTabWidget::pane {
    background-color: #ffffff;
    border: 1px solid #ddd;
}

QTabBar::tab {
    background-color: #e0e0e0;
    color: #333333;
    padding: 8px 16px;
    border: 1px solid #ccc;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    border-bottom: none;
    color: #0078d4;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #d8d8d8;
}

QLabel {
    color: #333333;
    background-color: transparent;
}

QCheckBox {
    color: #333333;
}

QSlider::groove:horizontal {
    background-color: #ddd;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background-color: #0078d4;
    width: 16px;
    height: 16px;
    border-radius: 8px;
    margin: -5px 0;
}

QProgressBar {
    background-color: #e0e0e0;
    border: 1px solid #ccc;
    border-radius: 4px;
    text-align: center;
    color: #333333;
}

QProgressBar::chunk {
    background-color: #28a745;
    border-radius: 3px;
}

QMenuBar {
    background-color: #f0f0f0;
    color: #333333;
    border-bottom: 1px solid #ddd;
}

QMenuBar::item {
    background-color: transparent;
    padding: 6px 12px;
}

QMenuBar::item:selected {
    background-color: #e0e0e0;
}

QMenu {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ddd;
}

QMenu::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QTableWidget {
    background-color: #ffffff;
    color: #333333;
    gridline-color: #ddd;
    border: 1px solid #ddd;
}

QTableWidget::item {
    background-color: #ffffff;
    color: #333333;
    padding: 4px;
}

QTableWidget::item:selected {
    background-color: #0078d4;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #e0e0e0;
    color: #333333;
    padding: 6px;
    border: 1px solid #ccc;
    font-weight: bold;
}

QToolTip {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 4px 8px;
}
"""

__all__ = ['LIGHT_THEME_FALLBACK']
