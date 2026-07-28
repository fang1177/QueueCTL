"""
QueueCTL Shell Command Subprocess Executor Module.

Executes shell commands in isolated subprocesses with timeout enforcement,
output capture, exit code tracking, and resource cleanup.
"""

import subprocess
import time
from typing import Dict, Any, Tuple
from queuectl.utils.logger import get_logger

logger = get_logger("queuectl.executor")


class CommandExecutor:
    """Subprocess executor for background jobs."""

    @staticmethod
    def execute(command: str, timeout_seconds: int = 60) -> Dict[str, Any]:
        """
        Executes a shell command with timeout enforcement.

        Args:
            command: The shell command string to execute.
            timeout_seconds: Maximum time allowed before terminating process.

        Returns:
            Dict containing exit_code, stdout, stderr, execution_duration_ms, error_message.
        """
        start_time = time.perf_counter()
        
        try:
            # Execute command using system shell
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                exit_code = process.returncode
                duration_ms = (time.perf_counter() - start_time) * 1000.0

                return {
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration_ms": duration_ms,
                    "error_message": None if exit_code == 0 else f"Command failed with exit code {exit_code}: {stderr.strip()}",
                }

            except subprocess.TimeoutExpired:
                # Forcefully terminate timed out subprocess
                logger.warning(f"Command timed out after {timeout_seconds}s: '{command}'")
                process.kill()
                stdout, stderr = process.communicate()
                duration_ms = (time.perf_counter() - start_time) * 1000.0

                return {
                    "exit_code": 124,  # Standard POSIX timeout exit code
                    "stdout": stdout,
                    "stderr": stderr,
                    "duration_ms": duration_ms,
                    "error_message": f"Execution timed out after {timeout_seconds} seconds.",
                }

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Failed to launch command process: {e}")
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": duration_ms,
                "error_message": f"Subprocess initialization error: {e}",
            }
