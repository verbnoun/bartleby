import digitalio
import time
from hardware import (
    Multiplexer, KeyboardHandler, RotaryEncoderHandler, 
    PotentiometerHandler
)
from connection import get_precise_time, format_processing_time
from constants import (
    DEBUG, SETUP_DELAY, DETECT_PIN,
    CONTROL_MUX_SIG, CONTROL_MUX_S0, CONTROL_MUX_S1, CONTROL_MUX_S2, CONTROL_MUX_S3,
    OCTAVE_ENC_CLK, OCTAVE_ENC_DT,
    KEYBOARD_L1A_MUX_SIG, KEYBOARD_L1A_MUX_S0, KEYBOARD_L1A_MUX_S1, KEYBOARD_L1A_MUX_S2, KEYBOARD_L1A_MUX_S3,
    KEYBOARD_L1B_MUX_SIG, KEYBOARD_L1B_MUX_S0, KEYBOARD_L1B_MUX_S1, KEYBOARD_L1B_MUX_S2, KEYBOARD_L1B_MUX_S3,
    KEYBOARD_L2_MUX_S0, KEYBOARD_L2_MUX_S1, KEYBOARD_L2_MUX_S2, KEYBOARD_L2_MUX_S3
)
from logging import log, TAG_HW

class HardwareCoordinator:
    def __init__(self):
        log(TAG_HW, "Setting up hardware...")
        # Set up detect pin as output HIGH to signal presence
        self.detect_pin = digitalio.DigitalInOut(DETECT_PIN)
        self.detect_pin.direction = digitalio.Direction.OUTPUT
        self.detect_pin.value = True
        
        # Initialize components
        self.components = self._initialize_components()
        time.sleep(SETUP_DELAY)
        
    def _initialize_components(self):
        control_mux = Multiplexer(
            CONTROL_MUX_SIG,
            CONTROL_MUX_S0,
            CONTROL_MUX_S1,
            CONTROL_MUX_S2,
            CONTROL_MUX_S3
        )
        
        keyboard = self._setup_keyboard()
        encoders = RotaryEncoderHandler(
            OCTAVE_ENC_CLK,
            OCTAVE_ENC_DT
        )
        
        return {
            'control_mux': control_mux,
            'keyboard': keyboard,
            'encoders': encoders,
            'pots': PotentiometerHandler(control_mux)
        }
    
    def _setup_keyboard(self):
        keyboard_l1a = Multiplexer(
            KEYBOARD_L1A_MUX_SIG,
            KEYBOARD_L1A_MUX_S0,
            KEYBOARD_L1A_MUX_S1,
            KEYBOARD_L1A_MUX_S2,
            KEYBOARD_L1A_MUX_S3
        )
        
        keyboard_l1b = Multiplexer(
            KEYBOARD_L1B_MUX_SIG,
            KEYBOARD_L1B_MUX_S0,
            KEYBOARD_L1B_MUX_S1,
            KEYBOARD_L1B_MUX_S2,
            KEYBOARD_L1B_MUX_S3
        )
        
        return KeyboardHandler(
            keyboard_l1a,
            keyboard_l1b,
            KEYBOARD_L2_MUX_S0,
            KEYBOARD_L2_MUX_S1,
            KEYBOARD_L2_MUX_S2,
            KEYBOARD_L2_MUX_S3
        )
    
    def read_hardware_state(self, state_manager):
        changes = {
            'keys': [],
            'pots': [],
            'encoders': []
        }
        
        # Always read keys at full speed
        start_time = get_precise_time()
        changes['keys'] = self.components['keyboard'].read_keys()
        if DEBUG:
            if changes['keys']:
                log(TAG_HW, format_processing_time(start_time, "Key state read"))
        
        # Read pots at interval
        if state_manager.should_scan_pots():
            start_time = get_precise_time()
            changes['pots'] = self.components['pots'].read_pots()
            if DEBUG:
                if changes['pots']:
                    log(TAG_HW, format_processing_time(start_time, "Potentiometer scan"))
            state_manager.update_pot_scan_time()
        
        # Read encoders at interval
        if state_manager.should_scan_encoders():
            start_time = get_precise_time()
            for i in range(self.components['encoders'].num_encoders):
                new_events = self.components['encoders'].read_encoder(i)
                if new_events:
                    changes['encoders'].extend(new_events)
            if changes['encoders']:
                log(TAG_HW, format_processing_time(start_time, "Encoder scan"))
            state_manager.update_encoder_scan_time()
            
        return changes
    
    def handle_encoder_events(self, encoder_events, midi):
        start_time = get_precise_time()
        for event in encoder_events:
            if event[0] == 'rotation':
                _, direction = event[1:3]
                midi.handle_octave_shift(direction)
                if DEBUG:
                    log(TAG_HW, f"Octave shifted {direction}: new position {self.components['encoders'].get_encoder_position(0)}")
                    log(TAG_HW, format_processing_time(start_time, "Octave shift processing"))
    
    def reset_encoders(self):
        self.components['encoders'].reset_all_encoder_positions()
