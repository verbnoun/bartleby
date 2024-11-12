import board
import time
import math
import digitalio
import rotaryio
import analogio

class Constants:
    DEBUG = True
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
    
    # Encoder GPIO Pins
    OCTAVE_ENC_CLK = board.GP20
    OCTAVE_ENC_DT = board.GP21

    # Potentiometer Constants
    POT_THRESHOLD = 1500  # Threshold for initial pot activation
    POT_CHANGE_THRESHOLD = 400  # Threshold for subsequent changes when pot is active
    POT_LOWER_TRIM = 0.05
    POT_UPPER_TRIM = 0.0
    NUM_POTS = 14
    
    # Keyboard Handler Constants
    NUM_KEYS = 25
    NUM_CHANNELS = 50
    """
    Velostat Pressure Sensor Properties:
    - High Resistance (≈150kΩ+): No/minimal pressure
    - Medium Resistance (≈40-80kΩ): Light touch
    - Low Resistance (≈1-10kΩ): Firm pressure
    
    MAX_VK_RESISTANCE: Upper resistance bound, readings above this normalize to 0 (no pressure)
    MIN_VK_RESISTANCE: Lower resistance bound, readings below this normalize to 1 (max pressure)
    
    Normalization maps this inverse relationship:
    - High resistance -> Low normalized value (light/no touch)
    - Low resistance -> High normalized value (firm pressure)
    """
    MAX_VK_RESISTANCE = 11000  
    MIN_VK_RESISTANCE = 500    
    INITIAL_ACTIVATION_THRESHOLD = 0.001
    TRACKING_THRESHOLD = 0.015
    DEACTIVATION_THRESHOLD = 0.008
    REST_VOLTAGE_THRESHOLD = 3.15
    ADC_RESISTANCE_SCALE = 3500

    # Envelope Control Points (in ohms)
    # These define the resistance values where envelope stages transition
    ENVELOPE_LIGHT_R = 9000    # Where quick initial ramp ends
    ENVELOPE_MID_R = 2000      # Where expressive mid-range ends 
    ENVELOPE_HEAVY_R = 1000    # Where final ramp to max begins
    
    # Envelope Curve Powers
    # These control the shape of each section (lower = more dramatic curve)
    ENVELOPE_LIGHT_CURVE = 0.6  # Initial ramp curve (light touch)
    ENVELOPE_MID_CURVE = 0.3    # Mid-range curve
    ENVELOPE_HEAVY_CURVE = 0.8  # Heavy press curve

class Multiplexer:
    def __init__(self, sig_pin, s0_pin, s1_pin, s2_pin, s3_pin):
        self.sig = analogio.AnalogIn(sig_pin)
        # Order pins from LSB to MSB (S0 to S3)
        self.select_pins = [
            digitalio.DigitalInOut(pin) for pin in (s0_pin, s1_pin, s2_pin, s3_pin)
        ]
        for pin in self.select_pins:
            pin.direction = digitalio.Direction.OUTPUT
            pin.value = False  # Initialize all pins to 0

    def select_channel(self, channel):
        # Convert channel number to 4-bit binary
        # For example, channel 5 (0101) should set S0=1, S1=0, S2=1, S3=0
        for i in range(4):
            self.select_pins[i].value = bool((channel >> i) & 1)
        time.sleep(0.0001)  # Small delay to allow mux to settle

    def read_channel(self, channel):
        if 0 <= channel < 16:  # Ensure channel is in valid range
            self.select_channel(channel)
            return self.sig.value
        return 0
    


import rotaryio

