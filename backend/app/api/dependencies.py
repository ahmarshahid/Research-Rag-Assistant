"""
FastAPI dependency injection for authentication.

This module provides:
- JWT token extraction from Authorization header
- Token verification and validation
- User ID extraction from token
- Dependency for protecting routes
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from uuid import UUID

from app.services.auth_service import auth_service
from app.utils.exceptions import AuthenticationException

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme (for automatic OpenAPI documentation)
security = HTTPBearer(description="JWT Bearer token")


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UUID:
    """
    Extract and validate JWT token from Authorization header.

    **Usage in routes:**
    ```python
    @router.get("/protected")
    async def protected_route(user_id = Depends(get_current_user_id)):
        return {"user_id": user_id}
    ```

    **How it works:**
    1. FastAPI extracts token from "Authorization: Bearer <token>" header
    2. Verifies JWT signature using SECRET_KEY
    3. Checks token expiration
    4. Checks if token is blacklisted (revoked)
    5. Extracts and returns user_id from token payload

    **Errors:**
    - 401 Unauthorized: Invalid/expired/blacklisted token

    Args:
        credentials: HTTPAuthorizationCredentials from Authorization header

    Returns:
        User ID (UUID) extracted from token

    Raises:
        HTTPException: If token invalid or verification fails
    """
    try:
        token = credentials.credentials

        # Verify token and extract payload
        payload = auth_service.verify_token(token, token_type="access")

        # Extract user_id from token subject
        user_id_str = payload.get("sub")
        if not user_id_str:
            logger.warning("Token missing user ID")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )

        try:
            user_id = UUID(user_id_str)
        except ValueError:
            logger.warning(f"Invalid user ID format in token: {user_id_str}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: invalid user ID format"
            )

        logger.debug(f"Authenticated user {user_id}")
        return user_id

    except AuthenticationException as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user_id: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(
        HTTPBearer(auto_error=False))
) -> UUID | None:
    """
    Optional version: Returns user_id if token present and valid, None otherwise.

    **Usage for endpoints that support both authenticated and anonymous access:**
    ```python
    @router.get("/public-data")
    async def get_data(user_id = Depends(get_optional_user_id)):
        if user_id:
            # Return user-specific data
        else:
            # Return public data
    ```

    Args:
        credentials: Optional HTTPAuthorizationCredentials

    Returns:
        User ID if authenticated, None if no valid token
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = auth_service.verify_token(token, token_type="access")
        user_id_str = payload.get("sub")

        if user_id_str:
            return UUID(user_id_str)
        return None

    except Exception as e:
        logger.debug(f"Optional authentication failed (expected): {e}")
        return None
