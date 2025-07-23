import os

# Tạm thời bỏ qua thư viện Wand do vấn đề với MagickWand
# from wand.image import Image as WandImage
from datetime import datetime
from typing import List, Optional, Tuple

from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import app_logger
from app.db.models import Image, ProcessingTask, Thumbnail
from app.schemas.image import ProcessStatus
from app.services.s3 import s3_service
from app.services.seaweedfs import seaweedfs_service


class ImageProcessor:
    @staticmethod
    def create_thumbnail(
        image_path: str, size: Tuple[int, int], output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Tạo thumbnail từ ảnh gốc
        """
        try:
            # Mở ảnh gốc
            with PILImage.open(image_path) as img:
                # Resize ảnh
                img.thumbnail(size)

                # Tạo đường dẫn output nếu chưa có
                if output_path is None:
                    directory = os.path.dirname(image_path)
                    filename = (
                        f"thumb_{size[0]}x{size[1]}_{os.path.basename(image_path)}"
                    )
                    output_path = os.path.join(directory, filename)

                # Tạo thư mục nếu chưa tồn tại
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Lưu thumbnail
                img.save(output_path)

                return output_path
        except Exception as e:
            app_logger.error(f"Error creating thumbnail: {e}")
            return None

    @staticmethod
    def resize_image(
        image_path: str, size: Tuple[int, int], output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Resize ảnh
        """
        try:
            # Mở ảnh gốc
            with PILImage.open(image_path) as img:
                # Resize ảnh
                resized_img = img.resize(size)

                # Tạo đường dẫn output nếu chưa có
                if output_path is None:
                    directory = os.path.dirname(image_path)
                    filename = (
                        f"resized_{size[0]}x{size[1]}_{os.path.basename(image_path)}"
                    )
                    output_path = os.path.join(directory, filename)

                # Tạo thư mục nếu chưa tồn tại
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Lưu ảnh đã resize
                resized_img.save(output_path)

                return output_path
        except Exception as e:
            app_logger.error(f"Error resizing image: {e}")
            return None

    @staticmethod
    def crop_image(
        image_path: str,
        box: Tuple[int, int, int, int],
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """
        Crop ảnh (box: left, upper, right, lower)
        """
        try:
            # Mở ảnh gốc
            with PILImage.open(image_path) as img:
                # Crop ảnh
                cropped_img = img.crop(box)

                # Tạo đường dẫn output nếu chưa có
                if output_path is None:
                    directory = os.path.dirname(image_path)
                    filename = f"cropped_{box[0]}_{box[1]}_{box[2]}_{box[3]}_{os.path.basename(image_path)}"
                    output_path = os.path.join(directory, filename)

                # Tạo thư mục nếu chưa tồn tại
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Lưu ảnh đã crop
                cropped_img.save(output_path)

                return output_path
        except Exception as e:
            app_logger.error(f"Error cropping image: {e}")
            return None

    @staticmethod
    def apply_filter(
        image_path: str, filter_type: str, output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Áp dụng filter cho ảnh (sử dụng PIL thay vì Wand)
        """
        try:
            # Mở ảnh gốc
            with PILImage.open(image_path) as img:
                # Áp dụng filter
                if filter_type == "grayscale":
                    # Chuyển sang grayscale
                    filtered_img = img.convert("L")
                else:
                    # Các filter khác tạm thời chỉ hỗ trợ grayscale
                    app_logger.warning(
                        f"Filter {filter_type} not implemented with PIL, using grayscale instead"
                    )
                    filtered_img = img.convert("L")

                # Tạo đường dẫn output nếu chưa có
                if output_path is None:
                    directory = os.path.dirname(image_path)
                    filename = f"{filter_type}_{os.path.basename(image_path)}"
                    output_path = os.path.join(directory, filename)

                # Tạo thư mục nếu chưa tồn tại
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Lưu ảnh đã áp dụng filter
                filtered_img.save(output_path)

                return output_path
        except Exception as e:
            app_logger.error(f"Error applying filter: {e}")
            return None

    @staticmethod
    def rotate_image(
        image_path: str, angle: float, output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Xoay ảnh
        """
        try:
            # Mở ảnh gốc
            with PILImage.open(image_path) as img:
                # Xoay ảnh
                rotated_img = img.rotate(angle, expand=True)

                # Tạo đường dẫn output nếu chưa có
                if output_path is None:
                    directory = os.path.dirname(image_path)
                    filename = f"rotated_{angle}_{os.path.basename(image_path)}"
                    output_path = os.path.join(directory, filename)

                # Tạo thư mục nếu chưa tồn tại
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Lưu ảnh đã xoay
                rotated_img.save(output_path)

                return output_path
        except Exception as e:
            app_logger.error(f"Error rotating image: {e}")
            return None


# Khởi tạo processor
image_processor = ImageProcessor()


def process_image(db: Session, task_id: int) -> bool:
    """
    Xử lý ảnh theo task
    """
    # Lấy thông tin task
    task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
    if not task:
        app_logger.error(f"Task not found: {task_id}")
        return False

    # Lấy thông tin ảnh
    image = db.query(Image).filter(Image.id == task.image_id).first()
    if not image:
        app_logger.error(f"Image not found: {task.image_id}")

        # Cập nhật trạng thái task
        task.status = ProcessStatus.FAILED
        task.error = "Image not found"
        task.completed_at = datetime.utcnow()
        db.add(task)
        db.commit()

        return False

    # Kiểm tra file ảnh có tồn tại không
    if not image.file_path or not os.path.exists(image.file_path):
        # Nếu ảnh lưu trên SeaweedFS hoặc S3, tải về local
        if image.storage_type == "seaweedfs" and image.seaweedfs_fid:
            # Tải từ SeaweedFS
            file_data = seaweedfs_service.download_file(image.storage_path)
            if not file_data:
                app_logger.error(f"Failed to download image from SeaweedFS: {image.id}")

                # Cập nhật trạng thái task
                task.status = ProcessStatus.FAILED
                task.error = "Failed to download image from SeaweedFS"
                task.completed_at = datetime.utcnow()
                db.add(task)
                db.commit()

                return False

            # Lưu vào local
            local_path = os.path.join(settings.UPLOAD_DIR, image.filename)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_data)

            # Cập nhật đường dẫn local
            image.file_path = local_path
            db.add(image)
            db.commit()

        elif image.storage_type == "s3" and image.s3_key:
            # Tải từ S3
            file_data = s3_service.download_file(image.s3_key)
            if not file_data:
                app_logger.error(f"Failed to download image from S3: {image.id}")

                # Cập nhật trạng thái task
                task.status = ProcessStatus.FAILED
                task.error = "Failed to download image from S3"
                task.completed_at = datetime.utcnow()
                db.add(task)
                db.commit()

                return False

            # Lưu vào local
            local_path = os.path.join(settings.UPLOAD_DIR, image.filename)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_data)

            # Cập nhật đường dẫn local
            image.file_path = local_path
            db.add(image)
            db.commit()
        else:
            app_logger.error(f"Image file not found: {image.file_path}")

            # Cập nhật trạng thái task
            task.status = ProcessStatus.FAILED
            task.error = "Image file not found"
            task.completed_at = datetime.utcnow()
            db.add(task)
            db.commit()

            return False

    # Cập nhật trạng thái task
    task.status = ProcessStatus.PROCESSING
    db.add(task)
    db.commit()

    try:
        # Parse params
        params = eval(task.params) if task.params else {}

        # Xử lý ảnh theo loại task
        result_path = None

        if task.task_type == "resize":
            width = params.get("width", 800)
            height = params.get("height", 600)
            result_path = image_processor.resize_image(image.file_path, (width, height))

        elif task.task_type == "crop":
            left = params.get("left", 0)
            upper = params.get("upper", 0)
            right = params.get("right", 100)
            lower = params.get("lower", 100)
            result_path = image_processor.crop_image(
                image.file_path, (left, upper, right, lower)
            )

        elif task.task_type == "filter":
            filter_type = params.get("filter_type", "grayscale")
            result_path = image_processor.apply_filter(image.file_path, filter_type)

        elif task.task_type == "rotate":
            angle = params.get("angle", 90)
            result_path = image_processor.rotate_image(image.file_path, angle)

        elif task.task_type == "thumbnail":
            width = params.get("width", 200)
            height = params.get("height", 200)
            size = params.get("size", "small")

            result_path = image_processor.create_thumbnail(
                image.file_path, (width, height)
            )

            # Tạo bản ghi Thumbnail
            if result_path:
                thumbnail = Thumbnail(
                    image_id=image.id,
                    size=size,
                    width=width,
                    height=height,
                    file_path=result_path,
                    storage_type="local",
                    storage_path=result_path,
                )
                db.add(thumbnail)
                db.commit()

        # Kiểm tra kết quả
        if not result_path:
            app_logger.error(
                f"Failed to process image: {image.id}, task: {task.task_type}"
            )

            # Cập nhật trạng thái task
            task.status = ProcessStatus.FAILED
            task.error = f"Failed to process image: {task.task_type}"
            task.completed_at = datetime.utcnow()
            db.add(task)
            db.commit()

            return False

        # Cập nhật kết quả task
        task.status = ProcessStatus.COMPLETED
        task.result = str({"result_path": result_path})
        task.completed_at = datetime.utcnow()
        db.add(task)
        db.commit()

        # Cập nhật trạng thái ảnh
        image.is_processed = True
        image.process_status = ProcessStatus.COMPLETED
        db.add(image)
        db.commit()

        app_logger.info(f"Processed image: {image.id}, task: {task.task_type}")
        return True

    except Exception as e:
        app_logger.error(f"Error processing image: {e}")

        # Cập nhật trạng thái task
        task.status = ProcessStatus.FAILED
        task.error = str(e)
        task.completed_at = datetime.utcnow()
        db.add(task)
        db.commit()

        return False


def create_thumbnails(db: Session, image_id: int) -> List[Thumbnail]:
    """
    Tạo các thumbnail cho ảnh và upload lên cùng storage type với ảnh gốc
    """
    from app.services.upload_service import UploadService
    
    # Lấy thông tin ảnh
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        app_logger.error(f"Image not found: {image_id}")
        return []

    # Download from remote if necessary
    if not image.file_path or not os.path.exists(image.file_path):
        if image.storage_type == "seaweedfs" and image.seaweedfs_fid:
            file_data = seaweedfs_service.download_file(image.storage_path)
            if not file_data:
                app_logger.error(f"Failed to download image from SeaweedFS for image_id {image.id} with FID: {image.seaweedfs_fid}")
                return []
            
            if not seaweedfs_service.available:
                app_logger.error("SeaweedFS service is unavailable")
                return []
            
            if not seaweedfs_service.file_exists(image.storage_path):
                app_logger.error(f"File does not exist on SeaweedFS for FID: {image.seaweedfs_fid}")
                return []
            
            local_path = os.path.join(settings.UPLOAD_DIR, image.filename)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_data)
            image.file_path = local_path
            db.add(image)
            db.commit()
        elif image.storage_type == "s3" and image.s3_key:
            file_data = s3_service.download_file(image.s3_key)
            if not file_data:
                app_logger.error(f"Failed to download image from S3: {image.id}")
                return []
            local_path = os.path.join(settings.UPLOAD_DIR, image.filename)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(file_data)
            image.file_path = local_path
            db.add(image)
            db.commit()
        else:
            app_logger.error(f"Image file not found: {image.file_path}")
            return []

    # Định nghĩa các kích thước thumbnail
    thumbnail_sizes = [
        {"size": "small", "width": 150, "height": 150},
        {"size": "medium", "width": 300, "height": 300},
        {"size": "large", "width": 600, "height": 600},
    ]

    thumbnails = []
    upload_service = UploadService()

    # Tạo các thumbnail
    for size_info in thumbnail_sizes:
        try:
            width_raw = size_info.get("width")
            height_raw = size_info.get("height")

            if not isinstance(width_raw, (int, float, str)) or not isinstance(
                height_raw, (int, float, str)
            ):
                raise ValueError("Invalid size values")

            # Convert to integer dimensions
            width = int(float(width_raw))
            height = int(float(height_raw))

            # Create thumbnail locally first
            result_path = image_processor.create_thumbnail(
                str(image.file_path), (width, height)
            )

            if not result_path:
                app_logger.error(f"Failed to create thumbnail: {size_info['size']}")
                continue

            # Determine storage type and upload thumbnail
            storage_type = image.storage_type or "local"
            storage_path = result_path
            seaweedfs_fid = None
            s3_key = None
            s3_url = None
            
            # Upload to same storage as original image
            if storage_type == "s3":
                from app.schemas.image import StorageType
                # Generate unique key for thumbnail
                thumb_filename = os.path.basename(result_path)
                thumb_key = f"thumbnails/{image.id}_{size_info['size']}_{thumb_filename}"
                
                # Upload to S3
                upload_result = upload_service.upload_from_path(
                    file_path=result_path,
                    user_id=image.owner_id,
                    storage_type=StorageType.S3,
                    custom_key=thumb_key
                )
                
                if upload_result["success"]:
                    storage_path = upload_result["key"]
                    s3_key = upload_result["key"]
                    s3_url = upload_result["url"]
                    app_logger.info(f"Uploaded thumbnail to S3: {thumb_key}")
                else:
                    app_logger.error(f"Failed to upload thumbnail to S3: {upload_result.get('error')}")
                    storage_type = "local"  # Fallback to local
                    
            elif storage_type == "seaweedfs":
                from app.schemas.image import StorageType
                # Upload to SeaweedFS
                upload_result = upload_service.upload_from_path(
                    file_path=result_path,
                    user_id=image.owner_id,
                    storage_type=StorageType.SEAWEEDFS
                )
                
                if upload_result["success"]:
                    storage_path = upload_result["key"]
                    # Get FID from SeaweedFS service
                    backend = upload_service.storage_manager.get_backend("seaweedfs")
                    seaweedfs_fid = backend.get_fid_for_key(upload_result["key"])
                    app_logger.info(f"Uploaded thumbnail to SeaweedFS: {upload_result['key']}")
                else:
                    app_logger.error(f"Failed to upload thumbnail to SeaweedFS: {upload_result.get('error')}")
                    storage_type = "local"  # Fallback to local

            # Tạo bản ghi Thumbnail
            thumbnail = Thumbnail(
                image_id=image.id,
                size=size_info["size"],
                width=size_info["width"],
                height=size_info["height"],
                file_path=result_path,
                storage_type=storage_type,
                storage_path=storage_path,
                seaweedfs_fid=seaweedfs_fid,
                s3_key=s3_key,
                s3_url=s3_url,
            )
            db.add(thumbnail)
            db.commit()
            db.refresh(thumbnail)

            thumbnails.append(thumbnail)

            app_logger.info(
                f"Created thumbnail: {thumbnail.id}, size: {size_info['size']}, storage: {storage_type}"
            )

        except Exception as e:
            app_logger.error(f"Error creating thumbnail: {e}")

    return thumbnails