class RotaryEncoderHandler:
    def __init__(self, octave_clk_pin, octave_dt_pin):
        # Initialize encoders using rotaryio
        self.encoders = [
            rotaryio.IncrementalEncoder(octave_clk_pin, octave_dt_pin, divisor=2)
        ]
        
        self.num_encoders = len(self.encoders)
        self.min_position = 0
        self.max_position = 3  # 4 modes (0-3)

        # Initialize state tracking
        self.encoder_positions = [0] * self.num_encoders
        self.last_positions = [encoder.position for encoder in self.encoders]

        self.reset_all_encoder_positions()

    def reset_all_encoder_positions(self):
        for i in range(self.num_encoders):
            self.reset_encoder_position(i)

    def reset_encoder_position(self, encoder_num):
        if 0 <= encoder_num < self.num_encoders:
            self.encoders[encoder_num].position = 0
            self.encoder_positions[encoder_num] = 0
            self.last_positions[encoder_num] = 0

    def read_encoder(self, encoder_num):
        events = []
        encoder = self.encoders[0]  

        events = []
        encoder = self.encoders[encoder_num]
        
        # Read current position
        current_position = encoder.position
        last_position = self.last_positions[encoder_num]

        # Check if the encoder position has changed
        if current_position != last_position:
            # Calculate direction (-1 for left, +1 for right)
            direction = 1 if current_position > last_position else -1

            # Update position with bounds checking
            new_pos = max(self.min_position, min(self.max_position, 
                                                 self.encoder_positions[encoder_num] + direction))
            
            # Only generate event if position actually changed within limits
            if new_pos != self.encoder_positions[encoder_num]:
                self.encoder_positions[encoder_num] = new_pos
                events.append(('rotation', encoder_num, direction, new_pos))
                
                if Constants.DEBUG:
                    print(f"E{encoder_num}: Position: {self.encoder_positions[encoder_num]} -> {new_pos}")
        
        # Save the current position for the next read
        self.last_positions[encoder_num] = current_position
        
        return events

    def get_encoder_position(self, encoder_num):
        if 0 <= encoder_num < self.num_encoders:
            return self.encoder_positions[encoder_num]
        return 0


class PotentiometerHandler:
    def __init__(self, multiplexer):
        self.multiplexer = multiplexer
        self.last_reported_values = [0] * Constants.NUM_POTS
        self.last_normalized_values = [0.0] * Constants.NUM_POTS
        self.is_active = [False] * Constants.NUM_POTS
        self.last_change = [0] * Constants.NUM_POTS

    def normalize_value(self, value):
        clamped_value = max(min(value, Constants.ADC_MAX), Constants.ADC_MIN)
        normalized = (clamped_value - Constants.ADC_MIN) / (Constants.ADC_MAX - Constants.ADC_MIN)
        if normalized < Constants.POT_LOWER_TRIM:
            normalized = 0
        elif normalized > (1 - Constants.POT_UPPER_TRIM):
            normalized = 1
        else:
            normalized = (normalized - Constants.POT_LOWER_TRIM) / (1 - Constants.POT_LOWER_TRIM - Constants.POT_UPPER_TRIM)
        return round(normalized, 3)  # Reduced precision to help with noise

    def read_pots(self):
        changed_pots = []
        for i in range(Constants.NUM_POTS):
            raw_value = self.multiplexer.read_channel(i)
            normalized_new = self.normalize_value(raw_value)
            change = abs(raw_value - self.last_reported_values[i])

            if self.is_active[i]:
                # Only report changes if they exceed the change threshold
                if change > Constants.POT_CHANGE_THRESHOLD:
                    # Only report if normalized value has actually changed
                    if normalized_new != self.last_normalized_values[i]:
                        changed_pots.append((i, self.last_normalized_values[i], normalized_new))
                        self.last_reported_values[i] = raw_value
                        self.last_normalized_values[i] = normalized_new
                        self.last_change[i] = change
                elif change < Constants.POT_THRESHOLD:
                    self.is_active[i] = False
            elif change > Constants.POT_THRESHOLD:
                self.is_active[i] = True
                if normalized_new != self.last_normalized_values[i]:
                    changed_pots.append((i, self.last_normalized_values[i], normalized_new))
                    self.last_reported_values[i] = raw_value
                    self.last_normalized_values[i] = normalized_new
                    self.last_change[i] = change
                
        return changed_pots

class KeyState:
    def __init__(self):
        self.active = False
        self.left_value = 0
        self.right_value = 0
        self.last_update = 0

