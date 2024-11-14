import board
import busio
import usb_midi
import digitalio
import time
from hardware import (
    Multiplexer, KeyboardHandler, RotaryEncoderHandler, 
    PotentiometerHandler, Constants as HWConstants
)
from midi import MidiLogic

class Constants:
    # Debug Settings
    DEBUG = True
    SEE_HEARTBEAT = True
    
    # Hardware Setup
    SETUP_DELAY = 0.1
    
    # UART/MIDI Pins
    UART_TX = board.GP16
    UART_RX = board.GP17
    
    # Connection
    DETECT_PIN = board.GP22
    CONNECTION_TIMEOUT = 2.0
    
    # Timing Intervals
    POT_SCAN_INTERVAL = 0.02
    ENCODER_SCAN_INTERVAL = 0.001
    MAIN_LOOP_INTERVAL = 0.001

    # Message Types
    MSG_HELLO = "hello"
    MSG_CONFIG = "cc:"
    MSG_HEARTBEAT = "♡"

    # Timing Constants
    CONFIG_REQUEST_TIMEOUT = 1.0
    CONNECTION_TIMEOUT = 1.0
    
    # UART Settings
    UART_BAUDRATE = 31250
    UART_TIMEOUT = 0.001

class TransportManager:
    """Manages shared UART instance for both text and MIDI communication"""
    def __init__(self, tx_pin, rx_pin, baudrate=31250, timeout=0.001):
        print("Initializing shared transport...")
        self.uart = busio.UART(
            tx=tx_pin,
            rx=rx_pin,
            baudrate=baudrate,
            timeout=timeout,
            bits=8,
            parity=None,
            stop=1
        )
        
        # Initialize USB MIDI port
        try:
            self.usb_midi = usb_midi.ports[1]
            print("USB MIDI initialized")
        except Exception as e:
            print(f"USB MIDI initialization error: {str(e)}")
            self.usb_midi = None
            
        print("Transport initialized")
        
    def get_uart(self):
        """Get the UART instance for text or MIDI use"""
        return self.uart
        
    def get_usb_midi(self):
        """Get the USB MIDI port"""
        return self.usb_midi
        
    def cleanup(self):
        """Clean shutdown of transport"""
        if self.uart:
            self.uart.deinit()

class TextUart:
    """Handles text-based UART communication, separate from MIDI"""
    def __init__(self, uart):
        self.uart = uart
        print("Text protocol initialized")

    def write(self, message):
        """Write text message, converting to bytes if needed"""
        if isinstance(message, str):
            message = message.encode('utf-8')
        return self.uart.write(message)

    def read(self, size=None):
        """Read available data"""
        if size is None and self.uart.in_waiting:
            size = self.uart.in_waiting
        if size:
            return self.uart.read(size)
        return None

    @property
    def in_waiting(self):
        """Number of bytes waiting to be read"""
        return self.uart.in_waiting

class StateManager:
    def __init__(self):
        self.current_time = 0
        self.last_pot_scan = 0
        self.last_encoder_scan = 0
        
    def update_time(self):
        self.current_time = time.monotonic()
        
    def should_scan_pots(self):
        return self.current_time - self.last_pot_scan >= Constants.POT_SCAN_INTERVAL
        
    def should_scan_encoders(self):
        return self.current_time - self.last_encoder_scan >= Constants.ENCODER_SCAN_INTERVAL
        
    def update_pot_scan_time(self):
        self.last_pot_scan = self.current_time
        
    def update_encoder_scan_time(self):
        self.last_encoder_scan = self.current_time

