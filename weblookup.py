import requests
import re
from gtts import gTTS
import os
import time

def fetch_fda_instruction(brand_name):
    url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{brand_name}&limit=1"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            try:
                directions = data['results'][0].get('dosage_and_administration', ["No directions found"])[0]
                return directions
            except (KeyError, IndexError):
                return "No instruction available"
        else:
            return "API error or medicine not found"
    except Exception as e:
        return f"Error fetching instructions: {e}"

def clean_directions(text):
    # Remove repeated 'Directions' or similar at the start
    cleaned = re.sub(r'^(Directions\s*)+', '', text, flags=re.IGNORECASE).strip()
    return cleaned

def get_directions_and_speak(brand_name, tray_number=None):
    directions = fetch_fda_instruction(brand_name)
    cleaned = clean_directions(directions)
    try:
        # Speak directions
        tts = gTTS(text=cleaned, lang='en', slow=False)
        tts.save("speak.mp3")
        os.system("mpg123 speak.mp3")
        os.remove("speak.mp3")
        time.sleep(3)  # <-- Add this line
        # Speak tray/medicine message 3 times with 10s delay
        if tray_number is not None:
            message = f"Tray {tray_number}: {brand_name} was dispensed. Please take your medicine now."
            for _ in range(3):
                tts = gTTS(text=message, lang='en', slow=False)
                tts.save("speak.mp3")
                os.system("mpg123 speak.mp3")
                os.remove("speak.mp3")
                time.sleep(10)
    except Exception as e:
        cleaned += f"\n(TTS error: {e})"
    return cleaned