class KeyMultiplexer:
    def __init__(self, sig_a_pin, sig_b_pin, l1_s0_pin, l1_s1_pin, l1_s2_pin, l1_s3_pin, 
                 l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin):
        """Initialize keyboard multiplexer with shared control pins for both banks"""
        # Initialize the L1 signal pins
        self.sig_a = analogio.AnalogIn(sig_a_pin)
        self.sig_b = analogio.AnalogIn(sig_b_pin)
        self.current_bank = 'a'  # Track which bank we're reading
        
        # Initialize L1 control pins (shared between banks)
        self.l1_select_pins = [
            digitalio.DigitalInOut(pin) for pin in (l1_s0_pin, l1_s1_pin, l1_s2_pin, l1_s3_pin)
        ]
        for pin in self.l1_select_pins:
            pin.direction = digitalio.Direction.OUTPUT
            pin.value = False

        # Initialize L2 select pins (shared between banks)
        self.l2_select_pins = [
            digitalio.DigitalInOut(pin) for pin in (l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin)
        ]
        for pin in self.l2_select_pins:
            pin.direction = digitalio.Direction.OUTPUT
            pin.value = False

        # Define scanning configurations
        self.l2a_active_channels = 10  # Channels 1-10 for keys 0-4
        self.l2b_active_channels = 14  # Channels 1-14 for keys 18-24
        self.l1_direct_channels = 14   # Channels 1-14 for direct connections
        self.settling_time = 0.001     # 1ms settling time

    def select_bank(self, bank):
        """Select which bank to read from (a or b)"""
        self.current_bank = bank

    def set_l1_channel(self, channel):
        """Set Level 1 multiplexer channel (0-15)"""
        if 0 <= channel < 16:
            for i, pin in enumerate(self.l1_select_pins):
                pin.value = bool((channel >> i) & 1)
            time.sleep(self.settling_time)

    def set_l2_channel(self, channel):
        """Set Level 2 multiplexer channel (0-15)"""
        if 0 <= channel < 16:
            for i, pin in enumerate(self.l2_select_pins):
                pin.value = bool((channel >> i) & 1)
            time.sleep(self.settling_time)

    def read_current_channel(self):
        """Read the currently selected channel's value from current bank"""
        return self.sig_a.value if self.current_bank == 'a' else self.sig_b.value

    def scan_all_channels(self, bank):
        """Scan all valid channel combinations for specified bank and return raw readings"""
        readings = []
        self.select_bank(bank)
        
        if bank == 'a':
            # First read L2A channels through L1A channel 0
            self.set_l1_channel(0)  # Select L2A input
            for channel in range(1, self.l2a_active_channels + 1):
                self.set_l2_channel(channel)
                readings.append(self.read_current_channel())
            
            # Then read L1A direct channels
            for channel in range(1, self.l1_direct_channels + 1):
                self.set_l1_channel(channel)
                readings.append(self.read_current_channel())
                
        else:  # bank == 'b'
            # First read L2B channels through L1B channel 0
            self.set_l1_channel(0)  # Select L2B input
            for channel in range(1, self.l2b_active_channels + 1):
                self.set_l2_channel(channel)
                readings.append(self.read_current_channel())
            
            # Then read L1B direct channels
            for channel in range(1, self.l1_direct_channels + 1):
                self.set_l1_channel(channel)
                readings.append(self.read_current_channel())

        return readings

    def cleanup(self):
        """Clean up GPIO pins"""
        self.sig_a.deinit()
        self.sig_b.deinit()
        for pin in self.l1_select_pins + self.l2_select_pins:
            pin.deinit()

