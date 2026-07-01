from gcs_storage import GCSStorage

storage = GCSStorage()

url = storage.upload_pdf("GEN AI.pdf")

print(url)