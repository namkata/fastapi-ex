# FastAPI Example Project

Dự án FastAPI với các chức năng:
- API CRUD cơ bản
- Hệ thống logging
- Upload nhiều file ảnh
- Xử lý process khi người dùng upload nhiều ảnh
- Quản lý tra cứu ảnh
- Tích hợp SeaweedFS để quản lý kích thước và chỉnh sửa ảnh
- Sử dụng LocalStack để mô phỏng AWS S3

## Cài đặt

```bash
# Cài đặt dependencies
pip install -r requirements.txt

# Khởi động ứng dụng
uvicorn app.main:app --reload
```

## Cấu trúc dự án

```
├── app/                    # Thư mục chính của ứng dụng
│   ├── api/                # API endpoints
│   ├── core/               # Cấu hình cơ bản
│   ├── db/                 # Database models và connections
│   ├── schemas/            # Pydantic models
│   ├── services/           # Business logic
│   ├── utils/              # Utility functions
│   └── main.py             # Entry point
├── logs/                   # Log files
├── tests/                  # Unit tests
├── .env                    # Environment variables
├── .gitignore             # Git ignore file
├── docker-compose.yml      # Docker compose configuration
├── Dockerfile              # Docker configuration
└── requirements.txt        # Project dependencies
```