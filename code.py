import board
import busio
import digitalio
import time
import usb_midi
from hardware import (
    Multiplexer, KeyboardHandler, RotaryEncoderHandler, 
    PotentiometerHandler, Constants as HWConstants
)
from midi import MidiLogic

class Constants:
    # System Constants
    DEBUG = True

    # Hardware Setup Delay
    SETUP_DELAY = 0.1

    # UART Pins
    MIDI_TX = board.GP16
    UART_RX = board.GP17

    # Detect Pin
    DETECT_PIN = board.GP22

    # Scan Intervals (in seconds)
    POT_SCAN_INTERVAL = 0.02
    ENCODER_SCAN_INTERVAL = 0.001
    MAIN_LOOP_INTERVAL = 0.001
    
    # Connection timeout (in seconds)
    CONNECTION_TIMEOUT = 1.0  # Time without message before considering disconnected

class UartHandler:
    """Handles both MIDI output and text communication over single UART"""
    def __init__(self):
        print(f"Initializing UART on TX={Constants.MIDI_TX}, RX={Constants.UART_RX}")
        try:
            # Initialize single UART for both MIDI and text at MIDI baud rate
            self.uart = busio.UART(tx=Constants.MIDI_TX,
                                rx=Constants.UART_RX,
                                baudrate=31250,  # MIDI baud rate for both
                                bits=8,
                                parity=None,
                                stop=1,
                                timeout=0.001)  # Small timeout for non-blocking reads
            self.buffer = bytearray()
            print("UART initialization successful")
        except Exception as e:
            print(f"UART initialization error: {str(e)}")
            raise

    def send_midi(self, message):
        """Send raw MIDI message bytes"""
        try:
            self.uart.write(bytes(message))
        except Exception as e:
            if str(e):  # Only print if there's an actual error message
                print(f"Error sending MIDI: {str(e)}")

    def check_for_messages(self):
        """Check for and process any incoming messages. Returns True if message received."""
        try:
            if self.uart.in_waiting:
                # Read available bytes
                new_bytes = self.uart.read(self.uart.in_waiting)
                if new_bytes:  # Only process if we actually got data
                    try:
                        message = new_bytes.decode('utf-8')
                        if Constants.DEBUG:
                            print(f"Received message: {message}")
                        return True
                    except Exception as e:
                        # Handle case where received bytes aren't valid UTF-8
                        if str(e):  # Only print if there's an actual error message
                            print(f"Received non-text data: {new_bytes.hex()}")
            return False
        except Exception as e:
            if str(e):  # Only print if there's an actual error message
                print(f"Error reading UART: {str(e)}")
            return False

    def cleanup(self):
        """Clean shutdown"""
        try:
            self.uart.deinit()
            print("UART cleaned up")
        except Exception as e:
            if str(e):  # Only print if there's an actual error message
                print(f"Error during cleanup: {str(e)}")

class UsbMIDI:
    """Handles USB MIDI output"""
    def __init__(self):
        self.midi = usb_midi.ports[1]
        print("USB MIDI initialized")

    def send_message(self, message):
        """Send raw MIDI message bytes"""
        self.midi.write(bytes(message))

