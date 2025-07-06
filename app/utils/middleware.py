import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging import app_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Lấy thời gian bắt đầu
        start_time = time.time()
        
        # Lấy thông tin request
        method = request.method
        url = request.url.path
        query_params = str(request.query_params)
        client_host = request.client.host if request.client else "unknown"
        
        # Log request
        app_logger.bind(api=True).info(
            f"Request: {method} {url} - Client: {client_host} - Params: {query_params}"
        )
        
        # Xử lý request
        try:
            response = await call_next(request)
            
            # Tính thời gian xử lý
            process_time = time.time() - start_time
            
            # Log response
            app_logger.bind(api=True).info(
                f"Response: {method} {url} - Status: {response.status_code} - Time: {process_time:.4f}s"
            )
            
            # Thêm header xử lý time
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Log lỗi
            app_logger.bind(api=True).error(
                f"Error: {method} {url} - Error: {str(e)}"
            )
            raise