class KeyDataProcessor:
    """Handles conversion of physical measurements to musical expression"""
    def __init__(self):
        pass
        
    def process_key_data(self, left_resistance, right_resistance, current_state):
        """Process resistance values into musical parameters"""
        # Calculate pressure
        left_pressure = self._normalize_pressure(left_resistance)
        right_pressure = self._normalize_pressure(right_resistance)
        
        avg_pressure = (left_pressure + right_pressure) / 2
        
        # Calculate velocity based on pressure and state
        velocity = self._calculate_velocity(avg_pressure)
        
        # Calculate pitch bend from pressure differential
        pitch_bend = self._calculate_pitch_bend(left_pressure, right_pressure)
        
        return {
            'pressure': avg_pressure,
            'velocity': velocity,
            'pitch_bend': pitch_bend,
            'left_pressure': left_pressure,
            'right_pressure': right_pressure
        }
        
    def _normalize_pressure(self, resistance):
        """Convert resistance to normalized pressure value with multi-stage envelope"""
        if resistance >= Constants.MAX_VK_RESISTANCE:
            return 0
        if resistance <= Constants.MIN_VK_RESISTANCE:
            return 1
            
        # Determine which envelope section we're in
        if resistance >= Constants.ENVELOPE_LIGHT_R:
            # Light touch section - quick ramp
            range_max = Constants.MAX_VK_RESISTANCE
            range_min = Constants.ENVELOPE_LIGHT_R
            curve = Constants.ENVELOPE_LIGHT_CURVE
            out_min = 0.0
            out_max = 0.3
            
        elif resistance >= Constants.ENVELOPE_MID_R:
            # Mid pressure section - more gradual
            range_max = Constants.ENVELOPE_LIGHT_R
            range_min = Constants.ENVELOPE_MID_R
            curve = Constants.ENVELOPE_MID_CURVE
            out_min = 0.3
            out_max = 0.7
            
        elif resistance >= Constants.ENVELOPE_HEAVY_R:
            # Heavy pressure section - quick ramp to max
            range_max = Constants.ENVELOPE_MID_R
            range_min = Constants.ENVELOPE_HEAVY_R
            curve = Constants.ENVELOPE_HEAVY_CURVE
            out_min = 0.7
            out_max = 0.9
            
        else:
            # Final ramp to max pressure
            range_max = Constants.ENVELOPE_HEAVY_R
            range_min = Constants.MIN_VK_RESISTANCE
            curve = Constants.ENVELOPE_HEAVY_CURVE
            out_min = 0.9
            out_max = 1.0

        # Calculate normalized position within this section
        pos = (range_max - resistance) / (range_max - range_min)
        
        # Apply curve and scale to section's output range
        curved = pow(pos, curve)
        return out_min + (curved * (out_max - out_min))
    
    def _calculate_velocity(self, pressure):
        """Calculate note velocity from pressure"""
        return int(pressure * 127)
    
    def _calculate_pitch_bend(self, left_pressure, right_pressure):
        """Calculate pitch bend from pressure differential"""
        pressure_diff = right_pressure - left_pressure
        max_pressure = max(left_pressure, right_pressure)
        if max_pressure == 0:
            return 0
        normalized_diff = pressure_diff / max_pressure
        return max(-1, min(1, normalized_diff))
    
class KeyState:
    """Tracks the physical state of a single key"""
    # State definitions
    INACTIVE = 0
    INITIAL_TOUCH = 1
    ACTIVE = 2
    RELEASE_PENDING = 3
    RELEASED = 4

    def __init__(self):
        self.state = self.INACTIVE
        self.left_resistance = float('inf')
        self.right_resistance = float('inf')
        self.last_update = 0
        
