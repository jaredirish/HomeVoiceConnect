"""
Wake word detection module for HomeVoice Connect integration.

Uses openWakeWord for efficient, local wake word detection.
"""
import asyncio
import logging
import os
import queue
import threading
import numpy as np
from typing import Callable, Optional

import openwakeword
import pyaudio

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Constants
RATE = 16000
CHUNK = 1280  # 0.08 seconds per chunk at 16kHz
FORMAT = pyaudio.paInt16
CHANNELS = 1
DETECTION_WINDOW = 2  # seconds


class WakeWordHandler:
    """Class to handle wake word detection."""

    def __init__(
        self,
        hass: HomeAssistant,
        wake_word: str,
        sensitivity: float,
    ) -> None:
        """Initialize the wake word handler."""
        self.hass = hass
        self.wake_word = wake_word
        self.sensitivity = sensitivity
        
        self._p = None
        self._stream = None
        self._running = False
        self._thread = None
        self._wake_word_model = None
        self._audio_queue = queue.Queue()
        self._callback = None
        
        # Map common wake words to built-in model names
        self._wake_word_mapping = {
            "alexa": "alexa",
            "hey computer": "hey_computer",
            "ok google": "ok_google",
            "hey google": "hey_google",
            "hey jarvis": "jarvis",
            "jarvis": "jarvis",
            "hey snapdragon": "snapdragon",
            "computer": "computer",
        }

    async def async_initialize(self) -> None:
        """Initialize the wake word detector and start listening."""
        await self.hass.async_add_executor_job(self._initialize_wake_word_model)
        self._running = True
        self._thread = threading.Thread(target=self._listen_for_wake_word, daemon=True)
        self._thread.start()
        _LOGGER.info("Wake word handler initialized with word: %s", self.wake_word)

    async def async_shutdown(self) -> None:
        """Shut down the wake word detector."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        
        if self._stream:
            await self.hass.async_add_executor_job(self._stream.stop_stream)
            await self.hass.async_add_executor_job(self._stream.close)
        
        if self._p:
            await self.hass.async_add_executor_job(self._p.terminate)
        
        _LOGGER.info("Wake word handler shut down")

    def register_wake_word_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when the wake word is detected."""
        self._callback = callback

    def _get_model_name_for_wake_word(self) -> str:
        """Get the appropriate model name for the configured wake word."""
        # Convert to lowercase and strip for consistent comparison
        normalized_wake_word = self.wake_word.lower().strip()
        
        if normalized_wake_word in self._wake_word_mapping:
            return self._wake_word_mapping[normalized_wake_word]
        
        # Default to "hey_computer" if no match
        _LOGGER.warning(
            "Wake word '%s' not found in built-in models, using 'hey_computer'",
            self.wake_word
        )
        return "hey_computer"

    def _initialize_wake_word_model(self) -> None:
        """Initialize the openWakeWord model."""
        # Create PyAudio instance
        self._p = pyaudio.PyAudio()
        
        # Create the openWakeWord detector
        self._wake_word_model = openwakeword.Model()
        
        # Get the appropriate model name
        model_name = self._get_model_name_for_wake_word()
        
        # Log available models
        available_models = self._wake_word_model.models.keys()
        _LOGGER.debug("Available wake word models: %s", available_models)
        
        # Open the audio stream
        self._stream = self._p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            stream_callback=self._audio_callback
        )
        self._stream.start_stream()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for PyAudio to get audio data."""
        if self._running:
            self._audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def _listen_for_wake_word(self) -> None:
        """Listen for the wake word in a separate thread."""
        buffer = []
        samples_per_second = RATE / CHUNK
        max_buffer_length = int(DETECTION_WINDOW * samples_per_second)
        
        try:
            while self._running:
                try:
                    audio_chunk = self._audio_queue.get(timeout=1.0)
                    
                    # Convert to int16 numpy array
                    audio_chunk_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
                    
                    # Add to buffer
                    buffer.append(audio_chunk_int16)
                    if len(buffer) > max_buffer_length:
                        buffer.pop(0)
                    
                    # Combine buffer into one array
                    audio_data = np.concatenate(buffer)
                    
                    # Process with openWakeWord
                    prediction = self._wake_word_model.predict(audio_data)
                    
                    # Check for wake word
                    model_name = self._get_model_name_for_wake_word()
                    score = prediction[f"detected_model_{model_name}"]
                    
                    if score > self.sensitivity:
                        _LOGGER.debug(
                            "Wake word detected with score %f (threshold: %f)",
                            score,
                            self.sensitivity
                        )
                        if self._callback:
                            # Run the callback in the event loop
                            asyncio.run_coroutine_threadsafe(
                                self._async_trigger_callback(), 
                                self.hass.loop
                            )
                            # Clear buffer after detection
                            buffer = []
                
                except queue.Empty:
                    pass
                except Exception as e:
                    _LOGGER.error("Error in wake word detection: %s", e)
        
        except Exception as e:
            _LOGGER.error("Wake word detection thread error: %s", e)

    async def _async_trigger_callback(self) -> None:
        """Trigger the callback in the event loop."""
        if self._callback:
            self._callback()
