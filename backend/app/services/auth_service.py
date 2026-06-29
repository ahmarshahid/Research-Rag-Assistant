"""
Authentication service for JWT token management.

Provides:
- Token creation (access + refresh)
- Token verification and validation
- Password hashing and verification
- Token blacklisting (revocation)

Uses:
- python-jose for JWT encoding/decoding
- passlib for password hashing (bcrypt)
- Redis for token blacklist
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.utils.exceptions import (
    AuthenticationException,
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
    TokenMissingException,
)

logger = logging.getLogger(__name__)

# Password hashing context (bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    JWT authentication service.

    Handles:
    - Creating access and refresh tokens
    - Verifying token signatures and expiration
    - Password hashing and comparison
    - Token blacklisting via Redis
    """

    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    # ── Token Creation ────────────────────────────────────────────────────

    def create_access_token(
        self, user_id: UUID, extra_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a JWT access token.

        Args:
            user_id: User UUID to encode in token subject
            extra_claims: Additional claims to include

        Returns:
            Encoded JWT string
        """
        expire = datetime.utcnow() + timedelta(
            minutes=self.access_token_expire_minutes
        )
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access",
            "iat": datetime.utcnow(),
        }
        if extra_claims:
            payload.update(extra_claims)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.debug(f"Created access token for user {user_id}")
        return token

    def create_refresh_token(self, user_id: UUID) -> str:
        """
        Create a JWT refresh token (longer-lived).

        Args:
            user_id: User UUID

        Returns:
            Encoded JWT string
        """
        expire = datetime.utcnow() + timedelta(
            days=self.refresh_token_expire_days
        )
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "refresh",
            "iat": datetime.utcnow(),
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.debug(f"Created refresh token for user {user_id}")
        return token

    # ── Token Verification ────────────────────────────────────────────────

    def verify_token(
        self, token: str, token_type: str = "access"
    ) -> Dict[str, Any]:
        """
        Verify and decode a JWT token.

        Args:
            token: Encoded JWT string
            token_type: Expected token type ('access' or 'refresh')

        Returns:
            Decoded token payload

        Raises:
            TokenMissingException: If token is empty
            TokenExpiredException: If token has expired
            InvalidTokenException: If token is invalid or wrong type
        """
        if not token:
            raise TokenMissingException("Token is required")

        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )

            # Verify token type
            if payload.get("type") != token_type:
                raise InvalidTokenException(
                    f"Expected {token_type} token, got {payload.get('type')}"
                )

            return payload

        except jwt.ExpiredSignatureError:
            raise TokenExpiredException("Token has expired")
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise InvalidTokenException(f"Invalid token: {str(e)}")

    # ── Password Hashing ──────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)


    async def register_user(self, email: str, username: str, password: str, db: Any):
        from sqlalchemy.future import select
        from app.models.database import User
        from app.models.schemas import TokenResponse
        from app.utils.exceptions import ValidationError
        
        stmt = select(User).where((User.email == email) | (User.username == username))
        result = await db.execute(stmt)
        if result.scalars().first():
            raise ValidationError("Email or username already registered")
            
        hashed_password = self.hash_password(password)
        new_user = User(email=email, username=username, password_hash=hashed_password)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        access_token = self.create_access_token(new_user.id)
        refresh_token = self.create_refresh_token(new_user.id)
        
        tokens = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60
        )
        return new_user, tokens

    async def login_user(self, email: str, password: str, db: Any):
        from sqlalchemy.future import select
        from app.models.database import User
        from app.models.schemas import TokenResponse
        
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user or not self.verify_password(password, user.password_hash):
            raise AuthenticationException("Invalid credentials")
            
        access_token = self.create_access_token(user.id)
        refresh_token = self.create_refresh_token(user.id)
        
        tokens = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60
        )
        return user, tokens

    async def refresh_access_token(self, refresh_token: str):
        from app.models.schemas import TokenResponse
        payload = self.verify_token(refresh_token, token_type="refresh")
        user_id = UUID(payload["sub"])
        
        access_token = self.create_access_token(user_id)
        new_refresh_token = self.create_refresh_token(user_id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60
        )

    async def logout_user(self, token: str):
        # We can implement Redis blacklisting here later if needed
        pass

    async def get_user_by_id(self, user_id: Any, db: Any):
        from app.models.database import User
        return await db.get(User, user_id)


# Global singleton instance
auth_service = AuthService()
