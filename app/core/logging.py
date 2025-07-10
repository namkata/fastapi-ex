import os
import sys
from loguru import logger, Logger
from app.core.config import settings


def setup_logging() -> Logger:
    """
    Thiết lập cấu hình logging cho ứng dụng sử dụng loguru
    """
    # Tạo thư mục logs nếu chưa tồn tại
    os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)

    # Xóa các handler mặc định
    logger.remove()

    # Thêm handler cho console
    logger.add(
        sys.stderr,
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # Thêm handler cho file
    logger.add(
        settings.LOG_FILE,
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
    )

    # Thêm handler cho các lỗi nghiêm trọng
    logger.add(
        "logs/error.log",
        format=settings.LOG_FORMAT,
        level="ERROR",
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
    )

    # Thêm handler cho các request API
    logger.add(
        "logs/api.log",
        format=settings.LOG_FORMAT,
        level=settings.LOG_LEVEL,
        rotation=settings.LOG_ROTATION,
        retention=settings.LOG_RETENTION,
        compression="zip",
        filter=lambda record: "api" in record["extra"],
    )

    return logger


# Tạo logger instance để sử dụng trong ứng dụng
app_logger = logger
