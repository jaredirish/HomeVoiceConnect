from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class VoiceInteraction(db.Model):
    """Model to store voice interaction data."""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Audio data and processing
    wake_word = db.Column(db.String(50), nullable=False)
    wake_word_sensitivity = db.Column(db.Float, nullable=False)
    audio_path = db.Column(db.String(255), nullable=True)  # Path to stored audio file
    transcription = db.Column(db.Text, nullable=True)      # What the user said (transcribed)
    
    # Response data
    response_text = db.Column(db.Text, nullable=True)      # AI response text
    response_time_ms = db.Column(db.Integer, nullable=True)  # Processing time in milliseconds
    
    # Device information
    input_device = db.Column(db.String(100), nullable=True)
    output_device = db.Column(db.String(100), nullable=True)
    
    # Status and additional info
    status = db.Column(db.String(20), default="completed", nullable=False)  # completed, error, etc.
    error_message = db.Column(db.Text, nullable=True)  # Error details if any
    gemini_api_version = db.Column(db.String(50), nullable=True)  # Which API version was used
    
    def __init__(self, **kwargs):
        """Initialize with keyword arguments."""
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __repr__(self):
        if self.transcription:
            return f"<VoiceInteraction {self.id}: {self.transcription[:30]}>"
        return f"<VoiceInteraction {self.id}>"


class Configuration(db.Model):
    """Model to store integration configuration."""
    id = db.Column(db.Integer, primary_key=True)
    
    # General configuration
    name = db.Column(db.String(100), default="HomeVoice Connect", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # API configuration
    api_key = db.Column(db.String(255), nullable=True)
    
    # Wake word configuration
    wake_word = db.Column(db.String(50), default="hey computer", nullable=False)
    wake_word_sensitivity = db.Column(db.Float, default=0.5, nullable=False)
    
    # Device configuration
    input_device = db.Column(db.String(100), nullable=True)
    output_device = db.Column(db.String(100), nullable=True)
    tts_service = db.Column(db.String(100), default="tts.google_translate_say", nullable=False)
    
    # Stats
    total_interactions = db.Column(db.Integer, default=0, nullable=False)
    successful_interactions = db.Column(db.Integer, default=0, nullable=False)
    failed_interactions = db.Column(db.Integer, default=0, nullable=False)
    
    # Active flag - only one configuration can be active at a time
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    def __init__(self, **kwargs):
        """Initialize with keyword arguments."""
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __repr__(self):
        return f"<Configuration {self.id}: {self.name}>"


class SavedResponse(db.Model):
    """Model to store saved responses for quick retrieval."""
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Response mapping data
    command_pattern = db.Column(db.String(255), nullable=False, unique=True)  # Pattern to match against
    response_text = db.Column(db.Text, nullable=False)  # Predefined response
    priority = db.Column(db.Integer, default=0, nullable=False)  # Higher priority responses match first
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    
    # Usage tracking
    match_count = db.Column(db.Integer, default=0, nullable=False)  # Number of times this response was used
    last_used = db.Column(db.DateTime, nullable=True)
    
    def __init__(self, **kwargs):
        """Initialize with keyword arguments."""
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __repr__(self):
        return f"<SavedResponse {self.id}: {self.command_pattern}>"