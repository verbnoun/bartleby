"""Key state tracking and activation logic."""

import time
from constants import (
    NUM_KEYS,
    INITIAL_ACTIVATION_THRESHOLD, DEACTIVATION_THRESHOLD
)
from logging import log, TAG_KEYSTAT

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
        try:
            log(TAG_KEYSTAT, f"Initializing key state tracker for {NUM_KEYS} keys")
            self.key_states = [KeyState() for _ in range(NUM_KEYS)]
            self.active_keys = []
            self.key_hardware_data = {}
            log(TAG_KEYSTAT, "Key state tracker initialized")
        except Exception as e:
            log(TAG_KEYSTAT, f"Failed to initialize key state tracker: {str(e)}", is_error=True)
            raise

    def check_key_activation(self, left_norm, right_norm, key_state):
        """Implement dual-phase activation logic"""
        try:
            max_pressure = max(left_norm, right_norm)
            
            if key_state.active:
                # Key is already active - use deactivation threshold
                if max_pressure < DEACTIVATION_THRESHOLD:
                    log(TAG_KEYSTAT, f"Key deactivated - pressure: {max_pressure:.3f}")
                    key_state.active = False
                    return False
                return True
            else:
                # Key is inactive - use initial activation threshold
                if max_pressure > INITIAL_ACTIVATION_THRESHOLD:
                    key_state.active = True
                    key_state.strike_velocity = max_pressure  # Capture initial velocity
                    log(TAG_KEYSTAT, f"Key activated - initial velocity: {key_state.strike_velocity:.3f}")
                    return True
                return False
        except Exception as e:
            log(TAG_KEYSTAT, f"Error checking key activation: {str(e)}", is_error=True)
            return False

    def update_key_state(self, key_index, left_normalized, right_normalized, position, pressure):
        """Update state for a single key and determine if it changed"""
        try:
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
                    log(TAG_KEYSTAT, f"Key {key_index} added to active keys")
            else:
                if key_index in self.active_keys:
                    self.active_keys.remove(key_index)
                    log(TAG_KEYSTAT, f"Key {key_index} removed from active keys")

            # Check if state changed
            if (left_normalized != key_state.left_value or 
                right_normalized != key_state.right_value or
                position != key_state.position or
                pressure != key_state.pressure):
                
                # Log significant changes in position or pressure (>10%)
                if abs(position - key_state.position) > 0.1 or abs(pressure - key_state.pressure) > 0.1:
                    log(TAG_KEYSTAT, f"Key {key_index} significant change:")
                    log(TAG_KEYSTAT, f"L/R: {left_normalized:.3f}/{right_normalized:.3f}")
                    log(TAG_KEYSTAT, f"Position: {position:.3f}, Pressure: {pressure:.3f}")
                
                key_state.left_value = left_normalized
                key_state.right_value = right_normalized
                key_state.position = position
                key_state.pressure = pressure
                key_state.last_update = time.monotonic()
                
                processing_time = time.monotonic() - start_time
                if processing_time > 0.001:  # Log if processing takes more than 1ms
                    log(TAG_KEYSTAT, f"Key {key_index} update took {processing_time*1000:.2f}ms")
                
                return True
            return False
            
        except Exception as e:
            log(TAG_KEYSTAT, f"Error updating key {key_index} state: {str(e)}", is_error=True)
            return False

    def format_key_hardware_data(self):
        """Format hardware data for debugging"""
        try:
            data = self.key_hardware_data
            log(TAG_KEYSTAT, f"Generated hardware data for {len(data)} keys")
            return data
        except Exception as e:
            log(TAG_KEYSTAT, f"Error formatting key hardware data: {str(e)}", is_error=True)
            return {}
