"""Cryptography utilities for secure data handling."""
import logging
from typing import Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64
import os

logger = logging.getLogger(__name__)


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Returns:
        str: Base64-encoded encryption key
    """
    return Fernet.generate_key().decode()


def derive_key_from_password(password: str, salt: bytes = None) -> Tuple[str, bytes]:
    """
    Derive encryption key from password using PBKDF2.
    
    Args:
        password: Password to derive key from
        salt: Optional salt bytes. If None, generates new salt
        
    Returns:
        tuple: (key string, salt bytes)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key.decode(), salt


def encrypt_value(plaintext: str, key: str) -> str:
    """
    Encrypt a plaintext value using Fernet.
    
    Args:
        plaintext: Value to encrypt
        key: Encryption key (base64-encoded)
        
    Returns:
        str: Encrypted value (base64-encoded)
        
    Raises:
        ValueError: If plaintext is empty or encryption fails
    """
    if not plaintext:
        raise ValueError("Cannot encrypt empty value")
    
    try:
        f = Fernet(key.encode())
        encrypted = f.encrypt(plaintext.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError(f"Failed to encrypt value: {e}")


def decrypt_value(encrypted: str, key: str) -> str:
    """
    Decrypt an encrypted value using Fernet.
    
    Args:
        encrypted: Encrypted value (base64-encoded)
        key: Encryption key (base64-encoded)
        
    Returns:
        str: Decrypted plaintext value
        
    Raises:
        ValueError: If decryption fails
    """
    if not encrypted:
        raise ValueError("Cannot decrypt empty value")
    
    try:
        f = Fernet(key.encode())
        decrypted = f.decrypt(encrypted.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise ValueError(f"Failed to decrypt value: {e}")


def rotate_encryption(old_encrypted: str, old_key: str, new_key: str) -> str:
    """
    Rotate encryption by decrypting with old key and re-encrypting with new key.
    
    Args:
        old_encrypted: Value encrypted with old key
        old_key: Old encryption key
        new_key: New encryption key
        
    Returns:
        str: Value encrypted with new key
    """
    plaintext = decrypt_value(old_encrypted, old_key)
    return encrypt_value(plaintext, new_key)