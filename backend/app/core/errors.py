"""Application errors independent of HTTP transport."""
class ApiError(Exception):
    def __init__(self, message, status=400, headers=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.headers = headers
