"""
Single Instance Manager for Page Management Application

This module provides the SingleInstanceManager class that ensures only one instance
of the application is running at a time using Qt's QLocalSocket and QLocalServer.
"""

from PySide6.QtNetwork import QLocalSocket, QLocalServer
from .logger import log_error

# Import SINGLE_INSTANCE_BASE_NAME with lazy loading to avoid potential circular dependency
_DEFAULT_KEY = None

def _get_default_key():
    """Lazy load the default key to avoid circular import issues."""
    global _DEFAULT_KEY
    if _DEFAULT_KEY is None:
        from .constants import SINGLE_INSTANCE_BASE_NAME
        _DEFAULT_KEY = SINGLE_INSTANCE_BASE_NAME
    return _DEFAULT_KEY


class SingleInstanceManager:
    """
    آلية التحقق من النسخة الواحدة باستخدام QLocalSocket و QLocalServer.
    """
    
    def __init__(self, key: str = None):
        self.key = key if key is not None else _get_default_key()
        self.server = None
        self.socket = None
    
    def is_already_running(self) -> bool:
        """التحقق إذا كانت هناك نسخة أخرى تعمل."""
        # Try to connect to existing server
        test_socket = QLocalSocket()
        test_socket.connectToServer(self.key)
        
        if test_socket.waitForConnected(500):
            # Server exists, another instance is running
            # Save the socket for later use in send_restore_message
            self.socket = test_socket
            return True
        
        # No server exists, we are the first instance
        # Clean up the test socket
        test_socket.disconnectFromServer()
        
        # Create the server
        self.server = QLocalServer()
        QLocalServer.removeServer(self.key)
        
        if not self.server.listen(self.key):
            log_error(f'[SingleInstance] Failed to start server: {self.server.errorString()}')
            return False
        
        # Successfully started server, we are the first instance
        return False
    
    def send_restore_message(self) -> bool:
        """إرسال رسالة RESTORE للنسخة الموجودة."""
        if not self.socket or not self.socket.isValid():
            # Try to reconnect if socket is not valid
            self.socket = QLocalSocket()
            self.socket.connectToServer(self.key)
            if not self.socket.waitForConnected(500):
                return False
        
        message = b"RESTORE"
        self.socket.write(message)
        self.socket.flush()
        self.socket.waitForBytesWritten(1000)
        self.socket.disconnectFromServer()
        return True
    
    def setup_server_handler(self, callback):
        """إعداد معالج للاتصالات الواردة."""
        if self.server:
            self.server.newConnection.connect(lambda: self._handle_connection(callback))
    
    def _handle_connection(self, callback):
        """معالجة الاتصال الوارد."""
        if not self.server:
            return
        client = self.server.nextPendingConnection()
        if not client:
            return
        client.waitForReadyRead(1000)
        data = client.readAll()
        if data.data() == b"RESTORE":
            callback()
        client.disconnectFromServer()
