from dataclasses import dataclass


@dataclass(frozen=True)
class AppError(Exception):
    code: int
    message: str
    status_code: int = 400


class InvalidRequestError(AppError):
    def __init__(self, message: str = "Invalid request") -> None:
        super().__init__(code=40000, message=message, status_code=400)


class ResourceNotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(code=40400, message=message, status_code=404)