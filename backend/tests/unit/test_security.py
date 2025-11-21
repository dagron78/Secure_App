"""
Unit tests for security module.

Tests password hashing, JWT tokens, and encryption functionality.
"""
import pytest
from datetime import datetime, timedelta
import os

# Mock environment variables BEFORE importing app modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["SECRET_KEY"] = "mock-secret-key"
os.environ["JWT_SECRET_KEY"] = "mock-jwt-secret-key"
os.environ["ENCRYPTION_KEY"] = "mock-encryption-key"

from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_token,
)
from app.core.crypto import encrypt_value, decrypt_value


class TestPasswordHashing:
    """Test password hashing and verification."""
    
    def test_password_hash_and_verify(self):
        """Test that password can be hashed and verified."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
    
    def test_wrong_password_fails(self):
        """Test that wrong password fails verification."""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)
        
        assert not verify_password(wrong_password, hashed)
    
    def test_different_hashes_for_same_password(self):
        """Test that same password generates different hashes (salt)."""
        password = "testpassword123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestJWTTokens:
    """Test JWT token creation and verification."""
    
    def test_create_access_token(self):
        """Test access token creation."""
        subject = "test@example.com"
        token = create_access_token(subject)
        
        assert token is not None
        assert isinstance(token, str)
    
    def test_verify_valid_token(self):
        """Test verification of valid token."""
        subject = "test@example.com"
        additional_claims = {"extra": "data"}
        token = create_access_token(subject, additional_claims=additional_claims)
        
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == "test@example.com"
        assert payload["extra"] == "data"
        assert "exp" in payload
    
    def test_verify_expired_token(self):
        """Test that expired token fails verification."""
        subject = "test@example.com"
        # Create token that expires immediately
        token = create_access_token(subject, expires_delta=timedelta(seconds=-1))
        
        payload = decode_token(token)
        # decode_token returns None on error (including expiration)
        assert payload is None
    
    def test_verify_invalid_token(self):
        """Test that invalid token fails verification."""
        invalid_token = "not.a.valid.token"
        payload = decode_token(invalid_token)
        
        assert payload is None


class TestEncryption:
    """Test encryption functionality."""
    
    def test_encrypt_decrypt_string(self):
        """Test encrypting and decrypting a string."""
        plaintext = "sensitive_data_123"
        key = "mock-encryption-key-must-be-32-bytes-base64"
        # Use a valid fernet key for testing
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        
        encrypted = encrypt_value(plaintext, key)
        
        assert encrypted != plaintext
        assert isinstance(encrypted, str)
        
        decrypted = decrypt_value(encrypted, key)
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_dict(self):
        """Test encrypting and decrypting a dictionary."""
        data = {
            "api_key": "sk-abc123",
            "secret": "very_secret",
            "nested": {"key": "value"}
        }
        import json
        plaintext = json.dumps(data)
        
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        
        encrypted = encrypt_value(plaintext, key)
        assert encrypted != str(data)
        
        decrypted = decrypt_value(encrypted, key)
        assert decrypted == plaintext
    
    def test_different_encryption_each_time(self):
        """Test that same plaintext encrypts differently each time."""
        plaintext = "test_data"
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        
        encrypted1 = encrypt_value(plaintext, key)
        encrypted2 = encrypt_value(plaintext, key)
        
        # Different encrypted values due to randomness
        assert encrypted1 != encrypted2
        
        # But both decrypt to same plaintext
        assert decrypt_value(encrypted1, key) == plaintext
        assert decrypt_value(encrypted2, key) == plaintext