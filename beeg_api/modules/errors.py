from base_api.modules.errors import (
    NotFound,
    NetworkError,
    BotDetection,
    ProxyError,
    UnknownNetworkError,
    DownloadFailed,
    AccessDeniedError,
)


class AuthenticationError(AccessDeniedError):
    """A Beeg account session is missing, invalid, expired, or denied."""


__all__ = [
    "NotFound",
    "NetworkError",
    "BotDetection",
    "ProxyError",
    "UnknownNetworkError",
    "DownloadFailed",
    "AuthenticationError",
]
