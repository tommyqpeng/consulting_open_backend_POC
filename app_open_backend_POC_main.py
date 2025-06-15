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
rubric_default = prompt_data["rubric"]
system_role_default = prompt_data["system_role"]
generation_instructions_default = prompt_data["generation_instructions"]

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

# --- Custom Prompt Parameters ---
st.markdown("## Prompt Components")
col1, col2 = st.columns(2)
with col1:
    custom_role = st.text_area("System Role", system_role_default, height=100)
    custom_rubric = st.text_area("Rubric", rubric_default, height=150)
with col2:
    generation_instructions = st.text_area("Generation Instructions", generation_instructions_default, height=150)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.4, step=0.05)

# --- Visual Prompt Order Editor ---
st.markdown("## Prompt Component Ordering")
prompt_parts = ["question", "rubric", "examples", "input", "instructions"]
selected_order = []
remaining_parts = prompt_parts.copy()

for i in range(len(prompt_parts)):
    choice = st.selectbox(
        f"Position {i + 1}",
        options=[""] + remaining_parts,
        key=f"prompt_order_{i}"
    )
    if choice:
        selected_order.append(choice)
        remaining_parts.remove(choice)

prompt_order = ",".join(selected_order)

# --- Base prompt generation ---
if st.button("Submit"):
    with st.spinner("Retrieving examples and building prompt..."):
        examples = retriever.get_nearest_neighbors(user_input, n=3)
        st.session_state.examples = examples
        prompt = build_prompt(question, custom_rubric, examples, user_input, generation_instructions, order=prompt_order)
        st.session_state.prompt = prompt

# --- If prompt built, show result and submit for feedback ---
if "prompt" in st.session_state:
    prompt = st.session_state.prompt
    examples = st.session_state.examples

    st.markdown("### Retrieved Historical Examples")
    for i, ex in enumerate(examples):
        with st.expander(f"Example {i + 1}"):
            st.markdown(f"**Past Answer:**\n{ex['answer']}")
            st.markdown(f"**Feedback Given:**\n{ex['feedback']}")

    st.markdown("### Final Prompt Preview")
    st.code(prompt, language="markdown")

    if st.button("Submit to DeepSeek"):
        with st.spinner("Generating feedback..."):
            feedback = generate_feedback(prompt, custom_role, DEEPSEEK_API_KEY, temperature)

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
                prompt.strip(),
                str(temperature)
            ])
            st.info("Logged to sheet.")
        else:
            st.error("No feedback returned. Check API or prompt.")
