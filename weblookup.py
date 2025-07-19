import requests
from bs4 import BeautifulSoup
from bs4.element import Tag
import time
from text_to_speech import speak_text


def get_directions_from_drugs_com(medicine_name, max_retries=3, retry_delay=2):
    """
    Fetch the 'Directions' section from drugs.com for the given brand name.
    Args:
        medicine_name (str): The brand name of the medicine (e.g., 'paracetamol').
        max_retries (int): Number of times to retry on network error.
        retry_delay (int): Seconds to wait between retries.
    Returns:
        str: The content of the Directions section, or an error message.
    """
    url_brand = medicine_name.strip().replace(' ', '-').lower()
    url = f"https://www.drugs.com/dosage/{url_brand}.html"
    attempt = 0
    while attempt < max_retries:
        try:
            response = requests.get(url, timeout=60)  # Increased timeout to 60 seconds (1 minute)
            response.raise_for_status()
            # Try lxml parser for speed and robustness, fallback to html.parser
            try:
                soup = BeautifulSoup(response.text, 'lxml')
            except Exception:
                soup = BeautifulSoup(response.text, 'html.parser')
            # Find the 'Directions' section header (h2 or h3)
            directions_header = soup.find(lambda tag: tag.name in ['h2', 'h3'] and 'directions' in tag.text.lower())
            if not directions_header:
                return "Directions section not found."
            # Collect all content until the next header of the same or higher level
            content = []
            for sibling in directions_header.find_next_siblings():
                if isinstance(sibling, Tag) and sibling.name and sibling.name.startswith('h'):
                    break
                content.append(sibling.get_text(strip=True))
            return '\n'.join(content).strip() or "Directions content not found."
        except requests.exceptions.RequestException as e:
            attempt += 1
            if attempt >= max_retries:
                return f"Network error fetching directions: {e}"
            time.sleep(retry_delay)
        except Exception as e:
            return f"Error fetching directions: {e}"


def get_directions_and_speak(medicine_name, max_retries=3, retry_delay=2):
    """
    Fetch directions for a medicine and speak them aloud using piper-tts.
    Args:
        medicine_name (str): The brand name of the medicine.
        max_retries (int): Number of times to retry on network error.
        retry_delay (int): Seconds to wait between retries.
    Returns:
        str: The directions text that was spoken.
    """
    directions = get_directions_from_drugs_com(medicine_name, max_retries, retry_delay)
    print(f"Directions for {medicine_name}:")
    print(directions)
    print("\nSpeaking directions...")
    speak_text(directions)
    return directions


if __name__ == "__main__":
    # Test run for 'neozep' - fetch directions and speak them
    result = get_directions_and_speak("neozep")
