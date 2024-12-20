"""Constants for Bartleby synthesizer."""

import board

# Hardware Setup
SETUP_DELAY = 0.1

# I2C Display Setup
I2C_SDA = board.GP18
I2C_SCL = board.GP19
I2C_MUX_ADDRESS = 0x70  # TCA9548A default address
OLED_ADDRESS = 0x3C    # SSD1306 default address
OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_CHANNELS = [0, 1, 2, 3, 4]  # Using first 5 channels of TCA9548A

# UART/MIDI Pins
UART_TX = board.GP16
UART_RX = board.GP17

# Timing Intervals
POT_SCAN_INTERVAL = 0.02
ENCODER_SCAN_INTERVAL = 0.001
MAIN_LOOP_INTERVAL = 0.001
MESSAGE_TIMEOUT = 0.5  # Increased from 0.05s to 0.5s for more reliable message assembly

# MIDI Settings
UART_BAUDRATE = 31250
UART_TIMEOUT = 0.005  # Increased from 0.001s to 0.005s for more complete reads

# MIDI Control Constants
CC_TIMBRE = 74
TIMBRE_CENTER = 64

# Connection Constants
DETECT_PIN = board.GP22
COMMUNICATION_TIMEOUT = 5.0  # Time without any message before disconnect
STARTUP_DELAY = 1.0  # Give devices time to initialize
BUFFER_CLEAR_TIMEOUT = 0.2  # Increased from 0.1s to 0.2s for complete buffer clearing
VALID_CARTRIDGES = ["Candide", "Don Quixote"]  # List of known cartridge names

# ADC Constants
ADC_MAX = 65535
ADC_MIN = 1

# Pin Definitions
KEYBOARD_L1A_MUX_SIG = board.GP26
KEYBOARD_L1A_MUX_S0 = board.GP0
KEYBOARD_L1A_MUX_S1 = board.GP1
KEYBOARD_L1A_MUX_S2 = board.GP2
KEYBOARD_L1A_MUX_S3 = board.GP3

KEYBOARD_L1B_MUX_SIG = board.GP27
KEYBOARD_L1B_MUX_S0 = board.GP4
KEYBOARD_L1B_MUX_S1 = board.GP5
KEYBOARD_L1B_MUX_S2 = board.GP6
KEYBOARD_L1B_MUX_S3 = board.GP7

KEYBOARD_L2_MUX_S0 = board.GP8
KEYBOARD_L2_MUX_S1 = board.GP9
KEYBOARD_L2_MUX_S2 = board.GP10
KEYBOARD_L2_MUX_S3 = board.GP11

CONTROL_MUX_SIG = board.GP28
CONTROL_MUX_S0 = board.GP12
CONTROL_MUX_S1 = board.GP13
CONTROL_MUX_S2 = board.GP14
CONTROL_MUX_S3 = board.GP15

OCTAVE_ENC_CLK = board.GP20
OCTAVE_ENC_DT = board.GP21

# Potentiometer Constants
POT_THRESHOLD = 1500  # Threshold for initial pot activation
POT_CHANGE_THRESHOLD = 400  # Threshold for subsequent changes when pot is active
POT_LOWER_TRIM = 0.05
POT_UPPER_TRIM = 0.0
POT_LOG_THRESHOLD = 0.01  # Threshold for logging pot changes
NUM_POTS = 16

# Keyboard Constants
NUM_KEYS = 25
NUM_CHANNELS = 50

# Sensor Constants
MAX_VK_RESISTANCE = 25000
MIN_VK_RESISTANCE = 1100
INITIAL_ACTIVATION_THRESHOLD = 0  # Removed threshold - note-on will fire with any detectable pressure
DEACTIVATION_THRESHOLD = 0.000015
REST_VOLTAGE_THRESHOLD = 3.3
ADC_RESISTANCE_SCALE = 100000

# MIDI Curve Constants
PRESSURE_CURVE = 0.3  # 0.0 = linear, 1.0 = extreme middle expansion
BEND_CURVE = 0      # 0.0 = linear, 1.0 = extreme middle stability

# MIDI Velocity Settings
VELOCITY_DELAY = 0
PRESSURE_HISTORY_SIZE = 8  # Increased from 3 to 8 for better release velocity calculation
RELEASE_VELOCITY_THRESHOLD = 0.01
RELEASE_VELOCITY_SCALE = 0.5

# MPE Configuration
ZONE_MANAGER = 0
ZONE_START = 1
ZONE_END = 15

# MIDI CC Numbers - Standard Controls
CC_MODULATION = 1
CC_VOLUME = 7
CC_FILTER_RESONANCE = 71
CC_RELEASE_TIME = 72
CC_ATTACK_TIME = 73
CC_DECAY_TIME = 75
CC_SUSTAIN_LEVEL = 76

# MIDI RPN Messages
RPN_MSB = 0
RPN_LSB_MPE = 6
RPN_LSB_PITCH = 0

# MIDI Pitch Bend
PITCH_BEND_CENTER = 8192
PITCH_BEND_MAX = 16383

# Note Management
MAX_ACTIVE_NOTES = 15

# MPE Settings
MPE_MEMBER_PITCH_BEND_RANGE = 48
MPE_MASTER_PITCH_BEND_RANGE = 2

# Default CC Assignments
DEFAULT_CC_ASSIGNMENTS = {
    0: CC_TIMBRE,
    1: CC_FILTER_RESONANCE,
    2: CC_ATTACK_TIME,
    3: CC_DECAY_TIME,
    4: CC_SUSTAIN_LEVEL,
    5: CC_RELEASE_TIME,
    6: CC_VOLUME,
    7: CC_MODULATION,
    8: 20,
    9: 21,
    10: 22,
    11: 23,
    12: 24,
    13: 25,
}
