import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# existing stuff like OPENAI_KEY, etc, probably here...

DATABASE_URL = os.getenv("DATABASE_URL")

class Config:
    """Configuration class for the Flask application"""
    
    # OpenAI Configuration (legacy)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

    # Gemini Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Spotify Configuration
    SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
    SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    @staticmethod
    def validate_config():
        """Validate that required configuration is present"""
        required_vars = [
            'GEMINI_API_KEY',
            'SPOTIPY_CLIENT_ID', 
            'SPOTIPY_CLIENT_SECRET'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(Config, var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"Warning: Missing required environment variables: {', '.join(missing_vars)}")
            print("Please add them to your .env file")
            return False
        
        return True


