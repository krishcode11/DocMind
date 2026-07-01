from google import genai
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter
from dotenv import load_dotenv
import os
import requests

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
EMBED_MODEL = "models/gemini-embedding-2"
EMBED_DIM = 3072

splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=200)

def load_and_chunk_pdf(path_or_url: str):
    temp_file = None

    try:
        # If URL, download it first
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):

            response = requests.get(path_or_url)
            response.raise_for_status()

            temp = tempfile.NamedTemporaryFile(
                suffix=".pdf",
                delete=False
            )

            temp.write(response.content)
            temp.close()

            temp_file = temp.name

            pdf_path = temp_file

        else:
            pdf_path = path_or_url

        docs = PDFReader().load_data(file=pdf_path)

        texts = [
            d.text
            for d in docs
            if getattr(d, "text", None)
        ]

        chunks = []

        for t in texts:
            chunks.extend(
                splitter.split_text(t)
            )

        return chunks

    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)

def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = []
    for text in texts:
        result = client.models.embed_content(
            model=EMBED_MODEL,
            contents=text
        )
        embeddings.append(result.embeddings[0].values)
    return embeddings
