"""
Test JWT token generation
"""

from apflow.cli.jwt_token import _generate_jwt_secret


class TestJwtToken:
    """Test JWT token utilities"""

    def test_generate_jwt_secret_length(self):
        """Test that generated JWT secret is 64 hex chars (32 bytes)"""
        secret = _generate_jwt_secret()
        assert len(secret) == 64
        # Verify it's valid hex
        int(secret, 16)

    def test_generate_jwt_secret_uniqueness(self):
        """Test that each call generates a different secret"""
        secrets = {_generate_jwt_secret() for _ in range(10)}
        assert len(secrets) == 10
