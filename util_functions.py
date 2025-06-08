# -*- coding: utf-8 -*-
"""
Created on Sun Jun  1 14:24:21 2025

@author: tommy
"""

import json
import re
import requests
from cryptography.fernet import Fernet
from datetime import datetime

def decrypt_file(encrypted_path, decryption_key):
    """
    Decrypts an encrypted JSON file using Fernet.
    Returns the parsed JSON as a dictionary.
    """
    with open(encrypted_path, "rb") as f:
        encrypted = f.read()
    fernet = Fernet(decryption_key)
    decrypted = fernet.decrypt(encrypted)
    return json.loads(decrypted)

def build_prompt(question, rubric, examples, user_input, generation_instructions):
    """
    Builds the full prompt for the model including instructions, question, examples, and candidate input.
    """
    retrieved_text = "\n".join(
        f"Past Answer: {item['answer']}\nFeedback Given: {item['feedback']}\n"
        for item in examples
    )

    return f"""
Case Question:
{question}

Candidate's Answer:
{user_input}

Historical Examples:
{retrieved_text}

Rubric:
{rubric}

{generation_instructions}
"""

def generate_feedback(prompt, system_role, api_key):
    """
    Sends the prompt and system role to the DeepSeek API and returns the feedback and average score.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_role},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4
    }

    response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)

    if response.status_code != 200:
        return None, response

    content = response.json()["choices"][0]["message"]["content"]

    return content
