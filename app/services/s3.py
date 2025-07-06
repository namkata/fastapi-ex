import os
import io
from typing import Optional, Dict, Any, BinaryIO
from fastapi import UploadFile
import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import app_logger
from app.db.models import Image
from app.schemas.image import StorageType


class S3Service:
    def __init__(self):
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
                endpoint_url=settings.S3_ENDPOINT_URL,
            )
            self.bucket_name = settings.S3_BUCKET_NAME
            self.available = True
            
            # Tạm thời bỏ qua việc tạo bucket khi khởi động
            # self._create_bucket_if_not_exists()
        except Exception as e:
            app_logger.error(f"Error initializing S3 service: {e}")
            self.available = False
    
    def _create_bucket_if_not_exists(self):
        """
        Tạo bucket nếu chưa tồn tại
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            app_logger.info(f"S3 bucket already exists: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket không tồn tại, tạo mới
                self.s3_client.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': settings.AWS_REGION
                    }
                )
                app_logger.info(f"Created S3 bucket: {self.bucket_name}")
            else:
                app_logger.error(f"Error checking S3 bucket: {e}")
    
    def upload_file(self, file: BinaryIO, key: str, content_type: Optional[str] = None) -> bool:
        """
        Upload file to S3
        """
        if not self.available:
            app_logger.warning("S3 service is not available")
            return False
            
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                key,
                ExtraArgs=extra_args
            )
            app_logger.info(f"Uploaded file to S3: {key}")
            return True
        except Exception as e:
            app_logger.error(f"Error uploading file to S3: {e}")
            return False
    
    def upload_from_path(self, file_path: str, key: Optional[str] = None) -> bool:
        """
        Upload file from local path to S3
        """
        if not self.available:
            app_logger.warning("S3 service is not available")
            return False
            
        try:
            if key is None:
                key = os.path.basename(file_path)
            
            content_type = None
            if file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
                content_type = 'image/jpeg'
            elif file_path.lower().endswith('.png'):
                content_type = 'image/png'
            elif file_path.lower().endswith('.gif'):
                content_type = 'image/gif'
            
            with open(file_path, 'rb') as f:
                return self.upload_file(f, key, content_type)
        except Exception as e:
            app_logger.error(f"Error uploading file from path to S3: {e}")
            return False
    
    def upload_from_upload_file(self, upload_file: UploadFile, key: Optional[str] = None) -> bool:
        """
        Upload UploadFile to S3
        """
        if not self.available:
            app_logger.warning("S3 service is not available")
            return False
            
        try:
            if key is None:
                key = upload_file.filename
            
            # Read file content
            file_content = upload_file.file.read()
            upload_file.file.seek(0)  # Reset file position
            
            # Upload to S3
            file_obj = io.BytesIO(file_content)
            return self.upload_file(file_obj, key, upload_file.content_type)
        except Exception as e:
            app_logger.error(f"Error uploading UploadFile to S3: {e}")
            return False
    
    def get_file_url(self, key: str) -> Optional[str]:
        """
        Get file URL from S3
        """
        if not self.available:
            app_logger.warning("S3 service is not available")
            return None
            
        return f"{settings.S3_ENDPOINT_URL}/{self.bucket_name}/{key}"
    
    def delete_file(self, key: str) -> bool:
        """
        Delete file from S3
        """
        if not self.available:
            app_logger.warning("S3 service is not available")
            return False
            
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            app_logger.info(f"Deleted file from S3: {key}")
            return True
        except Exception as e:
            app_logger.error(f"Error deleting file from S3: {e}")
            return False
    
    def download_file(self, key: str) -> Optional[bytes]:
        """
        Download file from S3
        """
        if not self.available:
            app_logger.warning("S3 service is not available")
            return None
            
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body'].read()
        except Exception as e:
            app_logger.error(f"Error downloading file from S3: {e}")
            return None


# Khởi tạo service
s3_service = S3Service()


def upload_image_to_s3(db: Session, image_id: int, file: UploadFile) -> Optional[Image]:
    """
    Upload ảnh lên S3 và cập nhật bản ghi Image
    """
    # Lấy thông tin ảnh
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return None
    
    # Tạo key cho S3
    ext = file.filename.split('.')[-1].lower()
    key = f"images/{db_image.id}/{db_image.filename}"
    
    # Upload lên S3
    result = s3_service.upload_from_upload_file(file, key)
    if not result:
        app_logger.error(f"Failed to upload image to S3: {image_id}")
        return None
    
    # Lấy URL
    url = s3_service.get_file_url(key)
    
    # Cập nhật bản ghi Image
    db_image.storage_type = StorageType.S3
    db_image.s3_key = key
    db_image.s3_url = url
    db_image.storage_path = url
    
    # Lưu vào database
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    app_logger.info(f"Uploaded image to S3: {image_id}, key: {key}")
    return db_image


def upload_local_image_to_s3(db: Session, image_id: int) -> Optional[Image]:
    """
    Upload ảnh từ local lên S3 và cập nhật bản ghi Image
    """
    # Lấy thông tin ảnh
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return None
    
    # Kiểm tra file có tồn tại không
    if not db_image.file_path or not os.path.exists(db_image.file_path):
        app_logger.error(f"Image file not found: {db_image.file_path}")
        return None
    
    # Tạo key cho S3
    key = f"images/{db_image.id}/{db_image.filename}"
    
    # Upload lên S3
    result = s3_service.upload_from_path(db_image.file_path, key)
    if not result:
        app_logger.error(f"Failed to upload image to S3: {image_id}")
        return None
    
    # Lấy URL
    url = s3_service.get_file_url(key)
    
    # Cập nhật bản ghi Image
    db_image.storage_type = StorageType.S3
    db_image.s3_key = key
    db_image.s3_url = url
    db_image.storage_path = url
    
    # Lưu vào database
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    app_logger.info(f"Uploaded local image to S3: {image_id}, key: {key}")
    return db_image


def delete_image_from_s3(db: Session, image_id: int) -> bool:
    """
    Xóa ảnh khỏi S3
    """
    # Lấy thông tin ảnh
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return False
    
    # Kiểm tra ảnh có lưu trên S3 không
    if db_image.storage_type != StorageType.S3 or not db_image.s3_key:
        app_logger.error(f"Image not stored on S3: {image_id}")
        return False
    
    # Xóa khỏi S3
    result = s3_service.delete_file(db_image.s3_key)
    if not result:
        app_logger.error(f"Failed to delete image from S3: {image_id}")
        return False
    
    app_logger.info(f"Deleted image from S3: {image_id}")
    return True