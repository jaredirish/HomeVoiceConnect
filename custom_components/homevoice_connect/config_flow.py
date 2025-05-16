"""Config flow for HomeVoice Connect integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICE_ID,
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

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

_LOGGER = logging.getLogger(__name__)


class HomeVoiceConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomeVoice Connect."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HomeVoiceConnectOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Validate the API key
            if not user_input.get(CONF_API_KEY):
                errors[CONF_API_KEY] = "missing_api_key"
            
            # Validate input and output devices
            if not user_input.get(CONF_INPUT_DEVICE):
                errors[CONF_INPUT_DEVICE] = "missing_input_device"
                
            if not user_input.get(CONF_OUTPUT_DEVICE):
                errors[CONF_OUTPUT_DEVICE] = "missing_output_device"

            if not errors:
                # Input is valid, set up the entry
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data=user_input,
                )

        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_WAKE_WORD, default=DEFAULT_WAKE_WORD): str,
                    vol.Optional(
                        CONF_WAKE_WORD_SENSITIVITY, default=DEFAULT_WAKE_WORD_SENSITIVITY
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
                    vol.Required(CONF_INPUT_DEVICE): str,
                    vol.Required(CONF_OUTPUT_DEVICE): str,
                    vol.Optional(CONF_TTS_SERVICE, default=DEFAULT_TTS_SERVICE): str,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)


class HomeVoiceConnectOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_WAKE_WORD,
                default=self.config_entry.options.get(
                    CONF_WAKE_WORD, self.config_entry.data.get(CONF_WAKE_WORD, DEFAULT_WAKE_WORD)
                ),
            ): str,
            vol.Optional(
                CONF_WAKE_WORD_SENSITIVITY,
                default=self.config_entry.options.get(
                    CONF_WAKE_WORD_SENSITIVITY, 
                    self.config_entry.data.get(CONF_WAKE_WORD_SENSITIVITY, DEFAULT_WAKE_WORD_SENSITIVITY)
                ),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=1.0)),
            vol.Optional(
                CONF_TTS_SERVICE,
                default=self.config_entry.options.get(
                    CONF_TTS_SERVICE, self.config_entry.data.get(CONF_TTS_SERVICE, DEFAULT_TTS_SERVICE)
                ),
            ): str,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
