import subprocess
import os

def speak_text(text):
    """
    Convert the given text to speech using piper-tts (high-quality neural TTS).
    Works with audio jack, Bluetooth, or any audio output on Raspberry Pi.
    Args:
        text (str): The text to be spoken aloud.
    """
    try:
        temp_file = "/tmp/speech.wav"
        subprocess.run(['piper', '--model', 'en_US-amy-low.onnx', '--output_file', temp_file], 
                      input=text.encode(), check=True)
        
        # Play the generated audio file
        subprocess.run(['aplay', temp_file], check=True)
        
        # Clean up temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
    except subprocess.CalledProcessError as e:
        print(f"Error with piper-tts: {e}")
    except FileNotFoundError:
        print("piper-tts not found. Please install piper-tts first.")
        print("Installation: pip install piper-tts")
        print("Or try: pip install piper-tts[onnx]")

if __name__ == "__main__":
    # Example usage: Speak a test string
    test_text = "This is a test of the text to speech system using piper-tts through the audio jack."
    speak_text(test_text)
