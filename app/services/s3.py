import mimetypes
import os
import uuid
from typing import BinaryIO, Optional
from urllib.parse import quote_plus
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import app_logger
from app.db.models import Image
from app.schemas.image import StorageType
from app.services.storage_manager import StorageBackend


class S3Service(StorageBackend):
    def _initialize(self) -> None:
        """Initialize S3 client and bucket"""
        try:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
                endpoint_url=settings.S3_ENDPOINT_URL,
                config=Config(s3={"addressing_style": "path"})
            )
            self.bucket_name = settings.S3_BUCKET_NAME
            
            # Test connection and create bucket if needed
            self._create_bucket_if_not_exists()
            self.available = True
            app_logger.info(f"S3 service initialized successfully (bucket: {self.bucket_name})")
        except Exception as e:
            app_logger.error(f"Error initializing S3 service: {e}")
            self.available = False

    def _create_bucket_if_not_exists(self) -> None:
        """
        Create S3 bucket if it doesn't exist.
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            app_logger.info(f"S3 bucket already exists: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                # Bucket không tồn tại, tạo mới
                create_params = {"Bucket": self.bucket_name}
                if settings.AWS_REGION != "us-east-1":
                    create_params["CreateBucketConfiguration"] = {"LocationConstraint": settings.AWS_REGION}
                self.s3_client.create_bucket(**create_params)
                app_logger.info(f"Created S3 bucket: {self.bucket_name}")
            else:
                app_logger.error(f"Error checking S3 bucket: {e}")

    def upload_file(
        self, file: BinaryIO, key: str, content_type: Optional[str] = None, **kwargs
    ) -> bool:
        if not self.available:
            app_logger.warning("S3 service is not available")
            return False
        try:
            file.seek(0)
            extra_args = {"ContentType": content_type} if content_type else {}
            
            # Add any additional S3-specific parameters from kwargs
            if 'metadata' in kwargs:
                extra_args['Metadata'] = kwargs['metadata']
            if 'cache_control' in kwargs:
                extra_args['CacheControl'] = kwargs['cache_control']
            
            self.s3_client.upload_fileobj(
                file, self.bucket_name, key, ExtraArgs=extra_args
            )
            app_logger.info(f"Uploaded file to S3: {key}")
            return True
        except ClientError as e:
            app_logger.error(
                f"AWS ClientError during upload: {e.response['Error']['Message']}"
            )
        except Exception as e:
            app_logger.error(f"Error uploading file to S3: {e}")
        return False

    def upload_from_path(self, file_path: str, key: Optional[str] = None, **kwargs) -> bool:
        if not self.available:
            app_logger.warning("S3 service is not available")
            return False
        try:
            if not os.path.exists(file_path):
                app_logger.error(f"File not found: {file_path}")
                return False
            
            if key is None:
                filename = os.path.basename(file_path)
                ext = os.path.splitext(filename)[-1].lower()
                key = f"uploads/{uuid.uuid4().hex}{ext}"

            content_type, _ = mimetypes.guess_type(file_path)
            with open(file_path, "rb") as f:
                return self.upload_file(f, key, content_type, **kwargs)
        except Exception as e:
            app_logger.error(f"Error uploading file from path to S3: {e}")
            return False

    def upload_from_upload_file(
        self, upload_file: UploadFile, key: Optional[str] = None, **kwargs
    ) -> bool:
        if not self.available:
            app_logger.warning("S3 service is not available")
            return False
        try:
            filename = upload_file.filename or "unnamed_file"
            if key is None:
                # Generate unique key if not provided
                ext = os.path.splitext(filename)[-1].lower()
                key = f"uploads/{uuid.uuid4().hex}{ext}"
            
            content_type = upload_file.content_type or "application/octet-stream"
            upload_file.file.seek(0)  # Ensure we're at the beginning
            return self.upload_file(upload_file.file, key, content_type)
        except Exception as e:
            app_logger.error(f"Error uploading UploadFile to S3: {e}")
            return False

    def get_file_url(self, key: str) -> Optional[str]:
        if not self.available:
            app_logger.warning("S3 service is not available")
            return None
        encoded_key = quote_plus(key)
        replaceEndpoint = settings.S3_ENDPOINT_URL.replace("localstack", "localhost")
        return f"{replaceEndpoint}/{self.bucket_name}/{encoded_key}"

    def delete_file(self, key: str) -> bool:
        if not self.available:
            app_logger.warning("S3 service is not available")
            return False
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            app_logger.info(f"Deleted file from S3: {key}")
            return True
        except ClientError as e:
            app_logger.error(
                f"AWS ClientError during delete: {e.response['Error']['Message']}"
            )
        except Exception as e:
            app_logger.error(f"Error deleting file from S3: {e}")
        return False

    def download_file(self, key: str) -> Optional[bytes]:
        if not self.available:
            app_logger.warning("S3 service is not available")
            return None
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read()
        except ClientError as e:
            app_logger.error(
                f"AWS ClientError during download: {e.response['Error']['Message']}"
            )
        except Exception as e:
            app_logger.error(f"Error downloading file from S3: {e}")
        return None

    def file_exists(self, key: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            app_logger.error(f"Error checking file existence on S3: {e}")
        return False

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        if not self.available:
            app_logger.warning("S3 service is not available")
            return None
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            app_logger.info(f"Generated presigned URL for: {key}")
            return url
        except ClientError as e:
            app_logger.error(
                f"AWS ClientError during presigned URL: {e.response['Error']['Message']}"
            )
        except Exception as e:
            app_logger.error(f"Error generating presigned URL: {e}")
        return None


# Init Service
s3_service = S3Service()


def upload_image_to_s3(db: Session, image_id: int, file: UploadFile) -> Optional[Image]:
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return None

    filename = file.filename or ""
    ext = os.path.splitext(filename)[-1].lower()
    key = f"images/{db_image.id}/{uuid.uuid4().hex}{ext}"

    if not s3_service.upload_from_upload_file(file, key):
        app_logger.error(f"Failed to upload image to S3: {image_id}")
        return None

    url = s3_service.get_file_url(key)

    db_image.storage_type = StorageType.S3
    db_image.s3_key = key
    db_image.s3_url = url or ""
    db_image.storage_path = key or ""

    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    app_logger.info(f"Uploaded image to S3: {image_id}, key: {key}")
    return db_image


def upload_local_image_to_s3(db: Session, image_id: int) -> Optional[Image]:
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return None

    file_path = db_image.file_path or ""
    if not db_image.file_path or not os.path.exists(file_path):
        app_logger.error(f"Image file not found: {file_path}")
        return None

    ext = os.path.splitext(db_image.filename)[-1].lower()
    key = f"images/{db_image.id}/{uuid.uuid4().hex}{ext}"

    if not s3_service.upload_from_path(file_path, key):
        app_logger.error(f"Failed to upload image to S3: {image_id}")
        return None

    url = s3_service.get_file_url(key)

    db_image.storage_type = StorageType.S3
    db_image.s3_key = key
    db_image.s3_url = url or ""
    db_image.storage_path = key or ""

    db.add(db_image)
    db.commit()
    db.refresh(db_image)

    app_logger.info(f"Uploaded local image to S3: {image_id}, key: {key}")
    return db_image


def delete_image_from_s3(db: Session, image_id: int) -> bool:
    db_image = db.query(Image).filter(Image.id == image_id).first()
    if not db_image:
        app_logger.error(f"Image not found: {image_id}")
        return False

    if db_image.storage_type != StorageType.S3.value or not db_image.s3_key:
        app_logger.error(f"Image not stored on S3: {image_id}")
        return False

    if not s3_service.delete_file(db_image.s3_key):
        app_logger.error(f"Failed to delete image from S3: {image_id}")
        return False

    app_logger.info(f"Deleted image from S3: {image_id}")
    return True
