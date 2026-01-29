"""User controller handling registration and login endpoints."""

import logging
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg2 import errors
from db_queries import create_user, get_user_by_email
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class UserController(BaseController):
    """Controller for user authentication endpoints."""

    def __init__(self):
        """Initialize user controller."""
        super().__init__()

    def register_user(self):
        """Register a new user with email + password hash."""
        try:
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

            data = request.get_json() or {}
            email = str(data.get('email', '') or '').strip().lower()
            password = data.get('password', '')
            display_name = str(data.get('display_name', '') or '').strip() or None

            if not email or not password:
                return jsonify({'success': False, 'error': 'Email and password are required'}), 400

            password_hash = generate_password_hash(password)
            try:
                user = create_user(email, password_hash, display_name)
            except errors.UniqueViolation:
                return jsonify({'success': False, 'error': 'Email already registered'}), 409

            if user is None:
                return jsonify({
                    'success': False,
                    'error': 'User registration unavailable. Database connection required.',
                    'error_code': 'DATABASE_UNAVAILABLE'
                }), 503

            public_user = {
                'id': user['id'],
                'email': user['email'],
                'display_name': user.get('display_name'),
                'created_at': user.get('created_at')
            }
            return jsonify({'success': True, 'user': public_user}), 201

        except Exception:
            logger.exception("Error registering user")
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    def login_user(self):
        """Simple email/password login check."""
        try:
            if not request.is_json:
                return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

            data = request.get_json() or {}
            email = str(data.get('email', '') or '').strip().lower()
            password = data.get('password', '')

            if not email or not password:
                return jsonify({'success': False, 'error': 'Email and password are required'}), 400

            user = get_user_by_email(email)
            if not user or not check_password_hash(user['password_hash'], password):
                return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

            public_user = {
                'id': user['id'],
                'email': user['email'],
                'display_name': user.get('display_name'),
                'created_at': user.get('created_at')
            }
            return jsonify({'success': True, 'user': public_user}), 200

        except Exception:
            logger.exception("Error logging in user")
            return jsonify({'success': False, 'error': 'Internal server error'}), 500
