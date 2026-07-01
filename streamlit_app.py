"""
Streamlit frontend (deployed on Streamlit Community Cloud).

Talks ONLY to the FastAPI backend over plain REST calls (requests).
It never imports inngest, never sends Inngest events, and never polls
localhost:8288. Ingestion progress and querying are both handled
entirely server-side by FastAPI.

Backend URL resolution order (first match wins):
  1. st.secrets["BACKEND_API_URL"]   (Streamlit Community Cloud -> app settings -> Secrets)
  2. BACKEND_API_URL environment variable (Docker / VM / local .env)
  3. Hardcoded fallback default below

Note: Render's free tier spins the backend down after inactivity, so the
first request after idle time can take 30-60s to "wake up". Health check
and request timeouts are set generously and the UI communicates this to
the user instead of just failing.
"""

from __future__ import annotations

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BACKEND_URL = "https://docmind-0zkb.onrender.com"


def _resolve_backend_url() -> str:
    try:
        if "BACKEND_API_URL" in st.secrets:
            return str(st.secrets["BACKEND_API_URL"]).rstrip("/")
    except Exception:  # noqa: BLE001 - st.secrets raises if no secrets.toml exists at all
        pass
    return os.getenv("BACKEND_API_URL", DEFAULT_BACKEND_URL).rstrip("/")


BACKEND_API_URL = _resolve_backend_url()

# Render free-tier cold starts can take 30-60s; give generous timeouts.
REQUEST_TIMEOUT_HEALTH_S = 60
REQUEST_TIMEOUT_UPLOAD_S = 180
REQUEST_TIMEOUT_QUERY_S = 90

st.set_page_config(page_title="RAG Ingest & Query", page_icon="📄", layout="centered")


def check_backend_health() -> tuple[bool, str | None]:
    try:
        response = requests.get(f"{BACKEND_API_URL}/health", timeout=REQUEST_TIMEOUT_HEALTH_S)
        if response.status_code == 200:
            return True, None
        return False, f"Backend returned HTTP {response.status_code}"
    except requests.Timeout:
        return False, "Backend took too long to respond (cold start?)."
    except requests.RequestException as exc:
        return False, str(exc)


def upload_pdf(file) -> dict:
    files = {"file": (file.name, file.getvalue(), "application/pdf")}
    response = requests.post(
        f"{BACKEND_API_URL}/upload", files=files, timeout=REQUEST_TIMEOUT_UPLOAD_S
    )
    response.raise_for_status()
    return response.json()


def ask_question(question: str, top_k: int) -> dict:
    response = requests.post(
        f"{BACKEND_API_URL}/query",
        json={"question": question, "top_k": top_k},
        timeout=REQUEST_TIMEOUT_QUERY_S,
    )
    response.raise_for_status()
    return response.json()


def _error_detail(exc: requests.HTTPError) -> str:
    if exc.response is None:
        return str(exc)
    try:
        return exc.response.json().get("detail", str(exc))
    except ValueError:
        return exc.response.text or str(exc)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("📄 RAG Document Assistant")

with st.spinner("Connecting to backend... (first request may take up to a minute if it was idle)"):
    healthy, health_error = check_backend_health()

if not healthy:
    st.error(
        f"Cannot reach backend API at `{BACKEND_API_URL}`.\n\n"
        f"Reason: {health_error}\n\n"
        "If this is a Render free-tier service, it may just be waking up from "
        "sleep — try refreshing in ~30-60 seconds."
    )
    if st.button("Retry connection"):
        st.rerun()
else:
    st.caption(f"✅ Connected to backend: `{BACKEND_API_URL}`")

st.header("Upload a PDF to Ingest")
uploaded = st.file_uploader("Choose a PDF", type=["pdf"], accept_multiple_files=False)

if uploaded is not None and st.button("Upload & Ingest", disabled=not healthy):
    with st.spinner("Uploading to backend and triggering ingestion..."):
        try:
            result = upload_pdf(uploaded)
        except requests.HTTPError as exc:
            st.error(f"Upload failed: {_error_detail(exc)}")
        except requests.Timeout:
            st.error("Upload timed out. If the backend was cold-starting, please try again.")
        except requests.RequestException as exc:
            st.error(f"Could not reach backend: {exc}")
        else:
            st.success(result.get("message", "Upload accepted."))
            st.caption(
                f"source_id: `{result.get('source_id')}` | "
                f"inngest_event_id: `{result.get('inngest_event_id')}`"
            )
            st.caption("Ingestion is running in the background. You can query once it completes.")

st.divider()
st.header("Ask a question about your PDFs")

with st.form("rag_query_form"):
    question = st.text_input("Your question")
    top_k = st.number_input("How many chunks to retrieve", min_value=1, max_value=20, value=5, step=1)
    submitted = st.form_submit_button("Ask", disabled=not healthy)

    if submitted and question.strip():
        with st.spinner("Asking the backend..."):
            try:
                result = ask_question(question.strip(), int(top_k))
            except requests.HTTPError as exc:
                st.error(f"Query failed: {_error_detail(exc)}")
            except requests.Timeout:
                st.error("Query timed out. If the backend was cold-starting, please try again.")
            except requests.RequestException as exc:
                st.error(f"Could not reach backend: {exc}")
            else:
                st.subheader("Answer")
                st.write(result.get("answer") or "(No answer)")

                sources = result.get("sources", [])
                if sources:
                    st.caption("Sources")
                    for source in sources:
                        filename = source.get("filename", "unknown")
                        score = source.get("score", 0.0)
                        text_preview = (source.get("text") or "")[:200]
                        st.write(f"- **{filename}** (score: {score:.3f}) — {text_preview}...")
