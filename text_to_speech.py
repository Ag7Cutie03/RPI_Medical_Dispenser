import os
import re
import subprocess
import tempfile

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

def speak(text):
    """Speak text using pico2wave if available, otherwise just print it"""
    global TTS_AVAILABLE
    
    if TTS_AVAILABLE:
        try:
            # Clean and format the text for better speech
            cleaned_text = clean_text_for_speech(text)
            print(f"🔊 Speaking: {cleaned_text}")
            
            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
            
            try:
                # Use pico2wave to convert text to speech and save as WAV
                # -w specifies output WAV file
                # -l specifies language (en-US for US English)
                subprocess.run([
                    'pico2wave', 
                    '-w', temp_wav_path, 
                    '-l', 'en-US',
                    cleaned_text
                ], check=True, capture_output=True)
                
                # Play the generated WAV file using aplay
                subprocess.run(['aplay', temp_wav_path], check=True)
                print("✓ Speech completed")
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_wav_path):
                    os.unlink(temp_wav_path)
                    
        except subprocess.CalledProcessError as e:
            print(f"❌ Speech error: {e}")
            print(f"Message: {text}")
        except Exception as e:
            print(f"❌ Speech error: {e}")
            print(f"Message: {text}")
    else:
        print(f"🔇 Speech (disabled): {text}")
        print(f"TTS_AVAILABLE: {TTS_AVAILABLE}")

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