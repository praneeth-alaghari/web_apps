import os
import streamlit as st
import requests

API_URL = os.environ.get("API_URL", "http://localhost:8001")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAINING_DIR = os.path.dirname(os.path.abspath(__file__))


def load_file(relative_path: str, base: str = None) -> str:
    root = base or BASE_DIR
    with open(os.path.join(root, relative_path), encoding="utf-8") as f:
        return f.read()


def inject_css():
    css = load_file("static/css/style.css")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def submit_action(email: dict, action: str):
    try:
        payload = {
            "email_id": email["id"],
            "action": action,
            "sender": email["sender"],
            "subject": email["subject"],
            "snippet": email["snippet"]
        }
        requests.post(f"{API_URL}/api/training/action", json=payload, timeout=60)
    except Exception as e:
        st.error(f"Action failed: {e}")
    st.session_state.train_idx += 1

def fetch_batch():
    with st.spinner("Fetching batch of emails..."):
        try:
            resp = requests.get(f"{API_URL}/api/training/emails", params={"per_page": 50}, timeout=60)
            data = resp.json()
            st.session_state.train_emails = data.get("emails", [])
            st.session_state.train_idx = 0
        except Exception as e:
            st.error(f"Failed to fetch batch: {e}")

def render():
    st.set_page_config(page_title="InboxAI - Train Model", page_icon="🧠", layout="wide")
    inject_css()

    st.markdown(
        "<h1 style='text-align:center; color:#e4e6eb; font-weight:700;'>"
        "🧠 Train InboxAI</h1>"
        "<p style='text-align:center; color:#6b7280; margin-top:-8px;'>"
        "Label your emails to teach the system your preferences</p>",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    if "train_emails" not in st.session_state:
        st.session_state.train_emails = []
    if "train_idx" not in st.session_state:
        st.session_state.train_idx = 0

    if len(st.session_state.train_emails) == 0:
        fetch_batch()

    emails = st.session_state.train_emails
    idx = st.session_state.train_idx

    if not emails:
        st.info("No more emails found.")
        if st.button("Refresh", use_container_width=True):
            fetch_batch()
            st.rerun()
        return

    st.markdown(
        f'<div style="text-align:center; margin-bottom: 20px;">'
        f'<span class="count-badge">Email {min(idx + 1, len(emails))} / {len(emails)}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if idx >= len(emails):
        st.success("Batch complete! Great job.")
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            if st.button("Load Next Batch ➡️", use_container_width=True):
                fetch_batch()
                st.rerun()
        return

    email = emails[idx]
    
    # Pre-render logic for privacy filter
    from services.categorizer import is_sensitive
    is_sens = is_sensitive(email.get("subject", "") + " " + email.get("snippet", ""))

    template = load_file("templates/email_card.html", base=TRAINING_DIR)
    
    subject_display = email["subject"]
    snippet_display = email["snippet"]
    if is_sens:
        subject_display = "🔒 Sensitive (Hidden from LLM)"
        snippet_display = "Content blocked to protect privacy."

    html = template.format(
        sender=email["sender"],
        subject=subject_display,
        date=email["date"],
        snippet=snippet_display,
    )
    st.markdown(html, unsafe_allow_html=True)

    if is_sens:
        st.warning("This email contains sensitive information and is prevented from being embedded or sent to LLMs. Proceeding will ignore it.")

    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col2:
        if st.button("✅ Keep", key=f"keep_{email['id']}", use_container_width=True, disabled=is_sens):
            submit_action(email, "KEEP")
            st.rerun()
    with col3:
        if st.button("🗑️ Delete", key=f"del_{email['id']}", use_container_width=True, disabled=is_sens):
            submit_action(email, "DELETE")
            st.rerun()
    with col4:
        if st.button("⏭️ Ignore", key=f"ign_{email['id']}", use_container_width=True):
            submit_action(email, "IGNORE")
            st.rerun()

if __name__ == "__main__":
    render()
