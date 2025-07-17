import pyttsx3
import time
import subprocess

def set_max_volume():
    """Set system volume to maximum and unmute audio jack output."""
    try:
        subprocess.run(['amixer', 'set', 'Master', '100%'], check=True)
        subprocess.run(['amixer', 'set', 'Master', 'unmute'], check=True)
        # Force output to audio jack (if on Raspberry Pi)
        subprocess.run(['amixer', 'cset', 'numid=3', '1'], check=True)
    except Exception as e:
        print(f"Warning: Could not set max volume or force audio jack: {e}")

def speak(text):
    set_max_volume()
    time.sleep(5)  # Wait 5 seconds before dictating the instruction
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 1.0)
    engine.say(text)
    engine.runAndWait() 