from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import os
import sys
import logging
import subprocess
import json
from werkzeug.middleware.proxy_fix import ProxyFix

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration constants
DOMAIN = "homevoice_connect"
CONFIG_PATH = "config"
SAMPLE_AUDIO_PATH = "sample_audio"

# Ensure necessary directories exist
os.makedirs(CONFIG_PATH, exist_ok=True)
os.makedirs(SAMPLE_AUDIO_PATH, exist_ok=True)

# Load or initialize configuration
def load_config():
    config_file = os.path.join(CONFIG_PATH, "config.json")
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    return {
        "name": "HomeVoice Connect",
        "api_key": "",
        "wake_word": "hey computer",
        "wake_word_sensitivity": 0.5,
        "input_device": "",
        "output_device": "",
        "tts_service": "tts.google_translate_say"
    }

def save_config(config):
    config_file = os.path.join(CONFIG_PATH, "config.json")
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return False

# Load available wake words from the integration
def get_available_wake_words():
    try:
        # This would normally query the component, but we'll use a static list for now
        return [
            "alexa", 
            "hey computer", 
            "ok google", 
            "hey google", 
            "hey jarvis", 
            "jarvis", 
            "hey snapdragon", 
            "computer"
        ]
    except Exception as e:
        logger.error(f"Error loading wake words: {e}")
        return ["hey computer"]

# Detect available audio devices
def get_audio_devices():
    try:
        # In a real implementation, this would detect actual audio devices
        # For our demo, we'll return some sample devices
        return {
            "input": ["Built-in Microphone", "USB Audio Device", "Webcam Microphone"],
            "output": ["Built-in Speakers", "HDMI Audio", "Bluetooth Speaker"]
        }
    except Exception as e:
        logger.error(f"Error detecting audio devices: {e}")
        return {"input": [], "output": []}

# Get available TTS services
def get_tts_services():
    try:
        # In a real implementation, this would query Home Assistant
        # For our demo, we'll return some sample services
        return [
            "tts.google_translate_say",
            "tts.cloud_say",
            "tts.piper_say"
        ]
    except Exception as e:
        logger.error(f"Error loading TTS services: {e}")
        return ["tts.google_translate_say"]

# Test wake word detection
def test_wake_word(wake_word, sensitivity):
    # This would normally trigger actual wake word detection
    # For our demo, we'll simulate success
    logger.info(f"Testing wake word '{wake_word}' with sensitivity {sensitivity}")
    return True

# Test audio capture
def test_audio_capture(input_device):
    # This would normally trigger actual audio capture
    # For our demo, we'll simulate success
    logger.info(f"Testing audio capture with device '{input_device}'")
    return True

# Test Gemini API
def test_gemini_api(api_key):
    # This would normally validate the API key with Gemini
    # For our demo, we'll check if the key looks valid (non-empty)
    if not api_key:
        return False
    logger.info(f"Testing Gemini API key: {api_key[:5]}...")
    return len(api_key) > 10  # Simple validation

# Test TTS output
def test_tts(output_device, tts_service):
    # This would normally trigger actual TTS playback
    # For our demo, we'll simulate success
    logger.info(f"Testing TTS '{tts_service}' on device '{output_device}'")
    return True

# Routes
@app.route('/')
def index():
    config = load_config()
    audio_devices = get_audio_devices()
    wake_words = get_available_wake_words()
    tts_services = get_tts_services()
    
    return render_template('index.html', 
                           config=config,
                           audio_devices=audio_devices,
                           wake_words=wake_words,
                           tts_services=tts_services)

@app.route('/config', methods=['POST'])
def update_config():
    config = load_config()
    
    # Update config with form data
    config['name'] = request.form.get('name', config['name'])
    config['api_key'] = request.form.get('api_key', config['api_key'])
    config['wake_word'] = request.form.get('wake_word', config['wake_word'])
    config['wake_word_sensitivity'] = float(request.form.get('wake_word_sensitivity', config['wake_word_sensitivity']))
    config['input_device'] = request.form.get('input_device', config['input_device'])
    config['output_device'] = request.form.get('output_device', config['output_device'])
    config['tts_service'] = request.form.get('tts_service', config['tts_service'])
    
    if save_config(config):
        flash('Configuration saved successfully!', 'success')
    else:
        flash('Error saving configuration.', 'danger')
    
    return redirect(url_for('index'))

@app.route('/test/wake_word', methods=['POST'])
def test_wake_word_route():
    config = load_config()
    wake_word = request.form.get('wake_word', config['wake_word'])
    sensitivity = float(request.form.get('sensitivity', config['wake_word_sensitivity']))
    
    success = test_wake_word(wake_word, sensitivity)
    
    return jsonify({
        'success': success,
        'message': 'Wake word detection test ' + ('successful' if success else 'failed')
    })

@app.route('/test/audio_capture', methods=['POST'])
def test_audio_capture_route():
    config = load_config()
    input_device = request.form.get('input_device', config['input_device'])
    
    success = test_audio_capture(input_device)
    
    return jsonify({
        'success': success,
        'message': 'Audio capture test ' + ('successful' if success else 'failed')
    })

@app.route('/test/gemini_api', methods=['POST'])
def test_gemini_api_route():
    config = load_config()
    api_key = request.form.get('api_key', config['api_key'])
    
    success = test_gemini_api(api_key)
    
    return jsonify({
        'success': success,
        'message': 'Gemini API test ' + ('successful' if success else 'failed')
    })

@app.route('/test/tts', methods=['POST'])
def test_tts_route():
    config = load_config()
    output_device = request.form.get('output_device', config['output_device'])
    tts_service = request.form.get('tts_service', config['tts_service'])
    
    success = test_tts(output_device, tts_service)
    
    return jsonify({
        'success': success,
        'message': 'TTS test ' + ('successful' if success else 'failed')
    })

@app.route('/status')
def status():
    """Return the status of the integration components."""
    # This would normally check the actual status of the integration
    # For our demo, we'll return a simulated status
    config = load_config()
    
    # Simple validation
    api_key_valid = bool(config['api_key'])
    input_device_valid = bool(config['input_device'])
    output_device_valid = bool(config['output_device'])
    
    status = {
        'wake_word_detector': {
            'status': 'running' if api_key_valid else 'stopped',
            'config': {
                'wake_word': config['wake_word'],
                'sensitivity': config['wake_word_sensitivity']
            }
        },
        'audio_capture': {
            'status': 'ready' if input_device_valid else 'not_configured',
            'device': config['input_device']
        },
        'gemini_api': {
            'status': 'connected' if api_key_valid else 'not_configured',
            'key_valid': api_key_valid
        },
        'tts_output': {
            'status': 'ready' if output_device_valid else 'not_configured',
            'device': config['output_device'],
            'service': config['tts_service']
        }
    }
    
    return jsonify(status)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)