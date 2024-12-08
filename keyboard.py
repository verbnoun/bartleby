import time
import digitalio
from constants import DEBUG, NUM_KEYS
from pressure import PressureSensorProcessor
from keystates import KeyStateTracker

class KeyboardHandler:
    def __init__(self, l1a_multiplexer, l1b_multiplexer, l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin):
        """Initialize keyboard handler with multiplexers and support classes"""
        self.l1a_mux = l1a_multiplexer
        self.l1b_mux = l1b_multiplexer
        
        # Initialize level 2 select pins
        self.l2_select_pins = [
            digitalio.DigitalInOut(pin) for pin in (l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin)
        ]
        for pin in self.l2_select_pins:
            pin.direction = digitalio.Direction.OUTPUT
            pin.value = False

        # Initialize support classes
        self.pressure_processor = PressureSensorProcessor()
        self.state_tracker = KeyStateTracker()
            
    def set_l2_channel(self, channel):
        """Set L2 multiplexer channel"""
        for i, pin in enumerate(self.l2_select_pins):
            pin.value = (channel >> i) & 1
        time.sleep(0.0001)  # 100 microseconds settling time
            
    def read_keys(self):
        """Read all keys with dual-phase detection"""
        changed_keys = []
        key_index = 0
        
        # Read first group (keys 1-5) from L2 Mux A through L1 Mux A channel 0
        for channel in range(1, 11, 2):
            self.set_l2_channel(channel)
            left_value = self.l1a_mux.read_channel(0)
            
            self.set_l2_channel(channel + 1)
            right_value = self.l1a_mux.read_channel(0)
            
            self._process_key_reading(key_index, left_value, right_value, changed_keys)
            key_index += 1
            
        # Read second group (keys 6-12) directly from L1 Mux A
        for channel in range(1, 15, 2):
            left_value = self.l1a_mux.read_channel(channel)
            right_value = self.l1a_mux.read_channel(channel + 1)
            
            self._process_key_reading(key_index, left_value, right_value, changed_keys)
            key_index += 1
            
        # Read third group (keys 13-19) directly from L1 Mux B
        for channel in range(1, 15, 2):
            left_value = self.l1b_mux.read_channel(channel)
            right_value = self.l1b_mux.read_channel(channel + 1)
            
            self._process_key_reading(key_index, left_value, right_value, changed_keys)
            key_index += 1
            
        # Read final group (keys 20-25) from L2 Mux B through L1 Mux B channel 0
        for channel in range(1, 13, 2):
            self.set_l2_channel(channel)
            left_value = self.l1b_mux.read_channel(0)
            
            self.set_l2_channel(channel + 1)
            right_value = self.l1b_mux.read_channel(0)
            
            self._process_key_reading(key_index, left_value, right_value, changed_keys)
            key_index += 1
            
        return changed_keys
        
    def _process_key_reading(self, key_index, left_value, right_value, changed_keys):
        """Process individual key readings with MPE calculations"""
        start_time = time.monotonic()
        
        # Convert ADC values to normalized pressures
        left_resistance = self.pressure_processor.adc_to_resistance(left_value)
        right_resistance = self.pressure_processor.adc_to_resistance(right_value)
        left_normalized = self.pressure_processor.normalize_resistance(left_resistance)
        right_normalized = self.pressure_processor.normalize_resistance(right_resistance)
        
        # Calculate MPE values
        position = self.pressure_processor.calculate_position(left_normalized, right_normalized)
        pressure = self.pressure_processor.calculate_pressure(left_normalized, right_normalized)
        
        # Update state and check for changes
        if self.state_tracker.update_key_state(key_index, left_normalized, right_normalized, position, pressure):
            key_state = self.state_tracker.key_states[key_index]
            changed_keys.append((
                key_index,
                position,  # X-axis (pitch bend)
                pressure,  # Z-axis (pressure)
                key_state.strike_velocity if not key_state.active else None  # Initial velocity
            ))
            
    def format_key_hardware_data(self):
        """Format hardware data for debugging"""
        return self.state_tracker.format_key_hardware_data()
