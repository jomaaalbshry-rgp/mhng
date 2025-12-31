"""
Dark theme custom styles.
Additional styles for dark theme customization.
"""

DARK_THEME_CUSTOM = """
QPushButton {
  background-color: #2e3440;
  color: #e6e6e6;
  border: 1px solid #3b4252;
  border-radius: 6px;
  padding: 6px 12px;
}
QPushButton:hover { background-color: #3b4252; }
QPushButton:pressed { background-color: #2b303b; }
QPushButton:disabled { background-color: #1f232b; color: #8a8f98; border-color: #2a2f38; }
QCheckBox { text-decoration: none; border: 0; }
QToolTip {
  background-color: #2e3440;
  color: #e6e6e6;
  border: 1px solid #3b4252;
  border-radius: 4px;
  padding: 4px 8px;
}
QLineEdit[readonly="true"] {
  background-color: #1f2329;
  color: #bdc3c7;
}
QGroupBox {
  border: 1px solid #3b4252;
  border-radius: 6px;
  margin-top: 8px;
  padding-top: 18px;
}
QGroupBox::title {
  subcontrol-origin: margin;
  left: 10px;
  padding: 0 6px;
  background-color: transparent;
}
/* تحسين ألوان التبويبات للثيم الداكن */
QTabWidget::pane {
  border: 1px solid #3b4252;
  background-color: #2e3440;
  border-radius: 4px;
}
QTabBar::tab {
  background-color: #2e3440;
  color: #e6e6e6;
  border: 1px solid #3b4252;
  border-bottom: none;
  padding: 8px 16px;
  margin-right: 2px;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
}
QTabBar::tab:selected {
  background-color: #3b4252;
  color: #88c0d0;
  font-weight: bold;
}
QTabBar::tab:hover:!selected {
  background-color: #434c5e;
}
QTabBar::tab:!selected {
  margin-top: 2px;
}
/* إصلاح ألوان جدول الإحصائيات للثيم الداكن */
QTableWidget {
  background-color: #2e3440;
  color: #e6e6e6;
  gridline-color: #3b4252;
  border: 1px solid #3b4252;
}
QTableWidget::item {
  background-color: #2e3440;
  color: #e6e6e6;
  padding: 4px;
}
QTableWidget::item:selected {
  background-color: #3b4252;
  color: #88c0d0;
}
QHeaderView::section {
  background-color: #3b4252;
  color: #e6e6e6;
  padding: 6px;
  border: 1px solid #434c5e;
  font-weight: bold;
}
QComboBox {
  background-color: #2e3440;
  color: #e6e6e6;
  border: 1px solid #3b4252;
  border-radius: 4px;
  padding: 4px 8px;
}
QComboBox::drop-down {
  border: none;
}
QComboBox QAbstractItemView {
  background-color: #2e3440;
  color: #e6e6e6;
  selection-background-color: #3b4252;
  selection-color: #88c0d0;
  border: 1px solid #3b4252;
}
"""

__all__ = ['DARK_THEME_CUSTOM']
