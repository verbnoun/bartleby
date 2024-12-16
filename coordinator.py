"""Hardware coordination and management for Bartleby."""

import digitalio
import time
from hardware import (
    Multiplexer, KeyboardHandler, RotaryEncoderHandler, 
    PotentiometerHandler
)
from constants import (
    SETUP_DELAY, DETECT_PIN,
    CONTROL_MUX_SIG, CONTROL_MUX_S0, CONTROL_MUX_S1, CONTROL_MUX_S2, CONTROL_MUX_S3,
    OCTAVE_ENC_CLK, OCTAVE_ENC_DT,
    KEYBOARD_L1A_MUX_SIG, KEYBOARD_L1A_MUX_S0, KEYBOARD_L1A_MUX_S1, KEYBOARD_L1A_MUX_S2, KEYBOARD_L1A_MUX_S3,
    KEYBOARD_L1B_MUX_SIG, KEYBOARD_L1B_MUX_S0, KEYBOARD_L1B_MUX_S1, KEYBOARD_L1B_MUX_S2, KEYBOARD_L1B_MUX_S3,
    KEYBOARD_L2_MUX_S0, KEYBOARD_L2_MUX_S1, KEYBOARD_L2_MUX_S2, KEYBOARD_L2_MUX_S3
)
from logging import log, TAG_HW

class HardwareCoordinator:
    def __init__(self):
        log(TAG_HW, "Initializing hardware coordinator")
        try:
            # Initialize components
            self.components = self._initialize_components()
            time.sleep(SETUP_DELAY)
            log(TAG_HW, "Hardware initialization complete")
        except Exception as e:
            log(TAG_HW, f"Hardware initialization failed: {str(e)}", is_error=True)
            raise
        
    def _initialize_components(self):
        try:
            log(TAG_HW, "Initializing control multiplexer")
            control_mux = Multiplexer(
                CONTROL_MUX_SIG,
                CONTROL_MUX_S0,
                CONTROL_MUX_S1,
                CONTROL_MUX_S2,
                CONTROL_MUX_S3
            )
            
            log(TAG_HW, "Setting up keyboard")
            keyboard = self._setup_keyboard()
            
            log(TAG_HW, "Initializing encoders")
            encoders = RotaryEncoderHandler(
                OCTAVE_ENC_CLK,
                OCTAVE_ENC_DT
            )
            
            log(TAG_HW, "Initializing potentiometers")
            pots = PotentiometerHandler(control_mux)
            
            return {
                'control_mux': control_mux,
                'keyboard': keyboard,
                'encoders': encoders,
                'pots': pots
            }
        except Exception as e:
            log(TAG_HW, f"Component initialization failed: {str(e)}", is_error=True)
            raise
    
    def _setup_keyboard(self):
        try:
            log(TAG_HW, "Initializing keyboard layer 1A multiplexer")
            keyboard_l1a = Multiplexer(
                KEYBOARD_L1A_MUX_SIG,
                KEYBOARD_L1A_MUX_S0,
                KEYBOARD_L1A_MUX_S1,
                KEYBOARD_L1A_MUX_S2,
                KEYBOARD_L1A_MUX_S3
            )
            
            log(TAG_HW, "Initializing keyboard layer 1B multiplexer")
            keyboard_l1b = Multiplexer(
                KEYBOARD_L1B_MUX_SIG,
                KEYBOARD_L1B_MUX_S0,
                KEYBOARD_L1B_MUX_S1,
                KEYBOARD_L1B_MUX_S2,
                KEYBOARD_L1B_MUX_S3
            )
            
            log(TAG_HW, "Creating keyboard handler")
            return KeyboardHandler(
                keyboard_l1a,
                keyboard_l1b,
                KEYBOARD_L2_MUX_S0,
                KEYBOARD_L2_MUX_S1,
                KEYBOARD_L2_MUX_S2,
                KEYBOARD_L2_MUX_S3
            )
        except Exception as e:
            log(TAG_HW, f"Keyboard setup failed: {str(e)}", is_error=True)
            raise
    
    def read_hardware_state(self, state_manager):
        changes = {
            'keys': [],
            'pots': [],
            'encoders': []
        }
        
        try:
            # Always read keys at full speed
            changes['keys'] = self.components['keyboard'].read_keys()
            if changes['keys']:
                log(TAG_HW, f"Keys changed: {len(changes['keys'])} events")
            
            # Read pots at interval
            if state_manager.should_scan_pots():
                changes['pots'] = self.components['pots'].read_pots()
                if changes['pots']:
                    log(TAG_HW, f"Pots changed: {len(changes['pots'])} events")
                state_manager.update_pot_scan_time()
            
            # Read encoders at interval
            if state_manager.should_scan_encoders():
                for i in range(self.components['encoders'].num_encoders):
                    new_events = self.components['encoders'].read_encoder(i)
                    if new_events:
                        changes['encoders'].extend(new_events)
                if changes['encoders']:
                    log(TAG_HW, f"Encoders changed: {len(changes['encoders'])} events")
                state_manager.update_encoder_scan_time()
                
            return changes
            
        except Exception as e:
            log(TAG_HW, f"Error reading hardware state: {str(e)}", is_error=True)
            return changes
    
    def handle_encoder_events(self, encoder_events, midi):
        try:
            for event in encoder_events:
                if event[0] == 'rotation':
                    _, direction = event[1:3]
                    midi.handle_octave_shift(direction)
                    log(TAG_HW, f"Octave shifted {direction}: new position {self.components['encoders'].get_encoder_position(0)}")
        except Exception as e:
            log(TAG_HW, f"Error handling encoder events: {str(e)}", is_error=True)
    
    def reset_encoders(self):
        try:
            self.components['encoders'].reset_all_encoder_positions()
            log(TAG_HW, "All encoder positions reset")
        except Exception as e:
            log(TAG_HW, f"Error resetting encoders: {str(e)}", is_error=True)
