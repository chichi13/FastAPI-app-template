from typing import Any

from fastapi.responses import JSONResponse

from app.schema import DefaultResponse


class HTTPCustomErrorException(Exception):
    def __init__(
        self, status_code: int, msg: str, details: dict[str, Any] | None = None
    ):
        self.status_code = status_code
        self.msg = msg
        self.details = details if details is not None else {}
        self.response = JSONResponse(
            status_code=self.status_code,
            content=DefaultResponse(msg=self.msg, details=self.details).model_dump(),
        )
        super().__init__(self.msg)

    def __call__(self) -> JSONResponse:
        return self.response
