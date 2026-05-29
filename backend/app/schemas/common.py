from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    code: int
    message: str
    data: DataT | None = None


def success_response(data: DataT, message: str = "success", code: int = 20000) -> ApiResponse[DataT]:
    return ApiResponse(code=code, message=message, data=data)


def empty_response(message: str, code: int) -> ApiResponse[None]:
    return ApiResponse(code=code, message=message, data=None)