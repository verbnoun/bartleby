"""Centralized logging system for Bartleby synthesizer."""

import sys

# ANSI Colors - Using bright variants for visibility
COLOR_WHITE = '\033[97m'        # Bright White for main
COLOR_CYAN = '\033[96m'         # Bright Cyan for hardware
COLOR_GREEN = '\033[92m'        # Bright Green for MIDI
COLOR_YELLOW = '\033[93m'       # Bright Yellow for transport
COLOR_BLUE = '\033[94m'         # Bright Blue for connection
COLOR_MAGENTA = '\033[95m'      # Bright Magenta for state
COLOR_ERROR = '\033[30;41m'     # Black text on red background for errors
COLOR_RESET = '\033[0m'

# Module Tags (7 chars)
TAG_MAIN = 'MAIN   '    # Main program flow
TAG_HW = 'HW     '    # Hardware operations
TAG_MIDI = 'MIDI   '    # MIDI operations
TAG_TRANS = 'TRANS  '    # Transport operations
TAG_CONN = 'CONN   '    # Connection operations
TAG_STATE = 'STATE  '    # State management

# Map tags to colors
TAG_COLORS = {
    TAG_MAIN: COLOR_WHITE,
    TAG_HW: COLOR_CYAN,
    TAG_MIDI: COLOR_GREEN,
    TAG_TRANS: COLOR_YELLOW,
    TAG_CONN: COLOR_BLUE,
    TAG_STATE: COLOR_MAGENTA,
}

# Enable flags for each module's logging
LOG_ENABLE = {
    TAG_MAIN: True,
    TAG_HW: True,
    TAG_MIDI: True,
    TAG_TRANS: True,
    TAG_CONN: True,
    TAG_STATE: True,
}

# Special debug flags
HEARTBEAT_DEBUG = False

def log(tag, message, is_error=False, is_heartbeat=False):
    """
    Log a message with the specified tag and optional error status.
    
    Args:
        tag: Module tag (must be 7 chars, spaces ok)
        message: Message to log
        is_error: Whether this is an error message
        is_heartbeat: Whether this is a heartbeat message
    """
    # Skip heartbeat messages unless HEARTBEAT_DEBUG is True
    if is_heartbeat and not HEARTBEAT_DEBUG:
        return
        
    # Check if logging is enabled for this tag
    if not LOG_ENABLE.get(tag, True):
        return
        
    if len(tag) != 7:
        raise ValueError(f"Tag must be exactly 7 characters (spaces ok), got '{tag}' ({len(tag)})")
        
    # Get module's color or default to white
    color = TAG_COLORS.get(tag, COLOR_WHITE)
    
    # Format the message
    if is_error:
        print(f"{COLOR_ERROR}[{tag}] [ERROR] {message}{COLOR_RESET}", file=sys.stderr)
    else:
        print(f"{color}[{tag}] {message}{COLOR_RESET}", file=sys.stderr)

# Example usage:
# from logging import log, TAG_MAIN
# log(TAG_MAIN, 'Starting system')
# log(TAG_MAIN, 'Failed to initialize', is_error=True)
# log(TAG_CONN, '♡', is_heartbeat=True)  # Only logs if HEARTBEAT_DEBUG is True
