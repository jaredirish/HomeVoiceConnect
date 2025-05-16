"""
HomeVoice Connect integration for Home Assistant.

This integration provides an always-on, local wake word activated voice assistant
using Google's Gemini Live API.
"""
import asyncio
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_NAME,
    Platform,
)

from .const import (
    DOMAIN,
    CONF_WAKE_WORD,
    CONF_WAKE_WORD_SENSITIVITY,
    CONF_INPUT_DEVICE,
    CONF_OUTPUT_DEVICE,
    CONF_TTS_SERVICE,
    DEFAULT_NAME,
    DEFAULT_WAKE_WORD,
    DEFAULT_WAKE_WORD_SENSITIVITY,
    DEFAULT_TTS_SERVICE,
)
from .wake_word_handler import WakeWordHandler
from .audio_capture_vad import AudioCaptureVAD
from .gemini_live_client import GeminiLiveClient
from .response_handler import ResponseHandler

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_WAKE_WORD, default=DEFAULT_WAKE_WORD): cv.string,
                vol.Optional(
                    CONF_WAKE_WORD_SENSITIVITY, default=DEFAULT_WAKE_WORD_SENSITIVITY
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
                vol.Required(CONF_INPUT_DEVICE): cv.string,
                vol.Required(CONF_OUTPUT_DEVICE): cv.string,
                vol.Optional(CONF_TTS_SERVICE, default=DEFAULT_TTS_SERVICE): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# Define platforms that this integration supports
PLATFORMS: list[Platform] = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomeVoice Connect component."""
    if DOMAIN not in config:
        return True

    hass.data.setdefault(DOMAIN, {})
    conf = config[DOMAIN]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=conf,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomeVoice Connect from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create component instances
    wake_word_handler = WakeWordHandler(
        hass, 
        entry.data.get(CONF_WAKE_WORD, DEFAULT_WAKE_WORD),
        entry.data.get(CONF_WAKE_WORD_SENSITIVITY, DEFAULT_WAKE_WORD_SENSITIVITY)
    )
    
    audio_capture = AudioCaptureVAD(
        hass,
        entry.data.get(CONF_INPUT_DEVICE)
    )
    
    gemini_client = GeminiLiveClient(
        hass,
        entry.data.get(CONF_API_KEY)
    )
    
    response_handler = ResponseHandler(
        hass,
        entry.data.get(CONF_OUTPUT_DEVICE),
        entry.data.get(CONF_TTS_SERVICE, DEFAULT_TTS_SERVICE)
    )

    # Store for use during cleanup
    homevoice_connect = HomeVoiceConnect(
        hass,
        wake_word_handler,
        audio_capture,
        gemini_client,
        response_handler
    )
    
    await homevoice_connect.async_initialize()
    
    hass.data[DOMAIN][entry.entry_id] = homevoice_connect

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    # Define services here if needed
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        homevoice_connect = hass.data[DOMAIN].pop(entry.entry_id)
        await homevoice_connect.async_shutdown()

    return unload_ok


class HomeVoiceConnect:
    """Class to manage the HomeVoice Connect integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        wake_word_handler: WakeWordHandler,
        audio_capture: AudioCaptureVAD,
        gemini_client: GeminiLiveClient,
        response_handler: ResponseHandler,
    ) -> None:
        """Initialize the HomeVoice Connect integration."""
        self.hass = hass
        self.wake_word_handler = wake_word_handler
        self.audio_capture = audio_capture
        self.gemini_client = gemini_client
        self.response_handler = response_handler
        
        self._current_state = "IDLE_LISTENING_FOR_WAKE_WORD"
        self._running = False
        self._loop_task = None

    async def async_initialize(self) -> None:
        """Initialize all components and start the main loop."""
        await self.wake_word_handler.async_initialize()
        await self.audio_capture.async_initialize()
        await self.gemini_client.async_initialize()
        await self.response_handler.async_initialize()
        
        # Register callback for wake word detection
        self.wake_word_handler.register_wake_word_callback(self._wake_word_detected)
        
        # Start the main loop
        self._running = True
        self._loop_task = asyncio.create_task(self._main_loop())
        
        _LOGGER.info("HomeVoice Connect integration initialized")

    async def async_shutdown(self) -> None:
        """Shut down all components."""
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        
        await self.wake_word_handler.async_shutdown()
        await self.audio_capture.async_shutdown()
        await self.gemini_client.async_shutdown()
        await self.response_handler.async_shutdown()
        
        _LOGGER.info("HomeVoice Connect integration shut down")

    async def _main_loop(self) -> None:
        """Main loop for the state machine."""
        while self._running:
            try:
                if self._current_state == "IDLE_LISTENING_FOR_WAKE_WORD":
                    # The wake word handler is already listening in its own thread
                    # and will call _wake_word_detected when triggered
                    await asyncio.sleep(0.1)
                
                elif self._current_state == "CAPTURING_COMMAND":
                    _LOGGER.debug("Starting audio capture")
                    audio_data = await self.audio_capture.capture_audio()
                    if audio_data:
                        self._current_state = "PROCESSING_WITH_GEMINI"
                        _LOGGER.debug("Audio capture complete, processing with Gemini")
                    else:
                        # If no audio was captured (timeout or error), return to listening
                        self._current_state = "IDLE_LISTENING_FOR_WAKE_WORD"
                        _LOGGER.debug("No audio captured, returning to wake word detection")
                
                elif self._current_state == "PROCESSING_WITH_GEMINI":
                    _LOGGER.debug("Sending audio to Gemini Live API")
                    response = await self.gemini_client.process_audio(audio_data)
                    self._current_state = "RESPONDING"
                    _LOGGER.debug("Received response from Gemini")
                
                elif self._current_state == "RESPONDING":
                    _LOGGER.debug("Playing response")
                    await self.response_handler.play_response(response)
                    self._current_state = "IDLE_LISTENING_FOR_WAKE_WORD"
                    _LOGGER.debug("Response complete, returning to wake word detection")
                
                else:
                    _LOGGER.error(f"Unknown state: {self._current_state}")
                    self._current_state = "IDLE_LISTENING_FOR_WAKE_WORD"
            
            except Exception as e:
                _LOGGER.error(f"Error in main loop: {e}")
                self._current_state = "IDLE_LISTENING_FOR_WAKE_WORD"
                await asyncio.sleep(1)  # Prevent tight loop on persistent errors

    @callback
    def _wake_word_detected(self) -> None:
        """Handle wake word detection."""
        _LOGGER.info("Wake word detected!")
        self._current_state = "CAPTURING_COMMAND"
        # The main loop will pick up this state change and proceed to audio capture