class BartlebyConnectionManager:
    """
    Handles the connection and handshake protocol for Bartleby (Host).
    Uses text UART for communication, separate from MIDI.
    
    State Machine:
    1. STANDALONE -> Always listening for hello
    2. CONFIGURING -> Hello received, requesting/awaiting config
    3. CONNECTED -> Config received, monitoring heartbeats
    """
    STANDALONE = 0
    CONFIGURING = 1
    CONNECTED = 2

    def __init__(self, text_uart, hardware_coordinator, midi_logic):
        # Setup communication
        self.uart = text_uart
        self.hardware = hardware_coordinator
        self.midi = midi_logic  # Only used when we need to send MIDI data
        
        # Initialize state
        self.state = self.STANDALONE
        self.last_message_time = 0
        self.config_received = False
        
        print(f"Bartleby connection manager initialized - listening for Candide")
        
    def update_state(self):
        """Main update loop - check timeouts"""
        if self.state != self.STANDALONE:
            if time.monotonic() - self.last_message_time > Constants.CONNECTION_TIMEOUT:
                print("Connection timeout - returning to listening state")
                self._reset_state()
    
    def handle_message(self, message):
        """Process incoming messages based on current state"""
        if not message:
            return
            
        # Always accept hello in any state - Candide might restart
        if message.startswith("hello"):
            print("---------------")
            print("HANDSHAKE STEP 1: Hello received from Candide")
            print("HANDSHAKE STEP 2: Requesting config and sending current state...")
            print("---------------")
            self.state = self.CONFIGURING
            self._send_current_hw_state()
            self._request_config()
            self.last_message_time = time.monotonic()
            return
            
        # Handle state-specific messages
        if self.state == self.CONFIGURING and message.startswith("cc:"):
            print("---------------")
            print("HANDSHAKE STEP 3: Config received from Candide")
            print("HANDSHAKE STEP 4: Moving to connected state")
            print("---------------")
            self.config_received = True
            self.state = self.CONNECTED
            self._send_welcome()
            self.last_message_time = time.monotonic()
            
        elif self.state == self.CONNECTED:
            if message == "heartbeat":
                self.last_message_time = time.monotonic()
                
    def _send_current_hw_state(self):
        """Send current hardware state as MIDI messages"""
        try:
            # Create a temporary state manager just for this read
            temp_state_manager = StateManager()
            temp_state_manager.update_time()
            
            # Read current hardware state
            state = self.hardware.read_hardware_state(temp_state_manager)
            
            # Send pot values as MIDI CC messages
            if state['pots']:
                # This is where we explicitly use MIDI
                self.midi.update([], state['pots'], {})
                print(f"Sent current pot values via MIDI")
            
            # Send encoder position
            encoder_pos = self.hardware.components['encoders'].get_encoder_position(0)
            print(f"Current octave position: {encoder_pos}")
            
            # Apply any necessary octave shift based on encoder position
            if encoder_pos != 0:
                self.midi.handle_octave_shift(encoder_pos)
            
        except Exception as e:
            print(f"Failed to send current state: {str(e)}")
                
    def _request_config(self):
        """Request configuration from Candide"""
        try:
            if Constants.DEBUG:
                print("DEBUG: Sending config request...")
            self.uart.write("request_config\n")
        except Exception as e:
            print(f"Failed to request config: {str(e)}")
            
    def _send_welcome(self):
        """Send welcome confirmation to Candide"""
        try:
            if Constants.DEBUG:
                print("DEBUG: Sending welcome message...")
            self.uart.write("welcome\n")
        except Exception as e:
            print(f"Failed to send welcome: {str(e)}")
            
    def _reset_state(self):
        """Return to listening state"""
        self.state = self.STANDALONE
        self.config_received = False
        self.last_message_time = 0
        # Clear any pending messages
        while self.uart.in_waiting:
            self.uart.read()

    def cleanup(self):
        """Clean up any resources"""
        self._reset_state()

    def is_connected(self):
        """Check if currently in connected state"""
        return self.state == self.CONNECTED

class HardwareCoordinator:
    def __init__(self):
        print("Setting up hardware...")
        # Set up detect pin as output HIGH to signal presence to Candide
        self.detect_pin = digitalio.DigitalInOut(Constants.DETECT_PIN)  # GP22
        self.detect_pin.direction = digitalio.Direction.OUTPUT
        self.detect_pin.value = True
        
        # Initialize other components
        self.components = self._initialize_components()
        time.sleep(Constants.SETUP_DELAY)
        
    def _initialize_components(self):
        control_mux = Multiplexer(
            HWConstants.CONTROL_MUX_SIG,
            HWConstants.CONTROL_MUX_S0,
            HWConstants.CONTROL_MUX_S1,
            HWConstants.CONTROL_MUX_S2,
            HWConstants.CONTROL_MUX_S3
        )
        
        keyboard = self._setup_keyboard()
        encoders = RotaryEncoderHandler(
            HWConstants.OCTAVE_ENC_CLK,
            HWConstants.OCTAVE_ENC_DT
        )
        
        return {
            'control_mux': control_mux,
            'keyboard': keyboard,
            'encoders': encoders,
            'pots': PotentiometerHandler(control_mux)
        }
    
    def _setup_keyboard(self):
        keyboard_l1a = Multiplexer(
            HWConstants.KEYBOARD_L1A_MUX_SIG,
            HWConstants.KEYBOARD_L1A_MUX_S0,
            HWConstants.KEYBOARD_L1A_MUX_S1,
            HWConstants.KEYBOARD_L1A_MUX_S2,
            HWConstants.KEYBOARD_L1A_MUX_S3
        )
        
        keyboard_l1b = Multiplexer(
            HWConstants.KEYBOARD_L1B_MUX_SIG,
            HWConstants.KEYBOARD_L1B_MUX_S0,
            HWConstants.KEYBOARD_L1B_MUX_S1,
            HWConstants.KEYBOARD_L1B_MUX_S2,
            HWConstants.KEYBOARD_L1B_MUX_S3
        )
        
        return KeyboardHandler(
            keyboard_l1a,
            keyboard_l1b,
            HWConstants.KEYBOARD_L2_MUX_S0,
            HWConstants.KEYBOARD_L2_MUX_S1,
            HWConstants.KEYBOARD_L2_MUX_S2,
            HWConstants.KEYBOARD_L2_MUX_S3
        )
    
    def read_hardware_state(self, state_manager):
        changes = {
            'keys': [],
            'pots': [],
            'encoders': []
        }
        
        # Always read keys at full speed
        changes['keys'] = self.components['keyboard'].read_keys()
        
        # Read pots at interval
        if state_manager.should_scan_pots():
            changes['pots'] = self.components['pots'].read_pots()
            if changes['pots']:
                state_manager.update_pot_scan_time()
        
        # Read encoders at interval
        if state_manager.should_scan_encoders():
            for i in range(self.components['encoders'].num_encoders):
                new_events = self.components['encoders'].read_encoder(i)
                if new_events:
                    changes['encoders'].extend(new_events)
            state_manager.update_encoder_scan_time()
            
        return changes
    
    def handle_encoder_events(self, encoder_events, midi):
        for event in encoder_events:
            if event[0] == 'rotation':
                _, direction = event[1:3]
                midi.handle_octave_shift(direction)
                if Constants.DEBUG:
                    print(f"Octave shifted {direction}: new position {self.components['encoders'].get_encoder_position(0)}")
    
    def reset_encoders(self):
        self.components['encoders'].reset_all_encoder_positions()

