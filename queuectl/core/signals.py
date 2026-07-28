"""
QueueCTL Signal Management Module.

Provides process signal handling for graceful shutdown.
"""

import signal
import sys
from typing import Callable, Optional
from queuectl.utils.logger import get_logger

logger = get_logger("queuectl.signals")


class SignalHandler:
    """Manages SIGINT/SIGTERM signals for graceful process termination."""

    def __init__(self):
        self.shutdown_requested = False
        self._custom_callback: Optional[Callable[[], None]] = None

    def register_signals(self, on_shutdown_callback: Optional[Callable[[], None]] = None):
        """Registers handlers for SIGINT and SIGTERM."""
        self._custom_callback = on_shutdown_callback
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, frame):
        sig_name = signal.Signals(signum).name
        logger.info(f"Received signal {sig_name} ({signum}). Initiating graceful shutdown...")
        self.shutdown_requested = True
        if self._custom_callback:
            self._custom_callback()
