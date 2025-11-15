"""
Unit tests for security module.

Tests password hashing, JWT tokens, and encryption functionality.
"""
import pytest
from datetime import datetime, timedelta

from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    verify_token,
    generate_secure_password
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
        data = {"sub": "test@example.com"}
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
    
    def test_verify_valid_token(self):
        """Test verification of valid token."""
        data = {"sub": "test@example.com", "extra": "data"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "test@example.com"
        assert payload["extra"] == "data"
        assert "exp" in payload
    
    def test_verify_expired_token(self):
        """Test that expired token fails verification."""
        data = {"sub": "test@example.com"}
        # Create token that expires immediately
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        payload = verify_token(token)
        assert payload is None
    
    def test_verify_invalid_token(self):
        """Test that invalid token fails verification."""
        invalid_token = "not.a.valid.token"
        payload = verify_token(invalid_token)
        
        assert payload is None


class TestEncryption:
    """Test encryption functionality."""
    
    def test_encrypt_decrypt_string(self):
        """Test encrypting and decrypting a string."""
        plaintext = "sensitive_data_123"
        encrypted = encrypt_value(plaintext)
        
        assert encrypted != plaintext
        assert isinstance(encrypted, str)
        
        decrypted = decrypt_value(encrypted)
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_dict(self):
        """Test encrypting and decrypting a dictionary."""
        data = {
            "api_key": "sk-abc123",
            "secret": "very_secret",
            "nested": {"key": "value"}
        }
        
        encrypted = encrypt_value(data)
        assert encrypted != str(data)
        
        decrypted = decrypt_value(encrypted)
        assert decrypted == data
    
    def test_different_encryption_each_time(self):
        """Test that same plaintext encrypts differently each time."""
        plaintext = "test_data"
        encrypted1 = encrypt_value(plaintext)
        encrypted2 = encrypt_value(plaintext)
        
        # Different encrypted values due to randomness
        assert encrypted1 != encrypted2
        
        # But both decrypt to same plaintext
        assert decrypt_value(encrypted1) == plaintext
        assert decrypt_value(encrypted2) == plaintext


class TestPasswordGeneration:
    """Test secure password generation."""
    
    def test_generate_password_default_length(self):
        """Test generating password with default length."""
        password = generate_secure_password()
        
        assert len(password) == 32
        assert isinstance(password, str)
    
    def test_generate_password_custom_length(self):
        """Test generating password with custom length."""
        password = generate_secure_password(length=16)
        
        assert len(password) == 16
    
    def test_generated_passwords_are_different(self):
        """Test that generated passwords are unique."""
        password1 = generate_secure_password()
        password2 = generate_secure_password()
        
        assert password1 != password2
    
    def test_password_has_required_characters(self):
        """Test that generated password has mix of characters."""
        password = generate_secure_password(length=50)
        
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        assert has_lower
        assert has_upper
        assert has_digit