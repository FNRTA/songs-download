class DeezerException(Exception):
    """Base exception for Deezer client errors"""
    pass

class Deezer404Exception(DeezerException):
    """Resource not found"""
    pass

class Deezer403Exception(DeezerException):
    """Authentication required"""
    pass

class DeezerApiException(DeezerException):
    """API-related errors"""
    pass