class Bartleby:
    def __init__(self):
        print("\nInitializing Bartleby...")
        # System components
        self.hardware = None
        self.midi = None
        self.uart = None
        self.usb_midi = None
        self.detect_pin = None
        self.last_detect_state = True  # Start true since we set pin high
        
        # Connection state
        self.last_candide_message = 0  # Track last message time
        self.candide_connected = False  # Track software connection state
        self.has_greeted = False  # Track if greeting has been played for current connection
        
        # Timing state
        self.current_time = 0
        self.last_pot_scan = 0
        self.last_encoder_scan = 0
        
        # Run setup
        self._setup_hardware()
        self._setup_midi()
        self._setup_uart()
        self._setup_initial_state()
        
    def _setup_hardware(self):
        """Initialize all hardware components"""
        # Setup detect pin as output and set high to signal presence
        self.detect_pin = digitalio.DigitalInOut(Constants.DETECT_PIN)
        self.detect_pin.direction = digitalio.Direction.OUTPUT
        self.detect_pin.value = True
        
        self.hardware = {
            'control_mux': Multiplexer(
                HWConstants.CONTROL_MUX_SIG,
                HWConstants.CONTROL_MUX_S0,
                HWConstants.CONTROL_MUX_S1,
                HWConstants.CONTROL_MUX_S2,
                HWConstants.CONTROL_MUX_S3
            ),
            'keyboard': self._setup_keyboard(),
            'encoders': RotaryEncoderHandler(
                HWConstants.OCTAVE_ENC_CLK,
                HWConstants.OCTAVE_ENC_DT
            )
        }
        
        # Create pot handler after mux is ready
        self.hardware['pots'] = PotentiometerHandler(self.hardware['control_mux'])
        
        # Initialize USB MIDI
        self.usb_midi = UsbMIDI()
        
        time.sleep(Constants.SETUP_DELAY)  # Allow hardware to stabilize

    def _setup_keyboard(self):
        """Initialize keyboard multiplexers and handler"""
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

    def _setup_midi(self):
        """Initialize MIDI"""
        self.midi = MidiLogic()

    def _setup_uart(self):
        """Initialize UART for both MIDI and communication"""
        print("Setting up UART...")
        self.uart = UartHandler()

    def _setup_initial_state(self):
        """Set initial system state"""
        self.hardware['encoders'].reset_all_encoder_positions()
        
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")

    def _play_greeting(self):
        """Play welcome melody"""
        greeting_notes = [60, 64, 67, 72]  # C E G C (ascending)
        velocities = [80, 85, 90, 95]  # Gradually increasing velocity
        durations = [0.2, 0.2, 0.2, 0.4]  # Last note slightly longer

        for note, velocity, duration in zip(greeting_notes, velocities, durations):
            self._send_midi_event(('note_on', note, velocity, 0))
            time.sleep(duration)  # Hold note
            self._send_midi_event(('note_off', note, 0, 0))
            time.sleep(0.05)  # Tiny gap between notes

    def _handle_encoder_events(self, encoder_events):
        """Process encoder state changes"""
        for event in encoder_events:
            if event[0] == 'rotation':
                _, direction = event[1:3]  
                midi_events = self.midi.handle_octave_shift(direction)
                print(f"Octave shifted {direction}: new position {self.hardware['encoders'].get_encoder_position(0)}")
                for event in midi_events:
                    self._send_midi_event(event)

    def _send_midi_event(self, event):
        """Send MIDI event via USB and hardware MIDI"""
        if Constants.DEBUG:
            print(f"Sending MIDI event: {event}")
        event_type, *params = event

        # Convert to MIDI message
        if event_type == 'note_on':
            note, velocity, _ = params
            midi_msg = [0x90, note, velocity]
        elif event_type == 'note_off':
            note, velocity, _ = params
            midi_msg = [0x80, note, velocity]
        elif event_type == 'control_change':
            cc_num, value, _ = params
            midi_msg = [0xB0, cc_num, value]
        else:
            return

        # Send via UART MIDI
        self.uart.send_midi(midi_msg)
        
        # Send via USB MIDI
        self.usb_midi.send_message(midi_msg)
        
        # Also send via USB MIDI through MidiLogic (for compatibility)
        self.midi.send_midi_event(event)

    def process_hardware(self):
        """Read and process all hardware inputs"""
        self.current_time = time.monotonic()
        
        # Check if Candide is still connected
        detect_state = self.detect_pin.value
        
        # Handle new connection
        if detect_state and not self.last_detect_state:
            print("Candide physically connected")
        
        # Handle disconnection
        elif not detect_state and self.last_detect_state:
            print("Candide physically unplugged")
            self.candide_connected = False  # Also mark software connection as down
            self.has_greeted = False  # Reset greeting state
            
        self.last_detect_state = detect_state

        changes = {
            'keys': [],
            'pots': [],
            'encoders': []
        }
        
        # Always read keys at full speed
        changes['keys'] = self.hardware['keyboard'].read_keys()
        
        # Read pots
        if self.current_time - self.last_pot_scan >= Constants.POT_SCAN_INTERVAL:
            changes['pots'] = self.hardware['pots'].read_pots()
            if changes['pots']:
                self.last_pot_scan = self.current_time
        
        # Read encoders at fastest interval
        if self.current_time - self.last_encoder_scan >= Constants.ENCODER_SCAN_INTERVAL:
            for i in range(self.hardware['encoders'].num_encoders):
                new_events = self.hardware['encoders'].read_encoder(i)
                if new_events:
                    changes['encoders'].extend(new_events)
            if changes['encoders']:
                self._handle_encoder_events(changes['encoders'])
            self.last_encoder_scan = self.current_time
            
        return changes

    def update(self):
        """Main update loop - returns False if should stop"""
        try:
            # Process all hardware
            changes = self.process_hardware()
            
            # Check for UART messages and update connection state
            if self.uart.check_for_messages():
                if not self.candide_connected:
                    print("Candide software connection established")
                    self.candide_connected = True
                    self.has_greeted = False  # Reset greeting flag on new connection
                
                if self.candide_connected and not self.has_greeted:
                    self._play_greeting()
                    self.has_greeted = True
                
                self.last_candide_message = time.monotonic()
            
            # Check for connection timeout
            elif (self.candide_connected and 
                  time.monotonic() - self.last_candide_message > Constants.CONNECTION_TIMEOUT):
                print("Candide software connection lost, bye Candide")
                self.candide_connected = False
                self.has_greeted = False  # Reset greeting flag on disconnect
            
            # Process MIDI events if hardware has changed
            if any(changes.values()):
                midi_events = self.midi.update(
                    changes['keys'],
                    changes['pots'],
                    {}  # Empty config since we're not using instrument settings
                )
                
                # Send each MIDI event
                for event in midi_events:
                    self._send_midi_event(event)
            
            return True
            
        except KeyboardInterrupt:
            return False
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            return False

    def run(self):
        """Main run loop"""
        try:
            while self.update():
                time.sleep(Constants.MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean shutdown"""
        if self.uart:
            self.uart.cleanup()
        if self.detect_pin:
            self.detect_pin.deinit()
        print("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁")

def main():
    controller = Bartleby()
    controller.run()

if __name__ == "__main__":
    main()