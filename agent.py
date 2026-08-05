# DEPRECATED: This is the v1 legacy agent with hardcoded pyautogui/subprocess.
# It is not imported by any production module and is kept for reference only.
# Do not add new functionality here. Use next/app_v5.py for the current agent loop.

import requests
import subprocess
import pyautogui
import time
import pyperclip

MODEL = "google/gemma-4-e4b"
API_URL = "http://127.0.0.1:1234/v1/chat/completions"

SYSTEM = """
Ты локальный Windows-агент.

Отвечай только одной командой в формате:
ACTION: аргумент

Доступные ACTION:
OPEN_APP: calc.exe / notepad.exe / chrome.exe
TYPE_TEXT: текст
SEARCH_WEB: запрос
ANSWER: обычный ответ

Если пользователь просит открыть программу — используй OPEN_APP.
Если просит напечатать текст — используй TYPE_TEXT.
Если просит найти в интернете — используй SEARCH_WEB.
"""

def ask_model(user_text):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.1,
        "max_tokens": 100
    }
    r = requests.post(API_URL, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

def open_app(app):
    apps = {
        "calc.exe": "calc",
        "calculator": "calc",
        "notepad.exe": "notepad",
        "chrome.exe": "chrome",
        "browser": "chrome"
    }

    cmd = apps.get(app.lower(), app)
    subprocess.Popen(["cmd", "/c", "start", "", cmd], shell=True)
    return f"Открыл: {cmd}"

def type_text(text):
    time.sleep(1)
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    return "Текст вставлен."

def search_web(query):
    subprocess.Popen(f'start chrome "https://www.google.com/search?q={query}"', shell=True)
    return f"Ищу: {query}"

def run_action(reply):
    print("MODEL:", reply)

    text = reply.strip()

    if text.startswith("ACTION:"):
        text = text.replace("ACTION:", "", 1).strip()

    if text.startswith("OPEN_APP"):
        app = text.replace("OPEN_APP", "", 1).replace(":", "").strip()
        return open_app(app)

    if text.startswith("TYPE_TEXT"):
        value = text.replace("TYPE_TEXT", "", 1).replace(":", "").strip()
        return type_text(value)

    if text.startswith("SEARCH_WEB"):
        query = text.replace("SEARCH_WEB", "", 1).replace(":", "").strip()
        return search_web(query)

    if text.startswith("ANSWER"):
        return text.replace("ANSWER", "", 1).replace(":", "").strip()

    return text

while True:
    user = input("\nТы: ").strip()
    if user.lower() in ["exit", "выход"]:
        break

    reply = ask_model(user)
    result = run_action(reply)
    print("Агент:", result)