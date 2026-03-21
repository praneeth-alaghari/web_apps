import os
import streamlit as st
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_URL = os.environ.get("API_URL", "http://localhost:8001")

def load_file(relative_path: str) -> str:
    with open(os.path.join(BASE_DIR, relative_path), encoding="utf-8") as f:
        return f.read()

def inject_css():
    css = load_file("static/css/style.css")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

def render_header():
    html = load_file("templates/header.html")
    st.markdown(html, unsafe_allow_html=True)

def render_hero_cards():
    col1, col2 = st.columns(2)
    with col1:
        html = load_file("templates/hero_card.html")
        st.markdown(html, unsafe_allow_html=True)
        fetch_clicked = st.button("🔄  Fetch Emails", use_container_width=True)
    with col2:
        html = load_file("templates/train_card.html")
        st.markdown(html, unsafe_allow_html=True)
        train_clicked = st.button("🧠  Start Training", use_container_width=True)
    return fetch_clicked, train_clicked

def render_count_badge(count: int):
    st.markdown(
        f'<div style="text-align:center">'
        f'<span class="count-badge">{count} emails found</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

def render_email_card(email: dict):
    pref = email.get("preference", "UNCERTAIN")
    pref_class = f"pref-{pref.lower()}"
    conf = int(email.get("confidence", 0) * 100)
    source = email.get("pref_source", "MEM")

    template = load_file("templates/email_card.html")
    html = template.format(
        sender=email["sender"],
        subject=email["subject"],
        date=email["date"],
        snippet=email["snippet"],
        category=email.get("category", "Uncategorized"),
        preference=pref,
        confidence=conf,
        pref_class=pref_class,
        source=source
    )
    st.markdown(html, unsafe_allow_html=True)

def render_divider():
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="InboxAI", page_icon="📬", layout="wide")
    inject_css()
    render_header()

    fetch_clicked, train_clicked = render_hero_cards()

    if train_clicked:
        st.switch_page("pages/Train_Model.py")
        return

    if not fetch_clicked:
        return

    with st.spinner("Fetching emails…"):
        try:
            resp = requests.get(f"{API_URL}/api/emails", timeout=30)
            data = resp.json()
        except Exception as e:
            st.error(f"Failed to fetch emails: {e}")
            return

    if "error" in data:
        st.error(data["error"])
        return

    emails = data.get("emails", [])
    render_count_badge(data.get("count", len(emails)))
    render_divider()

    for email in emails:
        render_email_card(email)

if __name__ == "__main__":
    main()
