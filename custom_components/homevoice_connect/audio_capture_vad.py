"""
Audio capture with Voice Activity Detection for HomeVoice Connect.

Uses WebRTC VAD for efficient voice activity detection to determine
when a user has finished speaking.
"""
import asyncio
import logging
import os
import queue
import threading
import numpy as np
import webrtcvad
import pyaudio
import wave
from typing import Optional
import tempfile

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Constants
RATE = 16000
CHUNK_DURATION_MS = 30
CHUNK_SIZE = int(RATE * CHUNK_DURATION_MS / 1000)
FORMAT = pyaudio.paInt16
CHANNELS = 1
VAD_AGGRESSIVE_MODE = 3  # 0-3, 3 is most aggressive
SPEECH_TIMEOUT_SECS = 2.0  # Stop capturing after this much silence
MAX_RECORDING_SECS = 15.0  # Maximum recording time
PADDING_DURATION_MS = 300  # Add padding to the end of the recording


class AudioCaptureVAD:
    """Class to handle audio capture with Voice Activity Detection."""

    def __init__(
        self,
        hass: HomeAssistant,
        input_device: str,
    ) -> None:
        """Initialize the audio capture."""
        self.hass = hass
        self.input_device = input_device
        
        self._p = None
        self._stream = None
        self._vad = None
        self._audio_queue = queue.Queue()
        self._temp_file = None
        self._recording = False
        self._thread = None

    async def async_initialize(self) -> None:
        """Initialize the audio capture and VAD."""
        self._vad = webrtcvad.Vad(VAD_AGGRESSIVE_MODE)
        self._p = pyaudio.PyAudio()
        
        # Find the device index for the specified input device
        device_index = await self._find_device_index()
        
        if device_index is None:
            _LOGGER.error(f"Could not find audio device: {self.input_device}")
            return
        
        _LOGGER.info(f"Initialized audio capture with device: {self.input_device} (index: {device_index})")

    async def async_shutdown(self) -> None:
        """Shut down the audio capture."""
        if self._recording and self._thread:
            self._recording = False
            self._thread.join(timeout=2.0)
        
        if self._stream:
            await self.hass.async_add_executor_job(self._stream.stop_stream)
            await self.hass.async_add_executor_job(self._stream.close)
        
        if self._p:
            await self.hass.async_add_executor_job(self._p.terminate)
        
        _LOGGER.info("Audio capture shut down")

    async def _find_device_index(self) -> Optional[int]:
        """Find the device index for the specified input device."""
        for i in range(self._p.get_device_count()):
            device_info = self._p.get_device_info_by_index(i)
            if (
                device_info["maxInputChannels"] > 0 and
                self.input_device.lower() in device_info["name"].lower()
            ):
                return i
        return None

    async def capture_audio(self) -> Optional[str]:
        """
        Capture audio with VAD and return the path to the audio file.
        
        Returns:
            Optional[str]: Path to the recorded audio file, or None if no audio was captured.
        """
        if self._recording:
            _LOGGER.warning("Audio capture already in progress")
            return None
        
        # Create a temporary file to store the audio
        self._temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_filename = self._temp_file.name
        self._temp_file.close()
        
        # Start recording in a separate thread
        self._recording = True
        recording_event = asyncio.Event()
        
        self._thread = threading.Thread(
            target=self._capture_with_vad,
            args=(temp_filename, recording_event)
        )
        self._thread.start()
        
        # Wait for recording to complete or timeout
        try:
            # Use a timeout slightly longer than MAX_RECORDING_SECS
            await asyncio.wait_for(recording_event.wait(), timeout=MAX_RECORDING_SECS + 2)
        except asyncio.TimeoutError:
            _LOGGER.warning("Audio capture timed out")
            self._recording = False
            self._thread.join()
            if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
                return temp_filename
            return None
        
        # Check if audio was captured successfully
        if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
            return temp_filename
        
        return None

    def _capture_with_vad(self, output_filename: str, recording_event: asyncio.Event) -> None:
        """
        Capture audio with VAD in a separate thread.
        
        Args:
            output_filename: Path to save the recorded audio
            recording_event: Event to signal when recording is complete
        """
        try:
            # Find the device index for the specified input device
            device_index = None
            for i in range(self._p.get_device_count()):
                device_info = self._p.get_device_info_by_index(i)
                if (
                    device_info["maxInputChannels"] > 0 and
                    self.input_device.lower() in device_info["name"].lower()
                ):
                    device_index = i
                    break
            
            if device_index is None:
                _LOGGER.error(f"Could not find audio device: {self.input_device}")
                recording_event.set()
                return
            
            # Open the audio stream
            self._stream = self._p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=CHUNK_SIZE
            )
            
            # Initialize wave file for recording
            wav_file = wave.open(output_filename, 'wb')
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(self._p.get_sample_size(FORMAT))
            wav_file.setframerate(RATE)
            
            # Initialize VAD state
            voiced_frames = []
            triggered = False
            ring_buffer = collections.deque(maxlen=int(PADDING_DURATION_MS / CHUNK_DURATION_MS))
            
            # Counters and timers
            num_silent_chunks = 0
            num_voiced_chunks = 0
            start_time = time.time()
            
            _LOGGER.debug("Starting audio capture")
            while self._recording:
                # Read audio chunk
                frame = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                
                # Check if this chunk contains speech
                is_speech = self._vad.is_speech(frame, RATE)
                
                if not triggered:
                    # Not yet triggered, add to ring buffer
                    ring_buffer.append((frame, is_speech))
                    num_voiced_chunks = sum(1 for _, speech in ring_buffer if speech)
                    
                    # If enough voiced chunks, trigger
                    if num_voiced_chunks > 0.5 * ring_buffer.maxlen:
                        triggered = True
                        _LOGGER.debug("Speech detected, recording started")
                        
                        # Add the buffered frames
                        for f, _ in ring_buffer:
                            voiced_frames.append(f)
                        
                        ring_buffer.clear()
                        num_silent_chunks = 0
                
                else:
                    # Already triggered, add frame
                    voiced_frames.append(frame)
                    
                    # Check for silence to determine end of speech
                    if not is_speech:
                        num_silent_chunks += 1
                        if num_silent_chunks > (SPEECH_TIMEOUT_SECS * 1000) / CHUNK_DURATION_MS:
                            _LOGGER.debug("Silence detected, recording stopped")
                            triggered = False
                            break
                    else:
                        num_silent_chunks = 0
                
                # Check for max recording time
                if time.time() - start_time > MAX_RECORDING_SECS:
                    _LOGGER.debug("Max recording time reached")
                    break
            
            # Write all voiced frames to the wave file
            for frame in voiced_frames:
                wav_file.writeframes(frame)
            
            # Clean up
            wav_file.close()
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
            
            _LOGGER.info(f"Audio capture complete, saved to {output_filename}")
            
        except Exception as e:
            _LOGGER.error(f"Error in audio capture: {e}")
        
        finally:
            self._recording = False
            recording_event.set()

import collections
import time
