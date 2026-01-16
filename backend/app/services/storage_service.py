from typing import Optional, BinaryIO, Tuple
from pathlib import Path
# import boto3  # Removed - using local storage only
# from google.cloud import storage as gcs_storage  # Commented out - using local storage
from app.core.config import settings
from app.core.logging_config import get_logger
import aiofiles
import uuid

logger = get_logger(__name__)


class StorageService:
    """Service for handling file storage (local storage only)"""
    
    def __init__(self):
        # self.s3_client = None  # Removed - using local storage only
        # self.gcs_client = None  # Commented out - using local storage
        # self.bucket_name = None  # Not needed for local storage
        # self._initialize_storage()  # Not needed for local storage
        pass  # Using local storage only, no initialization needed
    
    # def _initialize_storage(self):
    #     """Initialize cloud storage client - Disabled, using local storage"""
    #     # GCP Storage - Commented out
    #     # if settings.USE_GCP:
    #     #     if settings.GCP_PROJECT_ID and settings.GCP_STORAGE_BUCKET:
    #     #         self.gcs_client = gcs_storage.Client(project=settings.GCP_PROJECT_ID)
    #     #         self.bucket_name = settings.GCP_STORAGE_BUCKET
    #     # else:
    #     #     # AWS S3 - Removed
    #     #     if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY and settings.S3_BUCKET_NAME:
    #     #         self.s3_client = boto3.client(
    #     #             's3',
    #     #             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    #     #             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    #     #             region_name=settings.AWS_REGION
    #     #         )
    #     #         self.bucket_name = settings.S3_BUCKET_NAME
    
    async def upload_file(
        self,
        file_content: bytes,
        file_name: str,
        session_id: str,
        content_type: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Upload file to local storage and return a tuple of (file_id, url).
        """
        
        file_id = str(uuid.uuid4())
        
        # Local storage (default and only option now)
        local_path = Path(settings.UPLOAD_DIR) / session_id
        local_path.mkdir(exist_ok=True, parents=True)
        file_path = local_path / f"{file_id}_{file_name}"
        
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
            # Return a URL path that can be served by the API's static files mount (/uploads/...)
            uploads_dir_name = Path(settings.UPLOAD_DIR).name
            url = f"/{uploads_dir_name}/{session_id}/{file_id}_{file_name}"
            return file_id, url
        except Exception as e:
            logger.error(f"Error uploading file {file_name}: {e}", exc_info=True)
            raise
    
    async def get_file_url(self, file_key: str, expires_in: int = 3600) -> str:
        """Get file path (local storage)"""
        # AWS S3 - Removed
        # if self.s3_client:
        #     url = self.s3_client.generate_presigned_url(
        #         'get_object',
        #         Params={'Bucket': self.bucket_name, 'Key': file_key},
        #         ExpiresIn=expires_in
        #     )
        #     return url
        # GCP Storage - Commented out
        # elif self.gcs_client:
        #     bucket = self.gcs_client.bucket(self.bucket_name)
        #     blob = bucket.blob(file_key)
        #     url = blob.generate_signed_url(expiration=expires_in)
        #     return url
        # else:
        # Local storage
        return file_key
    
    async def delete_file(self, file_key: str) -> bool:
        """Delete file from local storage or by URL path"""
        try:
            # Local storage
            file_path = Path(file_key)
            if not file_path.exists():
                # file_key might be a URL path like /uploads/session/file
                uploads_dir_name = Path(settings.UPLOAD_DIR).name
                if isinstance(file_key, str) and file_key.startswith(f"/{uploads_dir_name}/"):
                    rel = file_key[len(f"/{uploads_dir_name}/"):]
                    file_path = Path(settings.UPLOAD_DIR) / rel
            
            if file_path.exists():
                file_path.unlink()
                return True
            else:
                logger.warning(f"File not found for deletion: {file_key}")
                return False
        except Exception as e:
            logger.error(f"Error deleting file {file_key}: {e}", exc_info=True)
            return False


# Global instance
storage_service = StorageService()
