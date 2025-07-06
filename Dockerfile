FROM python:3.11-slim

WORKDIR /app

# Cài đặt các dependencies cho Pillow và Wand
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    imagemagick \
    libmagickwand-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt các dependencies Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Tạo các thư mục cần thiết
RUN mkdir -p uploads logs static

# Expose port
EXPOSE 8000

# Khởi động ứng dụng
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]