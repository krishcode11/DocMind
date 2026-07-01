import json
import os
import uuid
from datetime import timedelta

from dotenv import load_dotenv
from google.cloud import storage
from google.oauth2 import service_account

load_dotenv()


class GCSStorage:
    def __init__(self):
        bucket_name = os.getenv("GCS_BUCKET_NAME")

        if not bucket_name:
            raise ValueError("GCS_BUCKET_NAME environment variable is missing.")

        credentials_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON")

        if credentials_json:
            # Production (Render)
            service_account_info = json.loads(credentials_json)

            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )

            self.client = storage.Client(
                project=service_account_info["project_id"],
                credentials=credentials,
            )

        else:
            # Local Development
            self.client = storage.Client()

        self.bucket = self.client.bucket(bucket_name)

    def upload_pdf(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        blob_name = f"pdfs/{uuid.uuid4()}.pdf"

        blob = self.bucket.blob(blob_name)

        blob.upload_from_filename(
            file_path,
            content_type="application/pdf",
        )

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=1),
            method="GET",
        )

        return signed_url

    def delete_file(self, blob_name: str):
        blob = self.bucket.blob(blob_name)

        if blob.exists():
            blob.delete()
