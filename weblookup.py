import requests
import pyttsx3

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

def get_directions_and_speak(brand_name):
    directions = fetch_fda_instruction(brand_name)
    try:
        engine = pyttsx3.init()
        engine.say(directions)
        engine.runAndWait()
    except Exception as e:
        directions += f"\n(TTS error: {e})"
    return directions