class Bartleby:
    def __init__(self):
        print("\nWake Up Bartleby!")
        self.state_manager = StateManager()
        
        # Initialize shared transport first
        self.transport = TransportManager(
            tx_pin=Constants.UART_TX,
            rx_pin=Constants.UART_RX,
            baudrate=Constants.UART_BAUDRATE,
            timeout=Constants.UART_TIMEOUT
        )
        
        # Get shared UART for text and MIDI
        shared_uart = self.transport.get_uart()
        self.text_uart = TextUart(shared_uart)
        self.midi = MidiLogic(
            transport_manager=self.transport,
            midi_callback=self._handle_midi_config
        )
        
        # Rest of initialization
        self.hardware = HardwareCoordinator()
        self.connection_manager = BartlebyConnectionManager(
            self.text_uart, 
            self.hardware,
            self.midi
        )
        self._setup_initial_state()

    def _handle_midi_config(self, message):
        self.connection_manager.handle_message(message)

    def _setup_initial_state(self):
        self.hardware.reset_encoders()
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")

    def update(self):
        try:
            # Update current time
            self.state_manager.update_time()
            
            # Check connection states
            self.connection_manager.update_state()
            
            # Process hardware and MIDI
            changes = self.hardware.read_hardware_state(self.state_manager)
            
            # Check for text messages
            if self.text_uart.in_waiting:
                new_bytes = self.text_uart.read()
                if new_bytes:
                    try:
                        message = new_bytes.decode('utf-8').strip()  # Decode byte sequence to UTF-8 string
                        if message:  # Only process non-empty messages
                            if Constants.DEBUG:
                                if message == Constants.MSG_HEARTBEAT:
                                    if Constants.SEE_HEARTBEAT:
                                        print("♡")
                                else:
                                    print(f"DEBUG: Received message: '{message}'")
                            self.connection_manager.handle_message(message)
                        elif Constants.DEBUG:
                            # Only print empty messages if we're in deep debug
                            print("DEBUG: Received empty UART data")
                    except Exception as e:
                        if str(e):
                            print(f"Received non-text data: {new_bytes.hex()}")

            # Handle encoder events and MIDI updates
            if changes['encoders']:
                self.hardware.handle_encoder_events(changes['encoders'], self.midi)
            
            if any(changes.values()):
                self.midi.update(
                    changes['keys'],
                    changes['pots'],
                    {}  # Empty config since we're not using instrument settings
                )
            
            return True
                
        except KeyboardInterrupt:
            return False
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            return False

    def run(self):
        print("Starting main loop...")
        try:
            while self.update():
                time.sleep(Constants.MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        if self.midi:
            print("Cleaning up MIDI...")
            self.midi.cleanup()
        if self.transport:
            print("Cleaning up transport...")
            self.transport.cleanup()
        if hasattr(self.hardware, 'detect_pin'):
            print("Cleaning up hardware...")
            self.hardware.detect_pin.value = False
            self.hardware.detect_pin.deinit()
        self.connection_manager.cleanup()
        print("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁")

def main():
    controller = Bartleby()
    controller.run()

if __name__ == "__main__":
    main()

def main():
    controller = Bartleby()
    controller.run()

if __name__ == "__main__":
    main()
