class ApplicationError(Exception):
    def __init__(
        self,
        message: str,
        error_code: str = "APPLICATION_ERROR",
        status_code: int = 400,
        *,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
