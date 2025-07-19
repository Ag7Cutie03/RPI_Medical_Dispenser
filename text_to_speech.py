import subprocess
import time
import os

def set_max_volume():
    """Set system volume to maximum and unmute audio jack output."""
    try:
        subprocess.run(['amixer', 'set', 'Master', '100%'], check=True)
        subprocess.run(['amixer', 'set', 'Master', 'unmute'], check=True)
        # Force output to audio jack (if on Raspberry Pi)
        subprocess.run(['amixer', 'cset', 'numid=3', '1'], check=True)
    except Exception as e:
        print(f"Warning: Could not set max volume or force audio jack: {e}")

def speak(text, voice='en_US-amy-low', output_wav='output.wav'):
    """
    Use Piper TTS to synthesize speech from text and play it.
    :param text: The text to speak.
    :param voice: Piper voice model to use (default: en_US-amy-low).
    :param output_wav: Output WAV file name.
    """
    set_max_volume()
    time.sleep(1)  # Short wait before speaking
    start_time = time.perf_counter()
    # Write text to a temporary file
    with open('tts_input.txt', 'w', encoding='utf-8') as f:
        f.write(text)
    # Run Piper to generate speech
    try:
        subprocess.run([
            'piper',
            '--model', f'/usr/share/piper/models/{voice}.onnx',
            '--output_file', output_wav,
            '--input_file', 'tts_input.txt'
        ], check=True)
        # Play the generated WAV file
        subprocess.run(['aplay', output_wav], check=True)
        elapsed = time.perf_counter() - start_time
        print(f"[BENCHMARK] TTS synthesis and playback for '{text[:30]}...' took {elapsed:.2f} seconds.")
    except Exception as e:
        print(f"Piper TTS error: {e}")
    finally:
        if os.path.exists('tts_input.txt'):
            os.remove('tts_input.txt')
        if os.path.exists(output_wav):
            os.remove(output_wav) 