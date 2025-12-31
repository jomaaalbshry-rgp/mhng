"""
وحدة التخزين الآمن - Secure Storage Module

هذه الوحدة توفر تشفير آمن للبيانات الحساسة مثل التوكنات
باستخدام مكتبة cryptography مع Fernet encryption.

Features:
- Fernet symmetric encryption (AES-128-CBC with HMAC)
- Automatic key generation and storage
- Key file permissions (600 on Unix)
- Graceful fallback for legacy XOR encryption

# TODO: Future improvements
# - Add key rotation support
# - Add secure memory wiping
# - Add hardware security module (HSM) support
"""

import os
import sys
import base64
import warnings
from pathlib import Path
from typing import Optional

# Try to import cryptography, fall back gracefully if not available
try:
    from cryptography.fernet import Fernet, InvalidToken
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    Fernet = None
    InvalidToken = Exception


# ==================== Constants ====================

# The secret key file location
SECURE_KEY_FILE = Path.home() / '.mng_secret.key'

# Legacy secret key for fallback XOR decryption
# This matches the SECRET_KEY in admin.py for backward compatibility
LEGACY_SECRET_KEY = b'\x93\x1f\x52\xaa\x09\x77\x2c\x5d\xee\x11\x23\x48\x9b\xcc\x07'


# ==================== Key Management ====================

def get_or_create_key() -> bytes:
    """
    Get the existing encryption key or create a new one.
    
    The key is stored in ~/.mng_secret.key with restricted permissions (600 on Unix).
    
    Returns:
        The encryption key as bytes
    
    Raises:
        RuntimeError: If cryptography library is not available
    """
    if not HAS_CRYPTOGRAPHY:
        raise RuntimeError(
            "cryptography library is not installed. "
            "Please install it with: pip install cryptography>=41.0.0"
        )
    
    key_file = SECURE_KEY_FILE
    
    # Check if key file already exists
    if key_file.exists():
        try:
            key = key_file.read_bytes().strip()
            # Validate that it's a valid Fernet key
            Fernet(key)
            return key
        except Exception:
            # Invalid key, regenerate
            pass
    
    # Generate new key
    key = Fernet.generate_key()
    
    # Write key to file
    try:
        key_file.write_bytes(key)
        
        # Set restrictive permissions on Unix systems (owner read/write only)
        if sys.platform != 'win32':
            os.chmod(str(key_file), 0o600)
        
    except (OSError, PermissionError) as e:
        # Log warning but continue - key will work for this session
        warnings.warn(f"Could not save encryption key to {key_file}: {e}")
    
    return key


def _get_fernet() -> Optional['Fernet']:
    """
    Get a Fernet instance with the current key.
    
    Returns:
        Fernet instance or None if cryptography is not available
    """
    if not HAS_CRYPTOGRAPHY:
        return None
    
    try:
        key = get_or_create_key()
        return Fernet(key)
    except Exception:
        return None


# ==================== Legacy XOR Encryption (for backward compatibility) ====================

def _legacy_xor_encrypt(plain: str, key: bytes = LEGACY_SECRET_KEY) -> str:
    """
    Legacy XOR encryption for backward compatibility.
    
    This is the same as simple_encrypt in admin.py.
    Uses urlsafe_b64encode to match the original implementation.
    
    Args:
        plain: Plaintext to encrypt
        key: Encryption key bytes
    
    Returns:
        Base64-encoded ciphertext (URL-safe)
    """
    if not plain:
        return ''
    
    try:
        data = plain.encode('utf-8')
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    except Exception:
        return ''


def _legacy_xor_decrypt(token: str, key: bytes = LEGACY_SECRET_KEY) -> str:
    """
    Legacy XOR decryption for backward compatibility.
    
    This is the same as simple_decrypt in admin.py.
    Uses urlsafe_b64decode to match the original implementation.
    
    Args:
        token: Base64-encoded ciphertext (URL-safe)
        key: Encryption key bytes
    
    Returns:
        Decrypted plaintext
    """
    if not token:
        return ''
    
    try:
        encrypted = base64.urlsafe_b64decode(token.encode('utf-8'))
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(encrypted))
        return decrypted.decode('utf-8')
    except Exception:
        return ''


# ==================== Secure Encryption Functions ====================

def encrypt_text(plain: str) -> str:
    """
    Encrypt plaintext and return base64-encoded ciphertext.
    
    Uses Fernet encryption if available, falls back to legacy XOR.
    
    Args:
        plain: The plaintext to encrypt
    
    Returns:
        Base64-encoded ciphertext (prefixed with 'FRN:' for Fernet encryption)
    """
    if not plain:
        return ''
    
    fernet = _get_fernet()
    
    if fernet is not None:
        try:
            # Encrypt with Fernet
            encrypted = fernet.encrypt(plain.encode('utf-8'))
            # Prefix with 'FRN:' to identify Fernet-encrypted data
            return 'FRN:' + encrypted.decode('utf-8')
        except Exception:
            pass
    
    # Fallback to legacy XOR encryption
    return _legacy_xor_encrypt(plain)


def decrypt_text(token: str) -> str:
    """
    Decrypt base64-encoded ciphertext and return plaintext.
    
    Tries Fernet decryption first (for 'FRN:' prefixed tokens),
    then falls back to legacy XOR decryption for backward compatibility.
    
    Args:
        token: Base64-encoded ciphertext
    
    Returns:
        Decrypted plaintext, or empty string if decryption fails
    """
    if not token:
        return ''
    
    # Check if this is Fernet-encrypted data (prefixed with 'FRN:')
    if token.startswith('FRN:'):
        fernet = _get_fernet()
        if fernet is not None:
            try:
                encrypted_data = token[4:].encode('utf-8')  # Remove 'FRN:' prefix
                decrypted = fernet.decrypt(encrypted_data)
                return decrypted.decode('utf-8')
            except InvalidToken:
                # Token might be corrupted or key changed
                pass
            except Exception:
                pass
        
        # If Fernet decryption failed, return empty (can't fall back for Fernet data)
        return ''
    
    # Non-prefixed tokens are legacy XOR-encrypted data
    # Fall back to legacy XOR decryption for backward compatibility
    return _legacy_xor_decrypt(token)


def migrate_encrypted_value(old_value: str) -> str:
    """
    Migrate a legacy-encrypted value to the new secure encryption.
    
    This decrypts using legacy method and re-encrypts with Fernet.
    
    Args:
        old_value: The legacy-encrypted value
    
    Returns:
        Newly encrypted value with Fernet, or original if migration fails
    """
    if not old_value:
        return ''
    
    # If already Fernet-encrypted, return as-is
    if old_value.startswith('FRN:'):
        return old_value
    
    # Decrypt with legacy method
    plain = _legacy_xor_decrypt(old_value)
    
    if not plain:
        # Decryption failed, return original
        return old_value
    
    # Re-encrypt with Fernet
    return encrypt_text(plain)


def is_cryptography_available() -> bool:
    """
    Check if the cryptography library is available.
    
    Returns:
        True if cryptography is available, False otherwise
    """
    return HAS_CRYPTOGRAPHY
