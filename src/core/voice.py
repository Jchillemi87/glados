# src/core/voice.py
import io
import wave
from typing import Optional
from src.core.config import settings
from wyoming.client import AsyncTcpClient
from wyoming.event import Event
from wyoming.audio import AudioChunk, AudioStart, AudioStop 

async def generate_speech(text: str) -> Optional[bytes]:
    """
    Connects to the Piper Wyoming Docker container via TCP.
    Sends text -> Receives Raw PCM -> Converts to WAV -> Returns Bytes.
    """
    if not text or not text.strip():
        return None

    # Default settings (will be updated by the AudioStart event)
    audio_data = bytearray()
    sample_rate = 22050
    sample_width = 2
    channels = 1

    try:
        # 1. Connect to Unraid
        client = AsyncTcpClient(settings.UNRAID_IP, settings.PORT_PIPER)
        await client.connect()

        # 2. Send Request (Manual Event Construction)
        # We manually build the payload to avoid typing issues with the Synthesize helper.
        # Piper expects 'voice' to be a dictionary with 'name'.
        payload = {
            "text": text,
            "voice": {"name": settings.PIPER_VOICE_ID} 
        }
        
        # Create the raw Wyoming Event
        event = Event(type="synthesize", data=payload)
        
        await client.write_event(event)

        # 3. Read Response Stream
        while True:
            event = await client.read_event()
            if event is None:
                break

            if AudioStart.is_type(event.type):
                start = AudioStart.from_event(event)
                sample_rate = start.rate
                sample_width = start.width
                channels = start.channels

            elif AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                audio_data.extend(chunk.audio)

            elif AudioStop.is_type(event.type):
                break

        await client.disconnect()

        if not audio_data:
            print("[VOICE WARNING] Piper returned no audio data.")
            return None

        # 4. Convert Raw PCM to WAV
        # Browsers require a WAV container header to play the audio.
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        
        return wav_buffer.getvalue()

    except Exception as e:
        print(f"[VOICE ERROR] Wyoming Protocol Failed: {e}")
        return None