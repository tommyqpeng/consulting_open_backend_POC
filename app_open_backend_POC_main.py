import streamlit as st
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
from faiss_lookup import EncryptedAnswerRetriever
from util_functions import build_prompt, generate_feedback, decrypt_file
from datetime import datetime

# --- Setup ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GSHEET_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(st.secrets["AnswerStorage_Sheet_ID"]).sheet1

APP_PASSWORD = st.secrets["APP_PASSWORD"]
DEEPSEEK_API_KEY = st.secrets["DEEPSEEK_API_KEY"]
DECRYPTION_KEY = st.secrets["DECRYPTION_KEY"].encode()

# --- State & Auth ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "password_attempts" not in st.session_state:
    st.session_state.password_attempts = 0

st.title("Interview Question Survey + Prompt Engineering Playground")

# --- Password ---
if not st.session_state.authenticated:
    if st.session_state.password_attempts >= 3:
        st.error("Too many incorrect attempts.")
        st.stop()
    password = st.text_input("Enter access password", type="password")
    if st.button("Submit Password"):
        if password == APP_PASSWORD:
            st.session_state.authenticated = True
        else:
            st.session_state.password_attempts += 1
            st.warning("Incorrect password.")
    st.stop()

# --- Load prompt and rubric ---
prompt_data = decrypt_file("prompts.json.encrypted", DECRYPTION_KEY)
question = prompt_data["question"]
rubric = prompt_data["rubric"]
system_role = prompt_data["system_role"]
generation_instructions = prompt_data["generation_instructions"]

# --- Load Retriever ---
@st.cache_resource
def load_retriever():
    return EncryptedAnswerRetriever(
        encrypted_index_path="faiss_index.encrypted",
        encrypted_meta_path="metadata.encrypted",
        decryption_key=DECRYPTION_KEY,
        model_name="all-MiniLM-L6-v2"
    )
retriever = load_retriever()

# --- UI Input ---
st.markdown("### Interview Question")
st.markdown(question)
user_input = st.text_area("Write your answer here:", height=200)

# --- Process Answer ---
if st.button("Submit") and user_input.strip():
    with st.spinner("Retrieving examples and building prompt..."):
        examples = retriever.get_nearest_neighbors(user_input, n=3)
        prompt = build_prompt(question, rubric, examples, user_input, generation_instructions)

    # --- Prompt Engineering Playground ---
    st.markdown("### Prompt Engineering Playground")

    with st.expander("View Prompt Sent to GPT"):
        st.code(prompt, language="markdown")

    with st.expander("View System Role"):
        st.code(system_role, language="markdown")

    with st.expander("View Full API Call Components"):
        st.json({
            "question": question,
            "rubric": rubric,
            "examples_used": examples,
            "user_input": user_input,
            "system_role": system_role,
            "final_prompt": prompt,
        })

    # --- Editable prompt & temperature ---
    st.markdown("### Edit Prompt, Role & Temperature")
    custom_role = st.text_area("Custom System Role", system_role, height=100)
    custom_prompt = st.text_area("Custom Prompt", prompt, height=300)
    temperature = st.slider("Model Temperature (0 = deterministic, 1 = creative)", 0.0, 1.0, 0.4, step=0.05)

    if st.button("Submit with Custom Prompt"):
        with st.spinner("Generating feedback..."):
            feedback = generate_feedback(custom_prompt, custom_role, DEEPSEEK_API_KEY, temperature)

        if feedback:
            st.success("Done!")
            st.markdown("### Feedback")
            st.write(feedback)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([
                timestamp,
                user_input.strip(),
                feedback.strip(),
                custom_role.strip(),
                custom_prompt.strip(),
                str(temperature)
            ])
            st.info("Your response has been logged.")
        else:
            st.error("API call failed.")