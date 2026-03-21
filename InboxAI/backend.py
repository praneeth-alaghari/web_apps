from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from services.gmail import fetch_emails
from services.categorizer import categorize_email
from training.service import fetch_training_emails

app = FastAPI(title="InboxAI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from services.db import get_preference_decision

from services.categorizer import categorize_emails_batch
from services.db import get_preference_decisions_batch

@app.get("/api/emails")
def get_emails():
    try:
        data = fetch_emails()
        emails = data.get("emails", [])
        if not emails:
            return data
            
        # 1. Batch get learned preferences from Qdrant/OpenAI
        decisions = get_preference_decisions_batch(emails)
        
        # 2. Batch get LLM categories from OpenAI
        categories = categorize_emails_batch(emails)
        
        # 3. Zip results back into email objects
        for i, email in enumerate(emails):
            pref_data = decisions[i]
            email["preference"] = pref_data["action"]
            email["confidence"] = pref_data["confidence"]
            email["pref_source"] = pref_data["source"]
            email["category"] = categories[i]
            
        return data
    except Exception as e:
        return {"error": str(e)}

from pydantic import BaseModel
from typing import Optional
from services.gmail import trash_email
from services.db import store_training_action

class TrainingAction(BaseModel):
    email_id: str
    action: str  # "KEEP", "DELETE", "IGNORE"
    sender: str
    subject: str
    snippet: str

@app.get("/api/training/emails")
def get_training_emails(
    page_token: str = Query(None),
    per_page: int = Query(50, ge=1, le=100),
):
    try:
        return fetch_training_emails(page_token=page_token, per_page=per_page)
    except Exception as e:
        return {"error": str(e)}

from fastapi import BackgroundTasks

@app.post("/api/training/action")
def submit_training_action(payload: TrainingAction, background_tasks: BackgroundTasks):
    try:
        action = payload.action.upper()

        if action in ["KEEP", "DELETE"]:
            # Process AI training in the background
            background_tasks.add_task(
                store_training_action,
                email_id=payload.email_id,
                action=action,
                sender=payload.sender,
                subject=payload.subject,
                snippet=payload.snippet
            )

        if action == "DELETE":
            # Process deletion in the background
            background_tasks.add_task(trash_email, payload.email_id)

        return {"status": "processing", "action": action, "email_id": payload.email_id}
    except Exception as e:
        return {"error": str(e)}
