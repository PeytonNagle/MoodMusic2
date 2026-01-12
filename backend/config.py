import os
import json
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


class ConfigLoader:
    """Handles loading and merging of JSON configuration files"""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            # Default to backend/configs directory
            self.config_dir = Path(__file__).parent / 'configs'
        else:
            self.config_dir = Path(config_dir)

        self.base_config = {}
        self.env_config = {}
        self.merged_config = {}

    def load(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """Load base config and environment-specific overrides"""
        # Determine environment
        if environment is None:
            environment = os.getenv('ENVIRONMENT', 'dev')

        # Load base config
        base_path = self.config_dir / 'config.json'
        self.base_config = self._load_json_file(base_path)

        # Load environment-specific config
        env_path = self.config_dir / f'config.{environment}.json'
        self.env_config = self._load_json_file(env_path, required=False)

        # Deep merge configurations
        self.merged_config = self._deep_merge(self.base_config, self.env_config)

        return self.merged_config

    def _load_json_file(self, path: Path, required: bool = True) -> Dict[str, Any]:
        """Load a JSON file from disk"""
        if not path.exists():
            if required:
                raise FileNotFoundError(f"Required config file not found: {path}")
            return {}

        try:
            with open(path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}")

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge override dict into base dict"""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def validate(self, config: Dict[str, Any]) -> bool:
        """Validate that required configuration sections exist"""
        required_sections = [
            'request_handling',
            'gemini',
            'spotify',
            'popularity',
            'database'
        ]

        missing = [sec for sec in required_sections if sec not in config]

        if missing:
            raise ValueError(f"Missing required config sections: {missing}")

        return True


class Config:
    """Enhanced configuration class with JSON config support"""

    # API Keys from environment (keep backward compatibility)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
    SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Load JSON configurations
    _loader = ConfigLoader()
    _config_data = {}
    DEBUG = True  # Default until initialized

    @classmethod
    def initialize(cls, environment: Optional[str] = None):
        """Initialize configuration from JSON files"""
        try:
            cls._config_data = cls._loader.load(environment)
            cls._loader.validate(cls._config_data)

            # Set DEBUG from config or env var
            cls.DEBUG = cls._config_data.get('flask', {}).get('debug',
                                            os.getenv('DEBUG', 'True').lower() == 'true')
        except (FileNotFoundError, ValueError) as e:
            print(f"Warning: Failed to load JSON config: {e}")
            print("Falling back to default values")
            # Set default empty config to allow fallback to hardcoded defaults
            cls._config_data = {
                'request_handling': {},
                'gemini': {},
                'spotify': {},
                'popularity': {},
                'database': {},
                'flask': {}
            }

    @classmethod
    def get(cls, path: str, default: Any = None) -> Any:
        """
        Get nested config value using dot notation.
        Example: Config.get('gemini.temperatures.analysis') -> 0.4
        """
        keys = path.split('.')
        value = cls._config_data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value

    # Convenience methods for commonly used values
    @classmethod
    def max_emojis(cls) -> int:
        return cls.get('request_handling.max_emojis', 12)

    @classmethod
    def default_song_limit(cls) -> int:
        return cls.get('request_handling.song_limits.default', 10)

    @classmethod
    def min_song_limit(cls) -> int:
        return cls.get('request_handling.song_limits.min', 10)

    @classmethod
    def max_song_limit(cls) -> int:
        return cls.get('request_handling.song_limits.max', 50)

    @classmethod
    def save_queue_enabled(cls) -> bool:
        return cls.get('database.save_queue.enabled', True)

    @classmethod
    def save_requests_enabled(cls) -> bool:
        return cls.get('database.persistence.save_requests', True)

    @classmethod
    def save_songs_enabled(cls) -> bool:
        return cls.get('database.persistence.save_songs', True)

    @classmethod
    def save_queue_max_size(cls) -> int:
        return cls.get('database.save_queue.max_size', 100)

    @classmethod
    def save_queue_behavior(cls) -> str:
        """Returns: 'skip', 'block', or 'error'"""
        return cls.get('database.save_queue.behavior_on_full', 'skip')

    @staticmethod
    def validate_config():
        """Validate that required API keys are present"""
        required_vars = [
            ('GEMINI_API_KEY', Config.GEMINI_API_KEY),
            ('SPOTIPY_CLIENT_ID', Config.SPOTIPY_CLIENT_ID),
            ('SPOTIPY_CLIENT_SECRET', Config.SPOTIPY_CLIENT_SECRET)
        ]

        missing_vars = [name for name, value in required_vars if not value]

        if missing_vars:
            print(f"Warning: Missing required environment variables: {', '.join(missing_vars)}")
            print("Please add them to your .env file")
            return False

        return True


# Initialize config on module load
Config.initialize()
