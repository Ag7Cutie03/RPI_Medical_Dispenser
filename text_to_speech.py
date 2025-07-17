import os
import re
import subprocess
import tempfile
import openai
import requests
import time

# Global variables for TTS
TTS_AVAILABLE = False

def configure_audio_system():
    """Configure Raspberry Pi audio system"""
    try:
        # Set volume to maximum
        subprocess.run(['amixer', 'set', 'Master', '100%'], check=True)
        print("✓ Volume set to maximum")
        
        # Unmute audio
        subprocess.run(['amixer', 'set', 'Master', 'unmute'], check=True)
        print("✓ Audio unmuted")
        
        # Unmute PCM
        subprocess.run(['amixer', 'set', 'PCM', 'unmute'], check=True)
        print("✓ PCM unmuted")
        
        return True
    except Exception as e:
        print(f"⚠️ Audio configuration warning: {e}")
        return False

def clean_text_for_speech(text):
    """Format text for better speech output by adding pauses for clarity"""
    if not text:
        return text
    
    # Add pauses for better speech rhythm and slower pace
    cleaned_text = text.replace('. ', '. ... ')
    cleaned_text = cleaned_text.replace(', ', ', ... ')
    cleaned_text = cleaned_text.replace(':', ': ... ')
    cleaned_text = cleaned_text.replace(';', '; ... ')
    # Add extra pauses for better clarity
    cleaned_text = cleaned_text.replace('  ', ' ... ')
    return cleaned_text

def check_pico2wave_availability():
    """Check if pico2wave is available on the system"""
    try:
        result = subprocess.run(['which', 'pico2wave'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ pico2wave found on system")
            return True
        else:
            print("❌ pico2wave not found on system")
            return False
    except Exception as e:
        print(f"❌ Error checking pico2wave availability: {e}")
        return False

def initialize_tts():
    """Initialize text-to-speech functionality using pico2wave"""
    global TTS_AVAILABLE
    
    # First configure audio system
    configure_audio_system()
    
    # Check if pico2wave is available
    if check_pico2wave_availability():
        TTS_AVAILABLE = True
        print("✓ Text-to-speech enabled with pico2wave")
        return True
    else:
        print("❌ pico2wave not available. Please install SVOX Pico TTS:")
        print("   sudo apt-get install libttspico-utils")
        TTS_AVAILABLE = False
        return False

def generate_doctor_instructions(medicine_name):
    """Generate clear, simple medicine instructions using OpenAI Chat API and a doctor-style prompt."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return f"No API key found. Please set the OPENAI_API_KEY environment variable."
    import openai
    openai.api_key = api_key
    prompt = (
        "You are a doctor talking to me as a patient. I want clear, simple instructions in layman's terms with the following format:\n"
        "- Take 1 [tablet/capsule] by mouth every [X] hours\n"
        "- Do not take more than [Y] [tablets/capsules] in 24 hours (this prevents any overdose) ([source1], [source2])\n"
        "- If you miss a dose, don’t double up—just take the next dose at the regular time\n"
        "- You can take it with or without food\n\n"
        f"Now give me instructions for **{medicine_name}** with the correct values."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
            temperature=0.2
        )
        answer = response.choices[0].message.content.strip()
        return answer
    except Exception as e:
        return f"Error generating instructions: {e}"

def set_max_volume():
    """Set system volume to maximum and unmute audio jack output."""
    try:
        subprocess.run(['amixer', 'set', 'Master', '100%'], check=True)
        subprocess.run(['amixer', 'set', 'Master', 'unmute'], check=True)
        subprocess.run(['amixer', 'set', 'PCM', 'unmute'], check=True)
        # Force output to audio jack (if on Raspberry Pi)
        subprocess.run(['amixer', 'cset', 'numid=3', '1'], check=True)
    except Exception as e:
        print(f"Warning: Could not set max volume or force audio jack: {e}")

def speak(text):
    """Speak text using OpenAI TTS API if available, otherwise just print it. If text is a medicine name or request for instructions, generate formatted instructions first."""
    set_max_volume()
    time.sleep(5)  # Wait 5 seconds before dictating the instruction
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print(f"🔇 Speech (no API key): {text}")
        return
    # Heuristic: if text is short or looks like a medicine name, generate instructions
    if (text.lower().startswith('instructions for ') and len(text.split()) <= 6) or (len(text.split()) <= 4 and text.isalpha()):
        # Extract medicine name
        if text.lower().startswith('instructions for '):
            medicine_name = text[len('instructions for '):].strip()
        else:
            medicine_name = text.strip()
        text = generate_doctor_instructions(medicine_name)
    try:
        # Call OpenAI TTS API
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": "tts-1",
                "input": text,
                "voice": "alloy"
            },
            stream=True
        )
        if response.status_code != 200:
            print(f"🔇 Speech (API error {response.status_code}): {text}")
            return
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
            for chunk in response.iter_content(chunk_size=4096):
                temp_audio.write(chunk)
            temp_audio_path = temp_audio.name
        # Play audio (try aplay, ffplay, or mpg123)
        played = False
        for player in [["aplay", temp_audio_path], ["ffplay", "-nodisp", "-autoexit", temp_audio_path], ["mpg123", temp_audio_path]]:
            try:
                subprocess.run(player, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                played = True
                break
            except Exception:
                continue
        if not played:
            print(f"🔇 Could not play audio. File at: {temp_audio_path}")
        else:
            os.unlink(temp_audio_path)
    except Exception as e:
        print(f"🔇 Speech error: {e}")
        print(f"Message: {text}")

def test_speech():
    """Test speech functionality"""
    try:
        # Try to enable speech if not already enabled
        if not TTS_AVAILABLE:
            initialize_tts()
        
        # Test with a simple message
        test_message = "Hello, this is a test of the text to speech functionality. Medicine dispenser is working correctly."
        speak(test_message)
        
        # Test with medicine instructions
        medicine_test = "Instructions for Advil: Take every 4 to 6 hours as needed for pain or fever. Do not exceed 1200mg per day without consulting your doctor."
        speak(medicine_test)
        
        return {
            'status': 'success', 
            'message': 'Speech test completed', 
            'tts_available': TTS_AVAILABLE
        }
    except Exception as e:
        return {
            'status': 'error', 
            'message': f'Speech test failed: {str(e)}', 
            'tts_available': TTS_AVAILABLE
        }

def test_audio_system():
    """Test and configure audio system"""
    try:
        # Configure audio
        audio_configured = configure_audio_system()
        
        # Test basic audio
        try:
            subprocess.run(['speaker-test', '-t', 'sine', '-f', '1000', '-l', '1'], timeout=2)
            basic_audio = True
        except:
            basic_audio = False
        
        # Test TTS
        test_message = "Audio system test completed successfully."
        speak(test_message)
        
        return {
            'status': 'success',
            'audio_configured': audio_configured,
            'basic_audio_test': basic_audio,
            'tts_available': TTS_AVAILABLE,
            'message': 'Audio system test completed'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'tts_available': TTS_AVAILABLE
        }

# Initialize TTS when module is imported
try:
    initialize_tts()
except Exception as e:
    print(f"Text-to-speech not available: {e}")
    print("Speech functionality will be disabled")
    TTS_AVAILABLE = False 