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


def fetch_emails():
    service = get_gmail_service()
    results = service.users().messages().list(
        userId="me", q="newer_than:7d"
    ).execute()
    messages = results.get("messages", [])

    if not messages:
        return {"count": 0, "emails": []}

    emails = []

    def callback(request_id, response, exception):
        if exception:
            print(f"Batch fetch error for {request_id}: {exception}")
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

    # Chunking batch requests to prevent rate limit (429: Too many concurrent requests)
    chunk_size = 10
    for i in range(0, min(len(messages), 50), chunk_size):
        batch = service.new_batch_http_request(callback=callback)
        for msg in messages[i:i + chunk_size]:
            batch.add(service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ))
        batch.execute()

    return {"count": len(emails), "emails": emails}


def trash_email(email_id: str):
    """Trashes an email by ID using the Gmail API."""
    try:
        service = get_gmail_service()
        service.users().messages().trash(userId="me", id=email_id).execute()
        return True
    except Exception as e:
        print(f"Error trashing email {email_id}: {e}")
        return False