class KeyboardHandler:
    def __init__(self, keyboard_mux, data_processor):
        """Initialize keyboard handler with multiplexer and data processor"""
        self.mux = keyboard_mux
        self.data_processor = data_processor
        self.key_states = [KeyState() for _ in range(Constants.NUM_KEYS)]
        self.active_keys = []
        self.key_hardware_data = {}
        
    def read_keys(self):
        """Read all keys and process their states"""
        changed_keys = []
        current_active_keys = []
        self.key_hardware_data.clear()
        
        # Get raw readings from both banks
        readings_a = self.mux.scan_all_channels('a')
        readings_b = self.mux.scan_all_channels('b')
        
        # Process keys 0-4 (through L2A, first 10 readings from bank A in pairs)
        for i in range(0, 10, 2):
            key_index = i // 2
            left_value = readings_a[i]
            right_value = readings_a[i + 1]
            self._process_key_reading(key_index, left_value, right_value, 
                                   current_active_keys, changed_keys)

        # Process keys 5-11 (direct on L1A, next 14 readings from bank A in pairs)
        l1a_base_idx = 10
        for i in range(0, 14, 2):
            key_index = 5 + (i // 2)
            left_value = readings_a[l1a_base_idx + i]
            right_value = readings_a[l1a_base_idx + i + 1]
            self._process_key_reading(key_index, left_value, right_value, 
                                   current_active_keys, changed_keys)

        # Process keys 12-17 (direct on L1B, first 14 readings from bank B in pairs)
        l1b_direct_readings = readings_b[14:]
        for i in range(0, 14, 2):
            key_index = 12 + (i // 2)
            left_value = l1b_direct_readings[i]
            right_value = l1b_direct_readings[i + 1]
            self._process_key_reading(key_index, left_value, right_value, 
                                   current_active_keys, changed_keys)

        # Process keys 18-24 (through L2B, first 14 readings from bank B in pairs)
        l2b_readings = readings_b[:14]
        for i in range(0, 14, 2):
            key_index = 18 + (i // 2)
            left_value = l2b_readings[i]
            right_value = l2b_readings[i + 1]
            self._process_key_reading(key_index, left_value, right_value, 
                                   current_active_keys, changed_keys)
            
        self.active_keys = current_active_keys
        return changed_keys

    def _process_key_reading(self, key_index, left_adc, right_adc, 
                           current_active_keys, changed_keys):
        """Process individual key readings and manage state transitions"""
        # Convert ADC to resistance
        left_resistance = self._adc_to_resistance(left_adc)
        right_resistance = self._adc_to_resistance(right_adc)
        
        key_state = self.key_states[key_index]
        
        # Determine if electrical values have changed
        values_changed = (
            left_resistance != key_state.left_resistance or 
            right_resistance != key_state.right_resistance
        )
        
        # Get processed pressure values from data processor
        processed_data = self.data_processor.process_key_data(
            left_resistance, right_resistance, key_state.state
        )
        
        # Handle state transitions
        new_state = self._update_key_state(
            key_state, processed_data['pressure'], processed_data['velocity']
        )
        
        # Store hardware data for debugging
        self.key_hardware_data[key_index] = (left_resistance, right_resistance)
        
        # Track active keys
        if new_state in (KeyState.ACTIVE, KeyState.INITIAL_TOUCH):
            current_active_keys.append(key_index)
            
            # Debug output
            if Constants.DEBUG:
                print(f"\nKey {key_index:02d}")
                print(f"  L: ADC={left_adc:5d} → R={left_resistance:8.1f}Ω")
                print(f"  R: ADC={right_adc:5d} → R={right_resistance:8.1f}Ω")
        
        # Record state changes
        if values_changed or new_state != key_state.state:
            key_state.left_resistance = left_resistance
            key_state.right_resistance = right_resistance
            key_state.state = new_state
            key_state.last_update = time.monotonic()
            changed_keys.append((key_index, processed_data['pressure'], 
                               processed_data['pitch_bend']))
    
    def _update_key_state(self, key_state, pressure, velocity):
        """Handle state machine transitions"""
        current_state = key_state.state
        
        if current_state == KeyState.INACTIVE:
            if pressure > Constants.INITIAL_ACTIVATION_THRESHOLD:
                return KeyState.INITIAL_TOUCH
                
        elif current_state == KeyState.INITIAL_TOUCH:
            if pressure < Constants.DEACTIVATION_THRESHOLD:
                return KeyState.INACTIVE
            return KeyState.ACTIVE
                
        elif current_state == KeyState.ACTIVE:
            if pressure < Constants.TRACKING_THRESHOLD:
                return KeyState.RELEASE_PENDING
                
        elif current_state == KeyState.RELEASE_PENDING:
            if pressure > Constants.TRACKING_THRESHOLD:
                return KeyState.ACTIVE
            elif pressure < Constants.DEACTIVATION_THRESHOLD:
                return KeyState.RELEASED
                
        elif current_state == KeyState.RELEASED:
            if pressure < Constants.DEACTIVATION_THRESHOLD:
                return KeyState.INACTIVE
            return KeyState.ACTIVE
            
        return current_state
    
    def _adc_to_resistance(self, adc_value):
        """Convert ADC reading to resistance value"""
        voltage = (adc_value / Constants.ADC_MAX) * 3.3
        if voltage >= Constants.REST_VOLTAGE_THRESHOLD:
            return float('inf')
        return Constants.ADC_RESISTANCE_SCALE * voltage / (3.3 - voltage)

    def format_key_hardware_data(self):
        """Format hardware data for debugging"""
        return {k: {"L": v[0], "R": v[1]} for k, v in self.key_hardware_data.items()}
