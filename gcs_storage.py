import os
import uuid
from datetime import timedelta

from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()


class GCSStorage:
    def __init__(self):
        self.client = storage.Client()
        self.bucket = self.client.bucket(
            os.getenv("GCS_BUCKET_NAME")
        )

    def upload_pdf(self, file_path: str) -> str:
        blob_name = f"pdfs/{uuid.uuid4()}.pdf"

        blob = self.bucket.blob(blob_name)

        # Upload PDF
        blob.upload_from_filename(
            file_path,
            content_type="application/pdf"
        )

        # Generate a signed URL valid for 1 hour
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET",
        )

        return signed_url