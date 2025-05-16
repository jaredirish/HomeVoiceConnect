"""Constants for the HomeVoice Connect integration."""

# Domain
DOMAIN = "homevoice_connect"

# Configuration constants
CONF_WAKE_WORD = "wake_word"
CONF_WAKE_WORD_SENSITIVITY = "wake_word_sensitivity"
CONF_INPUT_DEVICE = "input_device"
CONF_OUTPUT_DEVICE = "output_device"
CONF_TTS_SERVICE = "tts_service"

# Default values
DEFAULT_NAME = "HomeVoice Connect"
DEFAULT_WAKE_WORD = "hey computer"
DEFAULT_WAKE_WORD_SENSITIVITY = 0.5
DEFAULT_TTS_SERVICE = "tts.google_translate_say"

# States
STATE_IDLE = "idle"
STATE_LISTENING = "listening"
STATE_PROCESSING = "processing"
STATE_RESPONDING = "responding"

# Events
EVENT_WAKE_WORD_DETECTED = f"{DOMAIN}_wake_word_detected"
EVENT_COMMAND_CAPTURED = f"{DOMAIN}_command_captured"
EVENT_RESPONSE_RECEIVED = f"{DOMAIN}_response_received"
EVENT_RESPONSE_PLAYED = f"{DOMAIN}_response_played"
