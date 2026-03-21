import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)
model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SENSITIVE_KEYWORDS = [
    "password", "social security", "ssn", "credit card", "bank account",
    "otp", "verification code", "confidential", "api_key", "secret_key", 
    "access_token"
]

def is_sensitive(text: str) -> bool:
    """A simplistic heuristic check for sensitive information."""
    if not text:
        return False
    
    text_lower = text.lower()
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in text_lower:
            return True
            
    # Simple check for long numeric sequences that could be credit cards or SSN
    if re.search(r'\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b', text):
        return True
    
    return False

def categorize_email(email: dict) -> str:
    # Combine subject and snippet for analysis
    content = f"Subject: {email.get('subject', '')}\nSnippet: {email.get('snippet', '')}"
    
    # Check for sensitive info BEFORE sending to LLM
    if is_sensitive(content):
        return "Sensitive (Hidden from LLM)"
        
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an email categorization assistant. Categorize the provided email into exactly ONE of the following tags: [Personal, Promotional, Update, Social, Alert]. Reply with ONLY the tag name, and absolutely nothing else."},
                {"role": "user", "content": f"Please categorize this email:\n\n{content}"}
            ],
            temperature=0,
            max_tokens=10
        )
        category = response.choices[0].message.content.strip()
        return category
    except Exception as e:
        print(f"LLM Error: {e}")
        return "Uncategorized"

import json

def categorize_emails_batch(emails: list[dict]) -> list[str]:
    """Categorize multiple emails in a single LLM request."""
    if not emails:
        return []
    
    # Filter out sensitive emails and track indices
    prompts = []
    indices = []
    categories = ["Uncategorized"] * len(emails)
    
    for i, email in enumerate(emails):
        content = f"Subject: {email.get('subject', '')}\nSnippet: {email.get('snippet', '')}"
        if is_sensitive(content):
            categories[i] = "Sensitive (Hidden from LLM)"
        else:
            prompts.append(f"Email {i}: Subject: {email.get('subject', '')}, Snippet: {email.get('snippet', '')}")
            indices.append(i)
            
    if not prompts:
        return categories
        
    combined_prompt = "\n".join(prompts)
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an email categorization assistant. Categorize each email into exactly ONE of the following tags: [Personal, Promotional, Update, Social, Alert]. Reply with a JSON object containing a list named 'categories' with EXACTLY the tag names in the same order as presented, like this: {'categories': ['Personal', 'Promotional', ...]}. Do not include any other text."},
                {"role": "user", "content": f"Please categorize these emails:\n\n{combined_prompt}"}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )
        
        res_text = response.choices[0].message.content.strip()
        res_data = json.loads(res_text)
        
        llm_categories = res_data.get("categories", [])
            
        for i, idx in enumerate(indices):
            if i < len(llm_categories):
                categories[idx] = llm_categories[i]
                
    except Exception as e:
        print(f"Batch LLM Error: {e}")
        
    return categories
