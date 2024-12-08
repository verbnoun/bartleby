"""Centralized logging system for Bartleby synthesizer."""

import sys

# ANSI Colors - Using bright variants for dark mode visibility
COLOR_WHITE = '\033[97m'        # Bright White
COLOR_PEACH = '\033[38;5;217m'  # Bright Peach
COLOR_YELLOW = '\033[93m'       # Bright Yellow
COLOR_LIME = '\033[92m'         # Bright Lime
COLOR_AQUA = '\033[96m'         # Bright Aqua
COLOR_SKY = '\033[38;5;117m'    # Bright Sky Blue
COLOR_LAVENDER = '\033[38;5;183m' # Bright Lavender
COLOR_PINK = '\033[38;5;218m'   # Bright Pink
COLOR_CORAL = '\033[38;5;210m'  # Bright Coral
COLOR_MINT = '\033[38;5;121m'   # Bright Mint
COLOR_PERIWINKLE = '\033[38;5;147m' # Bright Periwinkle
COLOR_MAUVE = '\033[38;5;182m'  # Bright Mauve
COLOR_TURQUOISE = '\033[38;5;80m' # Bright Turquoise
COLOR_GOLD = '\033[38;5;220m'   # Bright Gold
COLOR_SALMON = '\033[38;5;209m'  # Bright Salmon
COLOR_VIOLET = '\033[38;5;141m'  # Bright Violet
COLOR_TEAL = '\033[38;5;86m'    # Bright Teal
COLOR_ROSE = '\033[38;5;211m'   # Bright Rose
COLOR_AZURE = '\033[38;5;123m'  # Bright Azure
COLOR_SAGE = '\033[38;5;151m'   # Bright Sage

# Special effect colors
COLOR_CYAN = '\033[96m'         # Bright Cyan
COLOR_BLUE = '\033[94m'         # Bright Blue
COLOR_MAGENTA = '\033[95m'      # Bright Magenta
COLOR_GREEN = '\033[92m'        # Bright Green

# Control codes
COLOR_ERROR = '\033[30;41m'     # Black text on red background for errors
COLOR_RESET = '\033[0m'

# Module Tags (8 chars) - Alphabetically ordered
TAG_BARTLEBY = 'BARTLEBY'  # code.py
TAG_CONFIG = 'CONFIG  '    # config.py
TAG_CONNECT = 'CONNECT '   # connection.py
TAG_CONTROL = 'CONTROL '   # controls.py
TAG_COORD = 'COORD   '     # coordinator.py
TAG_ENCODER = 'ENCODER '   # encoder.py
TAG_HARDWAR = 'HARDWAR'    # hardware.py
TAG_HW = 'HW      '     # Hardware operations
TAG_KEYBD = 'KEYBD   '     # keyboard.py
TAG_KEYSTAT = 'KEYSTAT '   # keystates.py
TAG_MAIN = 'MAIN    '    # Main program flow
TAG_MESSAGE = 'MESSAGE '   # messages.py
TAG_MIDI = 'MIDI    '     # midi.py
TAG_MUX = 'MUX     '     # mux.py
TAG_NOTES = 'NOTES   '    # notes.py
TAG_POTS = 'POTS    '    # pots.py
TAG_PRESSUR = 'PRESSUR '   # pressure.py
TAG_STATE = 'STATE   '    # state.py
TAG_TRANS = 'TRANS   '    # transport.py
TAG_ZONES = 'ZONES   '    # zones.py

# Map tags to colors - Each file has a unique color
TAG_COLORS = {
    TAG_BARTLEBY: COLOR_WHITE,      # code.py - White
    TAG_CONFIG: COLOR_PEACH,        # config.py - Peach
    TAG_CONNECT: COLOR_YELLOW,      # connection.py - Yellow
    TAG_CONTROL: COLOR_SAGE,        # controls.py - Sage
    TAG_COORD: COLOR_AQUA,          # coordinator.py - Aqua
    TAG_ENCODER: COLOR_SKY,         # encoder.py - Sky Blue
    TAG_HARDWAR: COLOR_LAVENDER,    # hardware.py - Lavender
    TAG_HW: COLOR_GOLD,             # Hardware ops - Gold
    TAG_KEYBD: COLOR_PINK,          # keyboard.py - Pink
    TAG_KEYSTAT: COLOR_CORAL,       # keystates.py - Coral
    TAG_MAIN: COLOR_AZURE,          # Main flow - Azure
    TAG_MESSAGE: COLOR_MINT,        # messages.py - Mint
    TAG_MIDI: COLOR_PERIWINKLE,     # midi.py - Periwinkle
    TAG_MUX: COLOR_MAUVE,           # mux.py - Mauve
    TAG_NOTES: COLOR_TURQUOISE,     # notes.py - Turquoise
    TAG_POTS: COLOR_SALMON,         # pots.py - Salmon
    TAG_PRESSUR: COLOR_VIOLET,      # pressure.py - Violet
    TAG_STATE: COLOR_TEAL,          # state.py - Teal
    TAG_TRANS: COLOR_ROSE,          # transport.py - Rose
    TAG_ZONES: COLOR_LIME           # zones.py - Lime
}

# Enable flags for each module's logging - Alphabetically ordered
LOG_ENABLE = {
    TAG_BARTLEBY: True,
    TAG_CONFIG: True,
    TAG_CONNECT: True,
    TAG_CONTROL: True,
    TAG_COORD: True,
    TAG_ENCODER: True,
    TAG_HARDWAR: True,
    TAG_HW: True,
    TAG_KEYBD: True,
    TAG_KEYSTAT: True,
    TAG_MAIN: True,
    TAG_MESSAGE: True,
    TAG_MIDI: True,
    TAG_MUX: True,
    TAG_NOTES: True,
    TAG_POTS: True,
    TAG_PRESSUR: True,
    TAG_STATE: True,
    TAG_TRANS: True,
    TAG_ZONES: True
}

# Special debug flags
HEARTBEAT_DEBUG = False

def log(tag, message, is_error=False, is_heartbeat=False):
    """
    Log a message with the specified tag and optional error status.
    
    Args:
        tag: Module tag (must be 8 chars, spaces ok)
        message: Message to log
        is_error: Whether this is an error message
        is_heartbeat: Whether this is a heartbeat message (special case)
    """
    # Skip heartbeat messages unless HEARTBEAT_DEBUG is True
    if is_heartbeat and not HEARTBEAT_DEBUG:
        return
        
    # Check if logging is enabled for this tag
    if not LOG_ENABLE.get(tag, True):
        return
        
    if len(tag) != 8:
        raise ValueError(f"Tag must be exactly 8 characters (spaces ok), got '{tag}' ({len(tag)})")
        
    # Get module's color or default to white
    color = TAG_COLORS.get(tag, COLOR_WHITE)
    
    # Format the message
    if is_error:
        print(f"{COLOR_ERROR}[{tag}] [ERROR] {message}{COLOR_RESET}", file=sys.stderr)
    else:
        print(f"{color}[{tag}] {message}{COLOR_RESET}", file=sys.stderr)

# Example usage:
# from logging import log, TAG_BARTLEBY
# log(TAG_BARTLEBY, 'Starting system')
# log(TAG_BARTLEBY, 'Failed to initialize', is_error=True)
# log(TAG_CONNECT, '♡', is_heartbeat=True)  # Only logs if HEARTBEAT_DEBUG is True
