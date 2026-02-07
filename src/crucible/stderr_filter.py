"""
Stderr filter to suppress harmless RuntimeError warnings.

The async httpx clients sometimes throw 'Event loop is closed' errors
during cleanup after all work is complete. These are cosmetic and harmless.
"""

import sys


class StderrFilter:
    """Filter to suppress RuntimeError event loop warnings from stderr."""
    
    def __init__(self, original_stderr):
        self._stderr = original_stderr
        self._suppressing_lines = 0
        self._in_runtime_error = False
    
    def write(self, message):
        # Detect start of RuntimeError traceback
        if "RuntimeError: Event loop is closed" in message:
            self._in_runtime_error = True
            self._suppressing_lines = 50  # Suppress next N lines
            return
        
        # Suppress lines that are part of the traceback
        if self._suppressing_lines > 0:
            # Check if this looks like part of traceback
            if any(pattern in message for pattern in [
                "Traceback",
                "File \"",
                "asyncio/",
                "_check_closed",
                "call_soon",
                "selector_events",
                "base_events",
                "Event loop is closed",
                "raise RuntimeError"
            ]):
                self._suppressing_lines -= 1
                return
            else:
                # Not part of traceback anymore, stop suppressing
                self._suppressing_lines = 0
                self._in_runtime_error = False
        
        # Write non-suppressed messages
        self._stderr.write(message)
    
    def flush(self):
        self._stderr.flush()
    
    def isatty(self):
        return self._stderr.isatty()
    
    def fileno(self):
        return self._stderr.fileno()
    
    def __getattr__(self, name):
        # Delegate other methods to original stderr
        return getattr(self._stderr, name)


def install_stderr_filter():
    """Install the stderr filter to suppress RuntimeError warnings."""
    if not isinstance(sys.stderr, StderrFilter):
        sys.stderr = StderrFilter(sys.stderr)
