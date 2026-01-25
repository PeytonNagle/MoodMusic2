"""Blueprint registration for MoodMusic2 API."""

from flask import Blueprint
from controllers import (
    SearchController,
    UserController,
    HistoryController,
    HealthController
)


def create_search_blueprint(gemini_service, spotify_service, save_queue=None):
    """Create and configure search blueprint."""
    bp = Blueprint('search', __name__, url_prefix='/api')
    controller = SearchController(gemini_service, spotify_service, save_queue)

    bp.route('/search', methods=['POST'])(controller.search_music)
    bp.route('/analyze', methods=['POST'])(controller.analyze)
    bp.route('/recommend', methods=['POST'])(controller.recommend)

    return bp


def create_user_blueprint():
    """Create and configure user blueprint."""
    bp = Blueprint('users', __name__, url_prefix='/api/users')
    controller = UserController()

    bp.route('/register', methods=['POST'])(controller.register_user)
    bp.route('/login', methods=['POST'])(controller.login_user)

    return bp


def create_history_blueprint():
    """Create and configure history blueprint."""
    bp = Blueprint('history', __name__, url_prefix='/api')
    controller = HistoryController()

    bp.route('/history/<int:user_id>', methods=['GET'])(controller.get_user_history)

    return bp


def create_health_blueprint(gemini_service=None, spotify_service=None):
    """Create and configure health blueprint."""
    bp = Blueprint('health', __name__)
    controller = HealthController(gemini_service, spotify_service)

    bp.route('/api/health', methods=['GET'])(controller.health_check)
    bp.route('/', methods=['GET'])(controller.root)

    return bp


def register_blueprints(app, gemini_service, spotify_service, save_queue=None):
    """
    Register all blueprints with the Flask app.

    Args:
        app: Flask application instance
        gemini_service: GeminiService instance
        spotify_service: SpotifyService instance
        save_queue: Optional queue for background saves
    """
    app.register_blueprint(create_search_blueprint(gemini_service, spotify_service, save_queue))
    app.register_blueprint(create_user_blueprint())
    app.register_blueprint(create_history_blueprint())
    app.register_blueprint(create_health_blueprint(gemini_service, spotify_service))
