"""
Response handler for HomeVoice Connect.

Manages playing back responses through Home Assistant TTS or media players.
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID, 
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.tts import DOMAIN as TTS_DOMAIN

_LOGGER = logging.getLogger(__name__)

class ResponseHandler:
    """Handler for playing back responses through Home Assistant."""

    def __init__(
        self,
        hass: HomeAssistant,
        output_device: str,
        tts_service: str,
    ) -> None:
        """Initialize the response handler."""
        self.hass = hass
        self.output_device = output_device
        self.tts_service = tts_service

    async def async_initialize(self) -> None:
        """Initialize the response handler."""
        # Verify that the output device exists
        if not await self._verify_output_device():
            _LOGGER.error(f"Output device not found: {self.output_device}")
            raise ValueError(f"Output device not found: {self.output_device}")
        
        # Verify that the TTS service exists
        if not await self._verify_tts_service():
            _LOGGER.error(f"TTS service not found: {self.tts_service}")
            raise ValueError(f"TTS service not found: {self.tts_service}")
        
        _LOGGER.info(f"Response handler initialized with device: {self.output_device}, TTS: {self.tts_service}")

    async def async_shutdown(self) -> None:
        """Shut down the response handler."""
        # No specific shutdown needed
        pass

    async def play_response(self, response: Dict[str, Any]) -> None:
        """
        Play the response using Home Assistant's services.
        
        Args:
            response: Dictionary containing 'text' and optionally 'audio_response'
        """
        if not response:
            _LOGGER.error("Empty response received")
            return
        
        text_response = response.get("text")
        audio_response = response.get("audio_response")
        
        if not text_response and not audio_response:
            _LOGGER.error("Response contains neither text nor audio")
            return
        
        try:
            if audio_response:
                # If we have direct audio, play it
                await self._play_audio(audio_response)
            elif text_response:
                # Otherwise use TTS
                await self._play_tts(text_response)
        except Exception as e:
            _LOGGER.error(f"Error playing response: {e}")

    async def _verify_output_device(self) -> bool:
        """Verify that the output device exists."""
        states = self.hass.states.async_all(MEDIA_PLAYER_DOMAIN)
        for state in states:
            if state.entity_id == self.output_device or state.entity_id == f"media_player.{self.output_device}":
                return True
        return False

    async def _verify_tts_service(self) -> bool:
        """Verify that the TTS service exists."""
        services = self.hass.services.async_services()
        tts_domain = self.tts_service.split(".", 1)[0] if "." in self.tts_service else TTS_DOMAIN
        tts_service = self.tts_service.split(".", 1)[1] if "." in self.tts_service else self.tts_service
        
        return tts_domain in services and tts_service in services.get(tts_domain, {})

    async def _play_tts(self, text: str) -> None:
        """
        Play text using the TTS service.
        
        Args:
            text: Text to speak
        """
        _LOGGER.debug(f"Playing TTS: {text[:50]}...")
        
        # Split service into domain and service
        domain, service = (
            self.tts_service.split(".", 1) 
            if "." in self.tts_service 
            else (TTS_DOMAIN, self.tts_service)
        )
        
        # Format media player entity ID if needed
        entity_id = (
            self.output_device 
            if self.output_device.startswith("media_player.") 
            else f"media_player.{self.output_device}"
        )
        
        # Call the TTS service
        service_data = {
            "entity_id": entity_id,
            "message": text,
        }
        
        await self.hass.services.async_call(
            domain,
            service,
            service_data,
            blocking=True,
        )
        
        _LOGGER.info(f"TTS response played on {entity_id}")

    async def _play_audio(self, audio_data: Any) -> None:
        """
        Play audio directly on a media player.
        
        Args:
            audio_data: Audio data or URL to play
        """
        # Note: This method would be implemented if/when Gemini Live provides direct audio responses
        # For now, it's a placeholder
        
        _LOGGER.warning("Direct audio playback not implemented yet")
        
        # Example implementation if audio_data were a URL:
        # entity_id = (
        #     self.output_device 
        #     if self.output_device.startswith("media_player.") 
        #     else f"media_player.{self.output_device}"
        # )
        #
        # await self.hass.services.async_call(
        #     MEDIA_PLAYER_DOMAIN,
        #     SERVICE_PLAY_MEDIA,
        #     {
        #         "entity_id": entity_id,
        #         ATTR_MEDIA_CONTENT_ID: audio_data,
        #         ATTR_MEDIA_CONTENT_TYPE: "audio/mp3",
        #     },
        #     blocking=True,
        # )
