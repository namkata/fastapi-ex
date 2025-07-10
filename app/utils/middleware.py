import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import app_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time = time.time()

        method = request.method
        url = request.url.path
        query_params = str(request.query_params)
        client_host = request.client.host if request.client else "unknown"

        app_logger.bind(api=True).info(
            f"Request: {method} {url} - Client: {client_host} - Params: {query_params}"
        )

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            app_logger.bind(api=True).info(
                f"Response: {method} {url} - Status: {response.status_code} - Time: {process_time:.4f}s"
            )

            response.headers["X-Process-Time"] = str(process_time)
            return response

        except Exception as e:
            app_logger.bind(api=True).error(f"Error: {method} {url} - Error: {str(e)}")
            raise
