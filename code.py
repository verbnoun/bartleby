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
    SETUP_DELAY = 0.1
    MIDI_TX = board.GP16
    MIDI_RX = board.GP17
    DETECT_PIN = board.GP22
    POT_SCAN_INTERVAL = 0.02
    ENCODER_SCAN_INTERVAL = 0.001
    MAIN_LOOP_INTERVAL = 0.001
    CONNECTION_TIMEOUT = 1.0

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

class ConnectionManager:
    def __init__(self, detect_pin):
        self.detect_pin = digitalio.DigitalInOut(detect_pin)
        self.detect_pin.direction = digitalio.Direction.OUTPUT
        self.detect_pin.value = True
        self.last_detect_state = True
        self.last_candide_message = 0
        self.candide_connected = False
        self.has_greeted = False
        
    def update_connection_state(self):
        detect_state = self.detect_pin.value
        connection_changed = False
        
        if detect_state and not self.last_detect_state:
            print("Candide physically connected")
            connection_changed = True
        elif not detect_state and self.last_detect_state:
            print("Candide physically unplugged")
            self.candide_connected = False
            self.has_greeted = False
            connection_changed = True
            
        self.last_detect_state = detect_state
        return connection_changed
    
    def handle_message_received(self):
        if not self.candide_connected:
            print("Candide software connection established")
            self.candide_connected = True
        self.last_candide_message = time.monotonic()
    
    def check_connection_timeout(self):
        if (self.candide_connected and 
            time.monotonic() - self.last_candide_message > Constants.CONNECTION_TIMEOUT):
            print("Candide software connection lost")
            self.candide_connected = False
            self.has_greeted = False
            return True
        return False
    
    def cleanup(self):
        if self.detect_pin:
            self.detect_pin.deinit()

class HardwareCoordinator:
    def __init__(self):
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
        self.connection_manager = ConnectionManager(Constants.DETECT_PIN)
        self.hardware = HardwareCoordinator()
        self.midi = self._setup_midi()
        self._setup_initial_state()
        
    def _setup_midi(self):
        return MidiLogic(
            midi_tx=Constants.MIDI_TX,
            midi_rx=Constants.MIDI_RX,
            midi_callback=self._handle_midi_config
        )

    def _handle_midi_config(self, message):
        if self.midi:
            self.midi.handle_config_message(message)

    def _setup_initial_state(self):
        self.hardware.reset_encoders()
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")

    def update(self):
        try:
            # Update current time
            self.state_manager.update_time()
            
            # Check connection states
            self.connection_manager.update_connection_state()
            
            # Process hardware and MIDI
            changes = self.hardware.read_hardware_state(self.state_manager)
            
            if self.midi.check_for_messages():
                self.connection_manager.handle_message_received()
            elif self.connection_manager.check_connection_timeout():
                if self.midi:
                    self.midi.reset_cc_defaults()
            
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
        try:
            while self.update():
                time.sleep(Constants.MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        if self.midi:
            self.midi.cleanup()
        self.connection_manager.cleanup()
        print("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁")

def main():
    controller = Bartleby()
    controller.run()

if __name__ == "__main__":
    main()
