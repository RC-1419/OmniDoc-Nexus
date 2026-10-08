"""Omnidoc Nexus - Streamlit chatbot. A plain client of the API: start the API first, then
    streamlit run omnidoc/ui/app.py
Set OMNIDOC_API_URL if the API is not at http://127.0.0.1:8000."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # so `omnidoc` imports work when launched by Streamlit

import streamlit as st  # noqa: E402

from omnidoc.ui.api_client import ApiClient, ApiError, Unauthorized  # noqa: E402

API_URL = os.environ.get("OMNIDOC_API_URL", "http://127.0.0.1:8000")
FIELD_NAMES = ["aadhaar_number", "pan_number", "passport_number"]

st.set_page_config(page_title="Omnidoc Nexus", page_icon="🔐", layout="wide")


def logout(notice: str = "") -> None:
    st.session_state.clear()
    if notice:
        st.session_state["notice"] = notice


def attempt(fn, *args, **kwargs):
    """Run an API call. Shows a friendly error and returns None on failure; an expired login ends the session."""
    try:
        return fn(*args, **kwargs)
    except Unauthorized:
        logout("Your session has expired. Please sign in again.")
        st.rerun()
    except ApiError as e:
        wait = f" (try again in {e.retry_after} s)" if e.retry_after else ""
        st.error(f"{e.detail}{wait}")
        return None


def show_file(file: dict, key: str) -> None:
    if file["mime"].startswith("image/"):
        st.image(file["data"], caption=file["name"])
    st.download_button(f"⬇ Download {file['name']}", file["data"], file_name=file["name"], mime=file["mime"], key=key)


# ---------------------------------------------------------------- sign in / sign up
def login_page(api: ApiClient) -> None:
    st.title("🔐 Omnidoc Nexus")
    st.caption("Your private vault for personal and family documents.")
    if notice := st.session_state.pop("notice", ""):
        st.warning(notice)
    sign_in, sign_up = st.tabs(["Sign in", "Create account"])
    with sign_in:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", type="primary"):
                token = attempt(api.login, username, password)
                if token:
                    st.session_state["token"] = token
                    st.rerun()
    with sign_up:
        with st.form("signup"):
            username = st.text_input("Choose a username", help="3-32 letters, numbers, . _ -")
            email = st.text_input("Email (optional)", help="Lets you say 'email it to me'.")
            password = st.text_input("Choose a password", type="password", help="At least 8 characters")
            again = st.text_input("Repeat password", type="password")
            if st.form_submit_button("Create account", type="primary"):
                if password != again:
                    st.error("The two passwords don't match.")
                elif attempt(api.signup, username, password, email.strip() or None):
                    token = attempt(api.login, username, password)
                    if token:
                        st.session_state["token"] = token
                        st.rerun()


# ---------------------------------------------------------------- documents view
def documents_page(api: ApiClient) -> None:
    st.header("My documents")
    people = attempt(api.people) or []
    docs = attempt(api.documents) or []

    with st.expander("➕ Upload a document", expanded=not docs):
        with st.form("upload", clear_on_submit=True):
            file = st.file_uploader("PDF or photo", type=["pdf", "png", "jpg", "jpeg"])
            person = st.selectbox("Whose document is it?", people, format_func=lambda p: f"{p['name']} ({p['relation']})") \
                if people else None
            doc_type = st.text_input("Document type (optional)", placeholder="Leave empty to detect it automatically",
                                     help="For example: aadhaar, pan, passport")
            if st.form_submit_button("Upload", type="primary"):
                if file is None:
                    st.error("Choose a file first.")
                else:
                    with st.spinner("Reading the document…"):
                        result = attempt(api.upload, file.name, file.getvalue(), file.type or "application/octet-stream",
                                         person["id"] if person else None, doc_type.strip() or None)
                    if result:
                        st.success(f"Saved as: {result['doc_type']}"
                                   + (f" (replaced {result['replaced']} older one)" if result["replaced"] else ""))
                        if result["fields_found"]:
                            st.write("Numbers found: " + ", ".join(result["fields_found"]))
                        for w in result["warnings"]:
                            st.warning(w)
                        docs = attempt(api.documents) or docs

    with st.expander("👪 Family members"):
        for p in people:
            st.write(f"• {p['name']} ({p['relation']})")
        with st.form("add_person", clear_on_submit=True):
            name = st.text_input("Name")
            relation = st.text_input("Relation", value="family", help="mother, father, spouse, child…")
            if st.form_submit_button("Add person") and name.strip():
                if attempt(api.add_person, name.strip(), relation.strip() or "family"):
                    st.rerun()

    if not docs:
        st.info("Nothing here yet. Upload your first document above.")
        return
    for d in docs:
        label = f"{d['doc_type'].upper()} · {d['person_name']} · {d['filename']}"
        with st.expander(label):
            st.caption(f"Added {d['created_at'][:10]}. Numbers held: {', '.join(d['fields']) or 'none'}")
            open_key = f"open_{d['id']}"
            if st.toggle("Show / download", key=open_key):
                data = attempt(api.file, d["id"])
                if data:
                    show_file({"name": d["filename"], "mime": d["mime"], "data": data}, f"dl_{d['id']}")
            with st.form(f"field_{d['id']}"):
                st.write("Type in a number the scanner missed")
                name = st.selectbox("Which number", FIELD_NAMES, key=f"fname_{d['id']}")
                value = st.text_input("Value", key=f"fval_{d['id']}")
                if st.form_submit_button("Save number") and value.strip():
                    if attempt(api.set_field, d["id"], name, value.strip()):
                        st.success("Saved.")
            if st.session_state.get("confirm_delete") == d["id"]:
                st.warning("Delete this document permanently?")
                yes, no = st.columns(2)
                if yes.button("Yes, delete", key=f"yes_{d['id']}", type="primary"):
                    if attempt(api.delete_document, d["id"]):
                        st.session_state.pop("confirm_delete")
                        st.rerun()
                if no.button("Keep it", key=f"no_{d['id']}"):
                    st.session_state.pop("confirm_delete")
                    st.rerun()
            elif st.button("🗑 Delete", key=f"del_{d['id']}"):
                st.session_state["confirm_delete"] = d["id"]
                st.rerun()


# ---------------------------------------------------------------- chat view
def chat_page(api: ApiClient, provider: str | None) -> None:
    st.header("Ask about your documents")
    messages = st.session_state.setdefault("messages", [])
    if not messages:
        st.info("Try: “What is my PAN number?”, “Show my Aadhaar card”, or “Email my passport to me”.")

    prompt = st.chat_input("Ask something…")
    if prompt:
        history = [{"role": m["role"], "content": m["content"][:4000]} for m in messages][-20:]
        messages.append({"role": "user", "content": prompt})
        st.session_state.pop("pending_email", None)
        with st.spinner("Thinking…"):
            reply = attempt(api.chat, prompt, history, provider)
        if reply is None:
            messages.pop()
        else:
            entry = {"role": "assistant", "content": reply["text"]}
            if reply["show_document"]:
                shown = reply["show_document"]
                data = attempt(api.file, shown["document_id"])
                if data:
                    entry["file"] = {"name": shown["filename"], "mime": shown["mime"], "data": data}
            messages.append(entry)
            if reply["email_action"]:
                st.session_state["pending_email"] = reply["email_action"]

    for i, m in enumerate(messages):
        with st.chat_message(m["role"]):
            st.write(m["content"])
            if m.get("file"):
                show_file(m["file"], f"msgfile_{i}")

    action = st.session_state.get("pending_email")
    if action:
        with st.container(border=True):
            st.write(f"**Send this email?**  \n{action['description']}  \nTo: `{action['to']}`")
            send, cancel = st.columns(2)
            if send.button("✅ Send", type="primary"):
                result = attempt(api.confirm_email, action["token"], None)
                if result:
                    messages.append({"role": "assistant", "content": f"Email sent to {action['to']}."})
                    st.session_state.pop("pending_email")
                    st.rerun()
            if cancel.button("Cancel"):
                messages.append({"role": "assistant", "content": "Okay, I didn't send anything."})
                st.session_state.pop("pending_email")
                st.rerun()


# ---------------------------------------------------------------- main
def main() -> None:
    api = ApiClient(API_URL, st.session_state.get("token"))
    if not api.token:
        login_page(api)
        return
    user = attempt(api.me)
    if user is None:
        return
    if "providers" not in st.session_state:
        st.session_state["providers"] = attempt(api.providers) or {"llm": [], "default_llm": None}
    providers = st.session_state["providers"]

    with st.sidebar:
        st.markdown(f"### 🔐 Omnidoc Nexus\nSigned in as **{user['username']}**")
        view = st.radio("Go to", ["💬 Chat", "📁 Documents"], label_visibility="collapsed")
        names = [p["name"] for p in providers["llm"]]
        provider = None
        if names:
            default = names.index(providers["default_llm"]) if providers["default_llm"] in names else 0
            provider = st.selectbox("AI model", names, index=default,
                                    format_func=lambda n: next(p["label"] for p in providers["llm"] if p["name"] == n))
        if st.button("Clear chat"):
            st.session_state["messages"] = []
            st.session_state.pop("pending_email", None)
            st.rerun()
        if st.button("Sign out"):
            logout()
            st.rerun()
        st.caption("Chat messages are kept only in this browser tab and disappear when you sign out or close it.")

    if view.endswith("Chat"):
        chat_page(api, provider)
    else:
        documents_page(api)


try:
    main()
except ApiError as e:  # e.g. the API isn't running
    st.error(e.detail)
    st.code("uvicorn omnidoc.api.main:app --reload")
