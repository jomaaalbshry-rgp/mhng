"""
وحدة التخزين الآمن - Secure Utils Package

هذه الحزمة تحتوي على وحدات مساعدة للأمان:
- secure_storage: تشفير وفك تشفير البيانات الحساسة باستخدام Fernet

Exported Functions:
- encrypt_text(plain): Encrypt plaintext using Fernet (or legacy XOR as fallback)
- decrypt_text(token): Decrypt ciphertext (supports both Fernet and legacy XOR)
- get_or_create_key(): Get or create the Fernet encryption key
- is_cryptography_available(): Check if cryptography library is installed
- migrate_encrypted_value(old_value): Migrate legacy XOR-encrypted data to Fernet
- SECURE_KEY_FILE: Path to the secret key file (~/.mng_secret.key)

# TODO: Future improvements
# - Add configuration management module
# - Add caching utilities
# - Add helper functions for common operations
"""

from .secure_storage import (
    get_or_create_key,
    encrypt_text,
    decrypt_text,
    SECURE_KEY_FILE,
    is_cryptography_available,
    migrate_encrypted_value
)

__all__ = [
    'get_or_create_key',
    'encrypt_text',
    'decrypt_text',
    'SECURE_KEY_FILE',
    'is_cryptography_available',
    'migrate_encrypted_value',
]

