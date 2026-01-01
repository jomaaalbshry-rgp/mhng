"""
خدمة إدارة التوكينات - Token Management Service
Token management functions for Facebook API tokens
"""

from typing import Optional, Tuple
from services.facebook_api import FacebookAPIService


def get_all_app_tokens(database_file: str, decrypt_fn) -> list:
    """
    الحصول على جميع التطبيقات والتوكينات المحفوظة.
    Get all saved applications and tokens.

    المعاملات:
        database_file: مسار ملف قاعدة البيانات - Database file path
        decrypt_fn: دالة فك التشفير - Decryption function

    العائد:
        قائمة من القواميس تحتوي على بيانات التطبيقات
        List of dictionaries containing app data
    """
    return FacebookAPIService.get_all_app_tokens(database_file, decrypt_fn)


def save_app_token(database_file: str, encrypt_fn, app_name: str, app_id: str, 
                   app_secret: str = '', short_lived_token: str = '', 
                   long_lived_token: str = '', token_expires_at: str = None, 
                   token_id: int = None) -> Tuple[bool, Optional[int]]:
    """
    حفظ أو تحديث تطبيق وتوكيناته.
    Save or update application and its tokens.

    المعاملات:
        database_file: مسار ملف قاعدة البيانات - Database file path
        encrypt_fn: دالة التشفير - Encryption function
        app_name: اسم التطبيق - App name
        app_id: معرف التطبيق - App ID
        app_secret: كلمة المرور - App secret
        short_lived_token: التوكن القصير - Short-lived token
        long_lived_token: التوكن الطويل - Long-lived token
        token_expires_at: تاريخ انتهاء التوكن - Token expiration date
        token_id: معرف التطبيق للتحديث (None لإضافة جديد) - App ID for update (None for new)

    العائد:
        tuple: (نجاح: bool, معرف السجل: int أو None)
        tuple: (success: bool, record ID: int or None)
    """
    return FacebookAPIService.save_app_token(
        database_file, encrypt_fn, app_name, app_id, app_secret,
        short_lived_token, long_lived_token, token_expires_at, token_id
    )


def delete_app_token(database_file: str, token_id: int) -> bool:
    """
    حذف تطبيق من قاعدة البيانات.
    Delete application from database.

    المعاملات:
        database_file: مسار ملف قاعدة البيانات - Database file path
        token_id: معرف التطبيق - App ID

    العائد:
        True إذا نجح الحذف - True if deletion successful
    """
    return FacebookAPIService.delete_app_token(database_file, token_id)


def exchange_token_for_long_lived(facebook_api_service, app_id: str, 
                                   app_secret: str, short_lived_token: str) -> tuple:
    """
    تحويل التوكن القصير إلى توكن طويل (60 يوم) عبر Facebook Graph API.
    Exchange short-lived token for long-lived token (60 days) via Facebook Graph API.

    المعاملات:
        facebook_api_service: نسخة من FacebookAPIService
        app_id: معرف التطبيق - App ID
        app_secret: كلمة المرور - App secret
        short_lived_token: التوكن القصير - Short-lived token

    العائد:
        tuple: (نجاح: bool, التوكن الطويل أو رسالة الخطأ: str, تاريخ الانتهاء: str أو None)
        tuple: (success: bool, long-lived token or error message: str, expiry date: str or None)
    """
    return facebook_api_service.exchange_token_for_long_lived(app_id, app_secret, short_lived_token)


def get_all_long_lived_tokens(database_file: str, decrypt_fn) -> list:
    """
    الحصول على جميع التوكينات الطويلة الصالحة.
    Get all valid long-lived tokens.

    المعاملات:
        database_file: مسار ملف قاعدة البيانات - Database file path
        decrypt_fn: دالة فك التشفير - Decryption function

    العائد:
        قائمة من التوكينات الطويلة - List of long-lived tokens
    """
    return FacebookAPIService.get_all_long_lived_tokens(database_file, decrypt_fn)
