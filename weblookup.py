import requests
import re
from gtts import gTTS
import os

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

def get_directions_and_speak(brand_name):
    directions = fetch_fda_instruction(brand_name)
    cleaned = clean_directions(directions)
    try:
        tts = gTTS(text=cleaned, lang='en', slow=False)
        tts.save("speak.mp3")
        os.system("mpg123 speak.mp3")
        os.remove("speak.mp3")
    except Exception as e:
        cleaned += f"\n(TTS error: {e})"
    return cleaned
