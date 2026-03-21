import os
import json
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv()


def get_gmail_service():
    token_str = os.environ.get("DEFAULT_GMAIL_TOKEN", "")
    token_str = token_str.strip("'\"")
    token_data = json.loads(token_str)
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )
    return build("gmail", "v1", credentials=creds)


import random

def fetch_training_emails(page_token: str = None, per_page: int = 50):
    """Fetch recent emails (newer_than:30d) and shuffle them for training."""
    service = get_gmail_service()

    # Gmail allows querying text directly
    kwargs = {
        "userId": "me",
        "q": "newer_than:30d",
        "maxResults": per_page
    }
    if page_token:
        kwargs["pageToken"] = page_token

    results = service.users().messages().list(**kwargs).execute()
    messages = results.get("messages", [])
    next_page_token = results.get("nextPageToken", None)

    emails = []

    def callback(request_id, response, exception):
        if exception:
            print(f"Batch training fetch error for {request_id}: {exception}")
            return
        
        headers = response.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "")
        snippet = response.get("snippet", "")

        emails.append({
            "id": response["id"],
            "subject": subject,
            "sender": sender,
            "date": date,
            "snippet": snippet,
        })

    batch = service.new_batch_http_request(callback=callback)
    for msg in messages:
        batch.add(service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ))
    batch.execute()

    # Shuffle them to mix the batch
    random.shuffle(emails)

    return {
        "count": len(emails),
        "emails": emails,
        "next_page_token": next_page_token,
    }
