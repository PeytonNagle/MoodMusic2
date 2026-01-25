"""Base controller class with common functionality."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BaseController:
    """Base controller with shared utilities."""

    def __init__(self):
        """Initialize base controller."""
        self.logger = logger
