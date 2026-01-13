from typing import Optional, BinaryIO
from pathlib import Path
# import boto3  # Removed - using local storage only
# from google.cloud import storage as gcs_storage  # Commented out - using local storage
from app.core.config import settings
import aiofiles
import uuid


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
    ) -> str:
        """Upload file to local storage and return path"""
        file_id = str(uuid.uuid4())
        file_key = f"{session_id}/{file_id}_{file_name}"
        
        # AWS S3 - Removed
        # if self.s3_client:
        #     # Upload to S3
        #     self.s3_client.put_object(
        #         Bucket=self.bucket_name,
        #         Key=file_key,
        #         Body=file_content,
        #         ContentType=content_type or "application/octet-stream"
        #     )
        #     url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{file_key}"
        #     return url
        
        # GCP Storage - Commented out
        # elif self.gcs_client:
        #     # Upload to GCS
        #     bucket = self.gcs_client.bucket(self.bucket_name)
        #     blob = bucket.blob(file_key)
        #     blob.upload_from_string(file_content, content_type=content_type)
        #     url = blob.public_url
        #     return url
        
        # Local storage (default and only option now)
        local_path = Path(settings.UPLOAD_DIR) / session_id
        local_path.mkdir(exist_ok=True, parents=True)
        file_path = local_path / f"{file_id}_{file_name}"
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        return str(file_path)
    
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
        """Delete file from local storage"""
        try:
            # AWS S3 - Removed
            # if self.s3_client:
            #     self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            # GCP Storage - Commented out
            # elif self.gcs_client:
            #     bucket = self.gcs_client.bucket(self.bucket_name)
            #     blob = bucket.blob(file_key)
            #     blob.delete()
            # else:
            # Local storage
            file_path = Path(file_key)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False


# Global instance
storage_service = StorageService()
