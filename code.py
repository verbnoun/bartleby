import board
import digitalio
import time
from hardware import (
    Multiplexer, KeyboardHandler, RotaryEncoderHandler, 
    PotentiometerHandler, Constants as HWConstants
)
from midi import MidiLogic

class Constants:
    DEBUG = False
    SEE_HEARTBEAT = False

    # Hardware Setup Delay
    SETUP_DELAY = 0.1

    # MIDI Pins
    MIDI_TX = board.GP16
    MIDI_RX = board.GP17

    # Detect Pin
    DETECT_PIN = board.GP22

    # Scan Intervals (in seconds)
    POT_SCAN_INTERVAL = 0.02
    ENCODER_SCAN_INTERVAL = 0.001
    MAIN_LOOP_INTERVAL = 0.001
    
    # Connection timeout (in seconds)
    CONNECTION_TIMEOUT = 1.0  # Time without message before considering disconnected

class Bartleby:
    def __init__(self):
        print("\nWake Up Bartleby!")
        # System components
        self.hardware = None
        self.midi = None
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
        """Initialize MIDI with transport configuration"""
        self.midi = MidiLogic(
            midi_tx=Constants.MIDI_TX,
            midi_rx=Constants.MIDI_RX,
            midi_callback=self._handle_midi_config
        )

    def _handle_midi_config(self, message):
        """Handle MIDI configuration messages from Candide"""
        if self.midi:
            self.midi.handle_config_message(message)

    def _setup_initial_state(self):
        """Set initial system state"""
        self.hardware['encoders'].reset_all_encoder_positions()
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")

    def _handle_candide_disconnect(self):
        """Handle Candide disconnection"""
        print("Candide software connection lost")
        self.candide_connected = False
        self.has_greeted = False
        if self.midi:
            self.midi.reset_cc_defaults()

    def _handle_encoder_events(self, encoder_events):
        """Process encoder state changes"""
        for event in encoder_events:
            if event[0] == 'rotation':
                _, direction = event[1:3]  
                midi_events = self.midi.handle_octave_shift(direction)
                if Constants.DEBUG:
                    print(f"Octave shifted {direction}: new position {self.hardware['encoders'].get_encoder_position(0)}")
                # MIDI events are handled internally by MidiLogic now

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
            
            if self.midi.check_for_messages():
                if not self.candide_connected:
                    print("Candide software connection established")
                    self.candide_connected = True
                self.last_candide_message = time.monotonic()
            
            # Check for connection timeout
            elif (self.candide_connected and 
                  time.monotonic() - self.last_candide_message > Constants.CONNECTION_TIMEOUT):
                self._handle_candide_disconnect()
            
            # Process MIDI events if hardware has changed
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
        """Main run loop"""
        try:
            while self.update():
                time.sleep(Constants.MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean shutdown"""
        if self.midi:
            self.midi.cleanup()
        if self.detect_pin:
            self.detect_pin.deinit()
        print("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁")

def main():
    controller = Bartleby()
    controller.run()

if __name__ == "__main__":
    main()