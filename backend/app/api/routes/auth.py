"""
Authentication API routes for user registration, login, and token management.

Endpoints:
- POST /api/auth/register - Create new user account
- POST /api/auth/login - Authenticate and receive JWT tokens
- POST /api/auth/refresh - Get new access token using refresh token
- POST /api/auth/logout - Revoke tokens (blacklist)
- GET /api/auth/me - Get current user profile
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user_id
from app.dependencies import get_db
from app.models.schemas import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import auth_service
from app.utils.exceptions import (
    AuthenticationException,
    DatabaseException,
    ValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    responses={
        201: {"description": "User registered successfully"},
        400: {"description": "Invalid input or user already exists"},
        500: {"description": "Server error"},
    },
)
async def register(
    request: UserRegisterRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Register a new user account.

    **Request:**
    ```json
    {
        "email": "user@example.com",
        "username": "johndoe",
        "password": "SecurePass123!"
    }
    ```

    **Requirements:**
    - Email must be valid and unique
    - Username must be 3-100 characters
    - Password must:
      - Be 8-128 characters
      - Contain uppercase letter
      - Contain digit
      - Contain special character (!@#$%^&*)

    **Response:** Returns JWT tokens (access + refresh)

    **Security:** Password is hashed with bcrypt before storage
    """
    try:
        logger.info(f"Registration attempt: {request.email}")

        # Register user (handles validation)
        user, tokens = await auth_service.register_user(
            email=request.email.lower(),  # Normalize email
            username=request.username,
            password=request.password,
            db=db,
        )

        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
            },
            "tokens": tokens.model_dump(),
            "message": "Registration successful",
        }

    except ValidationError as e:
        logger.warning(f"Registration validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except DatabaseException as e:
        logger.error(f"Registration database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user",
        )
    except Exception as e:
        logger.error(f"Unexpected error during registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post(
    "/login",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="User login",
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials or account locked"},
        400: {"description": "Invalid input"},
        500: {"description": "Server error"},
    },
)
async def login(request: UserLoginRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Authenticate user and receive JWT tokens.

    **Request:**
    ```json
    {
        "email": "user@example.com",
        "password": "SecurePass123!"
    }
    ```

    **Response:** Returns access token (15 min) + refresh token (7 days)

    **Security:**
    - Passwords compared using bcrypt
    - Failed login attempts tracked (lockout after 5 attempts)
    - Account lockout lasts 1 hour

    **Token Usage:**
    - Include access token in Authorization header: `Bearer <token>`
    - Use refresh token to get new access token when expired
    """
    try:
        logger.info(f"Login attempt: {request.email}")

        # Authenticate user
        user, tokens = await auth_service.login_user(
            email=request.email.lower(), password=request.password, db=db
        )

        return {
            "user": {
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
            },
            "tokens": tokens.model_dump(),
            "message": "Login successful",
        }

    except AuthenticationException as e:
        logger.warning(f"Login failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Login validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    responses={
        200: {"description": "Token refreshed"},
        401: {"description": "Invalid or expired refresh token"},
        500: {"description": "Server error"},
    },
)
async def refresh_token(
    refresh_token: str = Header(..., description="Refresh token from login"),
) -> TokenResponse:
    """
    Generate a new access token using a valid refresh token.

    **When to use:**
    - Access token has expired (usually after 15 minutes)
    - User remains logged in and needs to continue using API

    **Request Header:**
    ```
    refresh-token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```

    **Response:** New TokenResponse with fresh access token

    **Behavior:**
    - Refresh token remains valid for 7 days
    - New access token valid for 15 minutes
    - Can call this endpoint multiple times with same refresh token

    **Example flow:**
    1. User logs in → receives access_token (exp: +15 min) + refresh_token (exp: +7 days)
    2. After 15 min: access token expires
    3. Call /refresh with refresh_token → get new access_token
    4. Repeat step 2-3 for up to 7 days
    """
    try:
        logger.info("Token refresh requested")

        tokens = await auth_service.refresh_access_token(refresh_token)

        logger.info("Token refreshed successfully")
        return tokens

    except AuthenticationException as e:
        logger.warning(f"Token refresh failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user",
    responses={
        200: {"description": "Logout successful"},
        401: {"description": "Not authenticated"},
        500: {"description": "Server error"},
    },
)
async def logout(
    user_id=Depends(get_current_user_id),
    authorization: str = Header(None, description="Bearer token"),
) -> dict:
    """
    Logout user by revoking their token.

    **How it works:**
    - Extracts token from Authorization header
    - Adds token to blacklist (Redis)
    - Blacklisted tokens are rejected on all endpoints

    **Request Header:**
    ```
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```

    **Response:** Confirmation message

    **Security:**
    - Token is revoked immediately
    - Cannot reuse token after logout
    - Requires valid access token to logout
    """
    try:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header",
            )

        # Extract token from "Bearer <token>"
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise ValueError("Invalid authorization scheme")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format",
            )

        logger.info(f"Logout attempt for user {user_id}")

        # Blacklist token
        await auth_service.logout_user(token)

        return {"message": "Logout successful", "user_id": str(user_id)}

    except HTTPException:
        raise
    except AuthenticationException as e:
        logger.warning(f"Logout failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    responses={
        200: {"description": "User profile retrieved"},
        401: {"description": "Not authenticated"},
        404: {"description": "User not found"},
        500: {"description": "Server error"},
    },
)
async def get_current_user(
    user_id=Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Get authenticated user's profile information.

    **Request Header:**
    ```
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```

    **Response:** User profile with id, email, username, created_at, is_active

    **Security:**
    - Requires valid access token
    - Only current user can access their profile
    - Token verified on each request

    **Example Response:**
    ```json
    {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "email": "user@example.com",
        "username": "johndoe",
        "created_at": "2024-01-15T10:30:00",
        "is_active": true
    }
    ```
    """
    try:
        logger.info(f"Fetching profile for user {user_id}")

        user = await auth_service.get_user_by_id(user_id, db)

        if not user:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserResponse.model_validate(user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user profile",
        )
