# backend/utils/custom_exceptions.py
"""Custom exceptions for structured error handling across services."""

from fastapi import HTTPException, status

class ServiceException(HTTPException):
    """Base class for service-level exceptions mapped to HTTP errors."""
    def __init__(self, status_code: int, detail: str, headers: dict = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)

# --- HTTP 4xx Client Errors ---

class UserNotFoundError(ServiceException):
    """Raised when a user is not found (404)."""
    def __init__(self, detail: str = "User not found.", headers: dict = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail, headers=headers)

class ResourceNotFoundError(ServiceException):
    """Raised when a specific resource (e.g., job post, proposal) is not found (404)."""
    def __init__(self, detail: str = "Resource not found.", headers: dict = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail, headers=headers)

class PolicyViolationError(ServiceException):
    """Raised when an action is blocked by compliance or enforcement rules (403)."""
    def __init__(self, detail: str = "Action blocked by organizational policy or compliance rule.", headers: dict = None):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail, headers=headers)

class ConflictError(ServiceException):
    """Raised when a resource already exists or a conflicting action is attempted (409)."""
    def __init__(self, detail: str = "Resource conflict or already exists.", headers: dict = None):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail, headers=headers)

class InvalidInputError(ServiceException):
    """Raised for bad request data or validation failure (400)."""
    def __init__(self, detail: str = "Invalid input or data format provided.", headers: dict = None):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail, headers=headers)

# --- HTTP 5xx Server Errors ---

class ServiceUnavailableError(ServiceException):
    """Raised when a critical backend dependency (e.g., Ollama, DuckDB) is down (503)."""
    def __init__(self, detail: str = "Critical external service is currently unavailable.", headers: dict = None):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail, headers=headers)

class DataProcessingError(ServiceException):
    """Raised when an internal processing task fails unexpectedly (500)."""
    def __init__(self, detail: str = "Internal data processing failure.", headers: dict = None):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail, headers=headers)