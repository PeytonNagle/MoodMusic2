"""Blueprint registration for MoodMusic2 API."""

from flask import Blueprint
from controllers import (
    SearchController,
    UserController,
    HistoryController,
    HealthController
)
from services.auth import require_auth


def _apply(limiter, rule):
    """Return a no-op decorator if limiter is None, else limiter.limit(rule)."""
    if limiter is None:
        return lambda fn: fn
    return limiter.limit(rule)


def create_search_blueprint(mood_service, music_service, save_queue=None, limiter=None):
    """Create and configure search blueprint."""
    bp = Blueprint('search', __name__, url_prefix='/api')
    controller = SearchController(mood_service, music_service, save_queue)

    bp.route('/search', methods=['POST'])(_apply(limiter, "10/minute;100/day")(controller.search_music))
    bp.route('/analyze', methods=['POST'])(_apply(limiter, "20/minute;200/day")(controller.analyze))
    bp.route('/recommend', methods=['POST'])(_apply(limiter, "10/minute;100/day")(controller.recommend))

    return bp


def create_user_blueprint(limiter=None):
    """Create and configure user blueprint."""
    bp = Blueprint('users', __name__, url_prefix='/api/users')
    controller = UserController()

    auth_limit = _apply(limiter, "5/minute;30/day")
    bp.route('/register', methods=['POST'])(auth_limit(controller.register_user))
    bp.route('/login', methods=['POST'])(auth_limit(controller.login_user))

    return bp


def create_history_blueprint(limiter=None):
    """Create and configure history blueprint."""
    bp = Blueprint('history', __name__, url_prefix='/api')
    controller = HistoryController()

    handler = require_auth(controller.get_user_history)
    handler = _apply(limiter, "30/minute")(handler)
    bp.route('/history/<int:user_id>', methods=['GET'])(handler)

    return bp


def create_health_blueprint(mood_service=None, music_service=None, limiter=None):
    """Create and configure health blueprint."""
    bp = Blueprint('health', __name__)
    controller = HealthController(mood_service, music_service)

    # Health checks are exempt from rate limits.
    health = controller.health_check
    root = controller.root
    if limiter is not None:
        health = limiter.exempt(health)
        root = limiter.exempt(root)

    bp.route('/api/health', methods=['GET'])(health)
    bp.route('/', methods=['GET'])(root)

    return bp


def register_blueprints(app, mood_service, music_service, save_queue=None, limiter=None):
    """
    Register all blueprints with the Flask app.

    Args:
        app: Flask application instance
        mood_service: AI mood service instance (BaseMoodService)
        music_service: Music enrichment provider (BaseMusicService)
        save_queue: Optional queue for background saves
        limiter: Optional Flask-Limiter instance for per-route rate limits
    """
    app.register_blueprint(create_search_blueprint(mood_service, music_service, save_queue, limiter))
    app.register_blueprint(create_user_blueprint(limiter))
    app.register_blueprint(create_history_blueprint(limiter))
    app.register_blueprint(create_health_blueprint(mood_service, music_service, limiter))
