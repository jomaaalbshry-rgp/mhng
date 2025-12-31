"""
Update Event Handlers - معالجات أحداث التحديثات
Contains handlers for application updates.
"""

import os
import sys
from typing import Optional, Dict
from PySide6.QtWidgets import QMessageBox, QProgressDialog
from PySide6.QtCore import Qt, QThread, Signal

from core import log_info, log_error
from core.updater_utils import check_for_updates, create_update_script


class UpdateCheckThread(QThread):
    """خيط فحص التحديثات"""
    update_available = Signal(list)  # List of (name, current_version, latest_version)
    no_update = Signal()
    error = Signal(str)
    
    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version
    
    def run(self):
        try:
            # Returns list of (name, current_version, latest_version) tuples
            result = check_for_updates()
            if result and isinstance(result, list):  # Validate it's a non-empty list
                self.update_available.emit(result)
            else:
                self.no_update.emit()
        except Exception as e:
            self.error.emit(str(e))


class UpdateHandlers:
    """
    معالجات أحداث التحديثات
    Handles application update events and actions.
    """
    
    def __init__(self, parent=None, current_version: str = "1.0.0"):
        self.parent = parent
        self.current_version = current_version
        self._update_thread: Optional[UpdateCheckThread] = None
    
    def check_for_updates(self, silent: bool = False):
        """
        فحص التحديثات
        Check for available updates.
        """
        if self._update_thread and self._update_thread.isRunning():
            return
        
        self._update_thread = UpdateCheckThread(self.current_version)
        self._update_thread.update_available.connect(
            lambda result: self._on_update_available(result, silent)
        )
        self._update_thread.no_update.connect(
            lambda: self._on_no_update(silent)
        )
        self._update_thread.error.connect(
            lambda error: self._on_update_error(error, silent)
        )
        self._update_thread.start()
    
    def _on_update_available(self, result: list, silent: bool):
        """معالجة وجود تحديث متاح"""
        # result is a list of (name, current_version, latest_version)
        packages = [f"{name} ({current} → {latest})" 
                   for name, current, latest in result]
        packages_str = '\n'.join(packages)
        
        reply = QMessageBox.question(
            self.parent,
            "تحديث متاح",
            f"🆕 يتوفر تحديث للمكتبات التالية:\n\n{packages_str}\n\nهل تريد التحديث الآن؟",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._download_and_install(result)
    
    def _on_no_update(self, silent: bool):
        """معالجة عدم وجود تحديث"""
        if not silent:
            QMessageBox.information(
                self.parent,
                "لا يوجد تحديث",
                "✅ أنت تستخدم أحدث إصدار!"
            )
    
    def _on_update_error(self, error: str, silent: bool):
        """معالجة خطأ الفحص"""
        log_error(f"Update check failed: {error}")
        if not silent:
            QMessageBox.warning(
                self.parent,
                "خطأ",
                f"❌ فشل فحص التحديثات: {error}"
            )
    
    def _download_and_install(self, update_info: list):
        """
        تحميل وتثبيت التحديث
        
        Args:
            update_info: List of (name, current_version, latest_version) tuples
        
        Raises:
            NotImplementedError: This functionality needs to be implemented
        
        TODO: Implement using core.updater_utils.create_update_script 
              and run_update_and_restart
        """
        # Extract package names for the update
        packages_to_update = [name for name, _, _ in update_info]
        log_info(f"Update requested for packages: {packages_to_update}")
        raise NotImplementedError(
            "Download and installation functionality not yet implemented. "
            "Use core.updater_utils.create_update_script and run_update_and_restart "
            "to implement this feature."
        )
