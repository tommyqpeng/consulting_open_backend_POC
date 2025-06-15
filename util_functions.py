# -*- coding: utf-8 -*-
"""
Created on Sun Jun  1 14:24:21 2025

@author: tommy
"""

import json
import requests
from cryptography.fernet import Fernet

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

def build_prompt(
    question,
    rubric,
    examples,
    user_input,
    generation_instructions,
    order="question,rubric,examples,input,instructions"
):
    """
    Builds the full prompt for the model using a flexible ordering of components.
    Valid keys for 'order' are: question, rubric, examples, input, instructions.
    """

    components = {
        "question": f"Case Question:\n{question}\n",
        "rubric": f"Rubric:\n{rubric}\n",
        "examples": "\n".join(
            f"Past Answer:\n{item['answer']}\nFeedback Given:\n{item['feedback']}\n"
            for item in examples
        ),
        "input": f"Candidate's Answer:\n{user_input}\n",
        "instructions": generation_instructions.strip()
    }

    sections = []
    for key in order.split(","):
        key = key.strip().lower()
        if key in components:
            sections.append(components[key])
        else:
            raise ValueError(f"Invalid prompt section key: '{key}'")

    return "\n\n".join(sections)

def generate_feedback(prompt, system_role, api_key, temperature=0.4):
    """
    Sends the prompt and system role to the DeepSeek API with specified temperature.
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
        "temperature": temperature
    }

    try:
        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return content
    except Exception as e:
        print(f"[DeepSeek API Error] {e}")
        print("Response text:", getattr(response, "text", "No response"))
        return None
