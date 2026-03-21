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

@app.get("/api/emails")
def get_emails():
    try:
        data = fetch_emails()
        
        # Add category and preference to each email
        for email in data.get("emails", []):
            # 1. Check Qdrant for learned preference
            pref_data = get_preference_decision(email["subject"], email["snippet"])
            email["preference"] = pref_data["action"]
            email["confidence"] = pref_data["confidence"]
            email["pref_source"] = pref_data["source"]

            # 2. Get LLM category
            email["category"] = categorize_email(email)
            
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

@app.post("/api/training/action")
def submit_training_action(payload: TrainingAction):
    try:
        action = payload.action.upper()

        if action in ["KEEP", "DELETE"]:
            # Store in Qdrant
            store_training_action(
                email_id=payload.email_id,
                action=action,
                sender=payload.sender,
                subject=payload.subject,
                snippet=payload.snippet
            )

        if action == "DELETE":
            # Physically delete (trash) from Gmail
            trash_email(payload.email_id)

        return {"status": "success", "action": action, "email_id": payload.email_id}
    except Exception as e:
        return {"error": str(e)}
