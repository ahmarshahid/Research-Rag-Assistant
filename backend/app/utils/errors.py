"""
Custom exceptions for the application.

Exception hierarchy for clear error handling and appropriate HTTP responses.
"""

from typing import Optional


class ApplicationException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self, message: str, status_code: int = 500, error_code: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)


# ==== AUTHENTICATION ERRORS ====
class AuthenticationException(ApplicationException):
    """Base authentication error."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class InvalidCredentialsException(AuthenticationException):
    """Invalid email or password."""

    def __init__(self):
        super().__init__("Invalid email or password")


class TokenExpiredException(AuthenticationException):
    """JWT token has expired."""

    def __init__(self):
        super().__init__("Token has expired")


class InvalidTokenException(AuthenticationException):
    """JWT token is invalid."""

    def __init__(self):
        super().__init__("Invalid or malformed token")


class TokenMissingException(AuthenticationException):
    """JWT token is missing."""

    def __init__(self):
        super().__init__("Authorization header missing")


# ==== AUTHORIZATION ERRORS ====
class AuthorizationException(ApplicationException):
    """User lacks permission for operation."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)


class UserNotFoundException(ApplicationException):
    """User not found in database."""

    def __init__(self):
        super().__init__("User not found", status_code=404)


class DuplicateUserException(ApplicationException):
    """User with email already exists."""

    def __init__(self):
        super().__init__("Email already registered", status_code=409)


# ==== DOCUMENT ERRORS ====
class DocumentException(ApplicationException):
    """Base document error."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code=status_code)


class DocumentNotFound(DocumentException):
    """Document not found."""

    def __init__(self):
        super().__init__("Document not found", status_code=404)


class InvalidFileType(DocumentException):
    """File type not allowed."""

    def __init__(self, extension: str):
        super().__init__(
            f"File type .{extension} not allowed. Only PDF files are supported"
        )


class FileTooLarge(DocumentException):
    """File exceeds maximum size."""

    def __init__(self, size_mb: float, max_mb: int):
        super().__init__(f"File size {size_mb}MB exceeds maximum {max_mb}MB")


class PDFProcessingError(DocumentException):
    """Error processing PDF file."""

    def __init__(self, message: str = "Failed to process PDF"):
        super().__init__(message)


# ==== EMBEDDING ERRORS ====
class EmbeddingException(ApplicationException):
    """Base embedding error."""

    def __init__(self, message: str):
        super().__init__(message, status_code=500)


class EmbeddingGenerationFailed(EmbeddingException):
    """Failed to generate embeddings."""

    def __init__(self, message: str = "Failed to generate embeddings"):
        super().__init__(message)


class VectorDBError(ApplicationException):
    """Error with vector database operations."""

    def __init__(self, message: str = "Vector database operation failed"):
        super().__init__(message, status_code=500)


# ==== LLM ERRORS ====
class LLMException(ApplicationException):
    """Base LLM error."""

    def __init__(self, message: str):
        super().__init__(message, status_code=503)


class LLMAPIError(LLMException):
    """Error calling LLM API."""

    def __init__(self, provider: str, original_error: str):
        super().__init__(f"{provider} API error: {original_error}")


class LLMResponseError(LLMException):
    """Invalid response from LLM."""

    def __init__(self):
        super().__init__("Invalid response from LLM")


# ==== VALIDATION ERRORS ====
class ValidationException(ApplicationException):
    """Input validation failed."""

    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class InvalidQueryException(ValidationException):
    """Invalid search query."""

    def __init__(self):
        super().__init__("Query must be between 1 and 1000 characters")


# ==== RATE LIMITING ====
class RateLimitException(ApplicationException):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            f"Rate limit exceeded. Retry after {retry_after} seconds",
            status_code=429,
        )
        self.retry_after = retry_after


# ==== DATABASE ERRORS ====
class DatabaseException(ApplicationException):
    """Base database error."""

    def __init__(self, message: str = "Database error"):
        super().__init__(message, status_code=500)


class DatabaseConnectionError(DatabaseException):
    """Cannot connect to database."""

    def __init__(self):
        super().__init__("Cannot connect to database")


# ==== CACHE ERRORS ====
class CacheException(ApplicationException):
    """Base cache error."""

    def __init__(self, message: str = "Cache error"):
        super().__init__(message, status_code=500)


class CacheConnectionError(CacheException):
    """Cannot connect to Redis cache."""

    def __init__(self):
        super().__init__("Cache service unavailable")


# ==== GENERIC ALIASES (used across multiple services) ====
class NotFound(ApplicationException):
    """Generic not-found exception used when a resource cannot be located."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ValidationError(ApplicationException):
    """Generic validation error used when input fails business-rule checks."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(message, status_code=400)
