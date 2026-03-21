# 📬 InboxAI: Intelligent Email Assistant

## 📖 Overview
**InboxAI** is an intelligent, self-learning email housekeeper. It connects natively to your Gmail account to fetch your most recent emails and uses Large Language Models (LLMs) and Vector Embeddings to automatically categorize, evaluate, and assist in managing your inbox. 

Through its **Interactive Training Module**, InboxAI learns your reading behaviors. Every time you review an email and manually tell the app to "Keep" or "Delete" it, the system stores the semantic meaning of that action in a Vector Database. The next time a similar email arrives, the AI applies its memories to suggest whether you should keep or delete it, along with a confidence metric. Will automatically manage inbox in future based on a threshold confidence metric

Crucially, **Privacy is built-in by design**. InboxAI utilizes local regex-based sanitization algorithms to prevent highly sensitive emails (e.g., passwords, OTPs, financial data) from ever leaving your machine—meaning they are never embedded or passed to OpenAI.

In future once gained confidence on model's decisions, this feature can be scheduled to run periodically to keep the inbox clean automatically.

---

## 🛠️ Tech Stack
This application leverages a modern, robust, and highly-scalable tech stack.

* **Frontend:** [Streamlit](https://streamlit.io/) — providing a reactive, intuitive UI for the dashboard and training pipeline.
* **Backend API:** [FastAPI](https://fastapi.tiangolo.com/) — serving fast, concurrent API endpoints for email fetching and AI categorization. 
* **AI & Embeddings:** [OpenAI API](https://openai.com/) — utilizing `gpt-4o-mini` for lightning-fast categorization and `text-embedding-3-small` for generating vector embeddings.
* **Vector Database:** [Qdrant](https://qdrant.tech/) — acting as the semantic memory engine storing your past decisions to evaluate incoming emails via cosine similarity.
* **Integrations:** [Gmail REST API](https://developers.google.com/gmail/api) — accessing raw inbox data natively.
* **Deployment:** [Docker](https://www.docker.com/) & [Render](https://render.com/) — fully containerized and configured for one-click cloud deployment via `render.yaml`.

---

## ✨ Key Features
* **Automated Dashboard fetching:** Pulls your last 7 days of emails and evaluates them using AI in real-time.
* **One-Click Training Mode:** Seamlessly sift through new emails and establish an AI baseline by reviewing an endless queue of un-taught emails.
* **Smart Rate-Limiting:** Operates using an optimized "chunked batching" algorithm to efficiently query Gmail metadata without triggering Google's API Concurrency Limits (`HTTP 429`).
* **Background Processing:** Deletions and Vector processing run asynchronously in FastAPI to keep the UI snappy and block-free.
* **Zero-Downtime Cloud Ready:** Fully architected to run immediately natively on your machine via Docker-Compose, or securely on the web via Render.

---

## 🏗️ Architecture & Flow

1. **The Fetch:** Streamlit (Client) asks FastAPI (Server) for the latest emails. FastAPI hits the Gmail API via chunked batches.
2. **The Filter:** Incoming emails undergo a local check via `is_sensitive()`. If flagged, the email is visually locked and exempt from LLM processing.
3. **The Brain:** 
   * Emails are passed to `gpt-4o-mini` simultaneously via batched concurrent requests for structured categorization (e.g., "Newsletter", "Work", "Alert").
   * Simultaneously, emails are passed through `text-embedding-3-small` to generate vectors.
   * Those vectors are compared against your historical `KEEP` or `DELETE` memory logs stored in **Qdrant** using *k*-Nearest Neighbors (k-NN) similarity mapping.
4. **The Verdict:** The frontend merges both the LLM categorization and the Qdrant confidence score, displaying beautiful interactive cards in the UI recommending an action.

---

## 🚀 Quick Start / Local Setup

### 1. Prerequisites
You will need your standard API keys:
- Google Cloud Platform (GCP) OAuth Client ID & Secret
- OpenAI API Key
- A Local or Cloud [Qdrant Instance](https://cloud.qdrant.io/)

### 2. Environment Variables
Create a `.env` file in the root of the project with your configurations:
```env
GOOGLE_CLIENT_ID='YOUR_GOOGLE_ID'
GOOGLE_CLIENT_SECRET='YOUR_GOOGLE_SECRET'
DEFAULT_GMAIL_TOKEN='{"token": "..."}' # Full OAuth JSON generated locally
OPENAI_API_KEY='sk-...'
OPENAI_MODEL='gpt-4o-mini'

# Qdrant Config (Option A: Cloud)
QDRANT_URL='https://YOUR_CLUSTER.cloud.qdrant.io'
QDRANT_API_KEY='YOUR_QDRANT_API_KEY'

# Qdrant Config (Option B: Local)
QDRANT_HOST='localhost'
QDRANT_PORT='6333'
```

### 3. Running Locally (Docker)
The easiest way to spin up the application is via the included docker-compose file!

```bash
docker-compose up --build
```
This builds your FastAPI backend, loads the Streamlit UI, and natively mounts a local Qdrant Vector database all at once!

- **Dashboard:** [http://localhost:10000](http://localhost:10000)
- **FastAPI Core:** [http://localhost:8001](http://localhost:8001)

### 4. Running the Raw Scripts 
If you prefer running without Docker:
```bash
pip install -r requirements.txt
./start.sh
```

---

## ☁️ Cloud Deployment
InboxAI is structured specifically for **Render**. You can deploy it seamlessly natively without Docker, maintaining full security around your variables.

1. Connect your Github repository to the Render Dashboard.
2. Use the provided `render.yaml` Blueprint or create a standard Web Service pointed to `bash start.sh`.
3. Populate all variables (including the `QDRANT_API_KEY` and `DEFAULT_GMAIL_TOKEN`) into Render’s secure environment vault. 
4. The system will boot seamlessly into production.

---
*Created carefully as a demonstration of production-ready AI software architecture. Fully adaptable and intelligent.*
