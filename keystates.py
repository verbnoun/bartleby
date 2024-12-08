import time
from constants import (
    NUM_KEYS, DEBUG,
    INITIAL_ACTIVATION_THRESHOLD, DEACTIVATION_THRESHOLD
)

class KeyState:
    def __init__(self):
        """Initialize key state tracking"""
        self.active = False
        self.left_value = 0
        self.right_value = 0
        self.position = 0  # -1.0 to 1.0 for MPE pitch bend
        self.pressure = 0  # 0.0 to 1.0 for MPE pressure
        self.strike_velocity = 0  # 0.0 to 1.0 for MIDI note velocity
        self.last_update = 0
        self.adc_timestamp = 0  # Time when ADC reading started

class KeyStateTracker:
    def __init__(self):
        """Initialize key state tracking system"""
        self.key_states = [KeyState() for _ in range(NUM_KEYS)]
        self.active_keys = []
        self.key_hardware_data = {}

    def check_key_activation(self, left_norm, right_norm, key_state):
        """Implement dual-phase activation logic"""
        max_pressure = max(left_norm, right_norm)
        
        if key_state.active:
            # Key is already active - use deactivation threshold
            if max_pressure < DEACTIVATION_THRESHOLD:
                if DEBUG:
                    print(f"Key deactivated - pressure: {max_pressure:.3f}")
                key_state.active = False
                return False
            return True
        else:
            # Key is inactive - use initial activation threshold
            if max_pressure > INITIAL_ACTIVATION_THRESHOLD:
                key_state.active = True
                key_state.strike_velocity = max_pressure  # Capture initial velocity
                if DEBUG:
                    print(f"Key activated - initial velocity: {key_state.strike_velocity:.3f}")
                return True
            return False

    def update_key_state(self, key_index, left_normalized, right_normalized, position, pressure):
        """Update state for a single key and determine if it changed"""
        start_time = time.monotonic()
        key_state = self.key_states[key_index]
        is_active = self.check_key_activation(left_normalized, right_normalized, key_state)
        
        # Store hardware data
        self.key_hardware_data[key_index] = {
            "L": left_normalized,
            "R": right_normalized,
            "position": position,
            "pressure": pressure,
            "processing_time": time.monotonic() - start_time
        }
        
        if is_active:
            if key_index not in self.active_keys:
                self.active_keys.append(key_index)
                if DEBUG:
                    print(f"\nKey {key_index} activated")
        else:
            if key_index in self.active_keys:
                self.active_keys.remove(key_index)
                if DEBUG:
                    print(f"\nKey {key_index} deactivated")

        # Check if state changed
        if (left_normalized != key_state.left_value or 
            right_normalized != key_state.right_value or
            position != key_state.position or
            pressure != key_state.pressure):
            key_state.left_value = left_normalized
            key_state.right_value = right_normalized
            key_state.position = position
            key_state.pressure = pressure
            key_state.last_update = time.monotonic()
            if DEBUG:
                print(f"\nKey {key_index} state updated:")
                print(f"L/R: {left_normalized:.3f}/{right_normalized:.3f}")
                print(f"Position: {position:.3f}, Pressure: {pressure:.3f}")
            return True
        return False

    def format_key_hardware_data(self):
        """Format hardware data for debugging"""
        return self.key_hardware_data
