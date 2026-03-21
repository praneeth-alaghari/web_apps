import os
import json
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def main():
    load_dotenv()
    
    # Use the token string from the .env file that was saved earlier
    token_str = os.environ.get('DEFAULT_GMAIL_TOKEN')
    
    if not token_str:
        print("No DEFAULT_GMAIL_TOKEN found in .env")
        return
        
    # The token from dotenv may have surrounding quotes, let's strip them
    token_str = token_str.strip("'\"")
        
    token_data = json.loads(token_str)
    
    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes')
    )
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        
        print("Fetching emails from the last 24 hours...")
        # newer_than:1d queries emails from the last 24 hours
        results = service.users().messages().list(userId='me', q='newer_than:1d').execute()
        messages = results.get('messages', [])
        
        if not messages:
            print('No messages found in the last 24 hours.')
        else:
            print(f"Found {len(messages)} messages.")
            for msg in messages:
                message = service.users().messages().get(
                    userId='me', 
                    id=msg['id'], 
                    format='metadata', 
                    metadataHeaders=['Subject', 'From']
                ).execute()
                
                headers = message['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                
                print(f"- {subject} (From: {sender})")
                
    except Exception as error:
        print(f"An error occurred: {error}")

if __name__ == '__main__':
    main()
