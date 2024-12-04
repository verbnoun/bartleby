import board
import math
import time
import digitalio
import rotaryio
import analogio

class Constants:
    # Debug Settings
    DEBUG = False
    POT_LOG_THRESHOLD = 0.01
    
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
    
    OCTAVE_ENC_CLK = board.GP20
    OCTAVE_ENC_DT = board.GP21

    # Timing Intervals
    ENCODER_SCAN_INTERVAL = 0.001
    
    # Potentiometer Constants
    POT_THRESHOLD = 1500  # Threshold for initial pot activation
    POT_CHANGE_THRESHOLD = 400  # Threshold for subsequent changes when pot is active
    POT_LOWER_TRIM = 0.05
    POT_UPPER_TRIM = 0.0
    NUM_POTS = 16
    
    # Keyboard Constants
    NUM_KEYS = 25
    NUM_CHANNELS = 50

    # Sensor Constants
    MAX_VK_RESISTANCE = 10000 #11000 # Upper resistance bound
    MIN_VK_RESISTANCE = 750 #500   # Lower resistance bound
    INITIAL_ACTIVATION_THRESHOLD = 0.001 #0.01  # Threshold for note-on
    DEACTIVATION_THRESHOLD = 0.008  # Threshold for note-off
    REST_VOLTAGE_THRESHOLD = 3.3
    ADC_RESISTANCE_SCALE = 100000 #3500

    # Envelope Constants
    PRESSURE_FLOOR = 0.001      # Minimum pressure value to consider
    PRESSURE_CEILING = 1     # Maximum expected raw pressure value
    ENVELOPE_CURVE = 4       # Envelope curve shape (higher = more aggressive)


class Multiplexer:
    def __init__(self, sig_pin, s0_pin, s1_pin, s2_pin, s3_pin):
        """Initialize multiplexer with signal and select pins"""
        self.sig = analogio.AnalogIn(sig_pin)
        # Order pins from LSB to MSB (S0 to S3)
        self.select_pins = [
            digitalio.DigitalInOut(pin) for pin in (s0_pin, s1_pin, s2_pin, s3_pin)
        ]
        for pin in self.select_pins:
            pin.direction = digitalio.Direction.OUTPUT
            pin.value = False  # Initialize all pins to 0

    def select_channel(self, channel):
        """Set multiplexer channel selection pins"""
        # Convert channel number to 4-bit binary
        # For example, channel 5 (0101) should set S0=1, S1=0, S2=1, S3=0
        for i in range(4):
            self.select_pins[i].value = bool((channel >> i) & 1)
        time.sleep(0.0001)  # Small delay to allow mux to settle

    def read_channel(self, channel):
        """Read value from specified multiplexer channel"""
        if 0 <= channel < 16:  # Ensure channel is in valid range
            self.select_channel(channel)
            return self.sig.value
        return 0
    
class KeyMultiplexer:
    def __init__(self, l1_sig_pin, l1_s0_pin, l1_s1_pin, l1_s2_pin, l1_s3_pin, 
                 l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin):
        """Initialize key multiplexer with two-level multiplexing"""
        self.sig = analogio.AnalogIn(l1_sig_pin)

        # Initialize level 1 (MUX4) select pins
        self.l1_select_pins = [
            digitalio.DigitalInOut(pin) for pin in (l1_s0_pin, l1_s1_pin, l1_s2_pin, l1_s3_pin)
        ]
        for pin in self.l1_select_pins:
            pin.direction = digitalio.Direction.OUTPUT

        # Initialize level 2 (MUX3) select pins
        self.l2_select_pins = [
            digitalio.DigitalInOut(pin) for pin in (l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin)
        ]
        for pin in self.l2_select_pins:
            pin.direction = digitalio.Direction.OUTPUT

    def select_channel(self, level, channel):
        """Set channel selection pins for specified level"""
        pins = self.l1_select_pins if level == 1 else self.l2_select_pins
        for i, pin in enumerate(pins):
            pin.value = (channel >> i) & 1

    def read_channel(self):
        """Read current channel value"""
        return self.sig.value

    def scan_keyboard(self):
        """Scan all keyboard channels and return raw values"""
        raw_values = []
        for i in range(4):
            self.select_channel(1, i)  # Select a level 1 channel
            time.sleep(0.001)  # Allow the mux to settle
            
            # Determine the number of channels to scan on MUX3 (level 2)
            channels_to_scan = 16 if i < 3 else 2  # Last MUX only needs 2 channels
            
            # Scan the channels for the selected MUX3
            for j in range(channels_to_scan):
                self.select_channel(2, j)  # Select a level 2 channel
                time.sleep(0.001)  # Allow the mux to settle
                value = self.read_channel()  # Read the channel value
                raw_values.append(value)
        
        return raw_values

class PressureSensorProcessor:
    def adc_to_resistance(self, adc_value):
        """Convert ADC reading to resistance value"""
        voltage = (adc_value / Constants.ADC_MAX) * 3.3
        if voltage >= Constants.REST_VOLTAGE_THRESHOLD:
            return float('inf')
        return Constants.ADC_RESISTANCE_SCALE * voltage / (3.3 - voltage)
        
    def normalize_resistance(self, resistance):
        """Convert resistance to normalized pressure value (0.0-1.0) using logarithmic curve"""
        if resistance >= Constants.MAX_VK_RESISTANCE:
            return 0
        if resistance <= Constants.MIN_VK_RESISTANCE:
            return 1
            
        # Calculate logarithmic normalization
        log_min = math.log(Constants.MIN_VK_RESISTANCE)
        log_max = math.log(Constants.MAX_VK_RESISTANCE)
        log_value = math.log(resistance)
        
        # Inverse the normalization since resistance decreases with pressure
        normalized = 1.0 - ((log_value - log_min) / (log_max - log_min))
        
        # Apply envelope
        return self.apply_envelope(normalized)

    def apply_envelope(self, raw_pressure):
        """Apply envelope to expand limited pressure range"""
        # Clamp to floor/ceiling
        if raw_pressure < Constants.PRESSURE_FLOOR:
            return 0.0
        if raw_pressure > Constants.PRESSURE_CEILING:
            return 1.0
            
        # Normalize to new range
        normalized = (raw_pressure - Constants.PRESSURE_FLOOR) / (Constants.PRESSURE_CEILING - Constants.PRESSURE_FLOOR)
        
        # Apply curve
        curved = math.pow(normalized, Constants.ENVELOPE_CURVE)
        
        return max(0.0, min(1.0, curved))

    def calculate_position(self, left_norm, right_norm):
        """Calculate relative position (-1.0 to 1.0) from normalized L/R values"""
        total = left_norm + right_norm
        if total == 0:
            return 0
        return (right_norm - left_norm) / total

    def calculate_pressure(self, left_norm, right_norm):
        """Calculate total pressure (0.0-1.0) from normalized L/R values"""
        return max(left_norm, right_norm)

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
        self.key_states = [KeyState() for _ in range(Constants.NUM_KEYS)]
        self.active_keys = []
        self.key_hardware_data = {}

    def check_key_activation(self, left_norm, right_norm, key_state):
        """Implement dual-phase activation logic"""
        max_pressure = max(left_norm, right_norm)
        
        if key_state.active:
            # Key is already active - use deactivation threshold
            if max_pressure < Constants.DEACTIVATION_THRESHOLD:
                if Constants.DEBUG:
                    print(f"Key deactivated - pressure: {max_pressure:.3f}")
                key_state.active = False
                return False
            return True
        else:
            # Key is inactive - use initial activation threshold
            if max_pressure > Constants.INITIAL_ACTIVATION_THRESHOLD:
                key_state.active = True
                key_state.strike_velocity = max_pressure  # Capture initial velocity
                if Constants.DEBUG:
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
                if Constants.DEBUG:
                    print(f"\nKey {key_index} activated")
        else:
            if key_index in self.active_keys:
                self.active_keys.remove(key_index)
                if Constants.DEBUG:
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
            if Constants.DEBUG:
                print(f"\nKey {key_index} state updated:")
                print(f"L/R: {left_normalized:.3f}/{right_normalized:.3f}")
                print(f"Position: {position:.3f}, Pressure: {pressure:.3f}")
            return True
        return False

    def format_key_hardware_data(self):
        """Format hardware data for debugging"""
        return self.key_hardware_data

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

class RotaryEncoderHandler:
    def __init__(self, octave_clk_pin, octave_dt_pin):
        """Initialize rotary encoder handler"""
        # Initialize encoders using rotaryio
        self.encoders = [
            rotaryio.IncrementalEncoder(octave_clk_pin, octave_dt_pin, divisor=2)
        ]
        
        self.num_encoders = len(self.encoders)
        self.min_position = -3  # Changed from 0 to -3 to allow down three octaves
        self.max_position = 3   # Allow up three octaves

        # Initialize state tracking
        self.encoder_positions = [0] * self.num_encoders
        self.last_positions = [encoder.position for encoder in self.encoders]

        self.reset_all_encoder_positions()

    def reset_all_encoder_positions(self):
        """Reset all encoder positions to initial state"""
        for i in range(self.num_encoders):
            self.reset_encoder_position(i)

    def reset_encoder_position(self, encoder_num):
        """Reset specified encoder to initial position"""
        if 0 <= encoder_num < self.num_encoders:
            self.encoders[encoder_num].position = 0
            self.encoder_positions[encoder_num] = 0
            self.last_positions[encoder_num] = 0

    def read_encoder(self, encoder_num):
        """Read encoder and return events if position changed"""
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
        """Get current position of specified encoder"""
        if 0 <= encoder_num < self.num_encoders:
            return self.encoder_positions[encoder_num]
        return 0

class PotentiometerHandler:
    def __init__(self, multiplexer):
        """Initialize potentiometer handler with multiplexer"""
        self.multiplexer = multiplexer
        self.last_reported_values = [0] * Constants.NUM_POTS
        self.last_normalized_values = [0.0] * Constants.NUM_POTS
        self.is_active = [False] * Constants.NUM_POTS
        self.last_change = [0] * Constants.NUM_POTS

    def normalize_value(self, value):
        """Convert ADC value to normalized range (0.0-1.0)"""
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
        """Read all potentiometers and return changed values"""
        changed_pots = []
        for i in range(Constants.NUM_POTS):
            raw_value = self.multiplexer.read_channel(i)
            normalized_new = self.normalize_value(raw_value)
            change = abs(raw_value - self.last_reported_values[i])
            change_normalized = abs(normalized_new - self.last_normalized_values[i])

            if self.is_active[i]:
                # Only report changes if they exceed the change threshold
                if change > Constants.POT_CHANGE_THRESHOLD:
                    # Only report if normalized value has actually changed
                    if normalized_new != self.last_normalized_values[i]:
                        changed_pots.append((i, self.last_normalized_values[i], normalized_new))
                        self.last_reported_values[i] = raw_value
                        self.last_normalized_values[i] = normalized_new
                        self.last_change[i] = change
                        
                        # Only log if change exceeds logging threshold
                        if Constants.DEBUG and change_normalized > Constants.POT_LOG_THRESHOLD:
                            print(f"\nPot {i}: {self.last_normalized_values[i]:.3f} -> {normalized_new:.3f}")
                            
                elif change < Constants.POT_THRESHOLD:
                    self.is_active[i] = False
            elif change > Constants.POT_THRESHOLD:
                self.is_active[i] = True
                if normalized_new != self.last_normalized_values[i]:
                    changed_pots.append((i, self.last_normalized_values[i], normalized_new))
                    self.last_reported_values[i] = raw_value
                    self.last_normalized_values[i] = normalized_new
                    self.last_change[i] = change
                    
                    # Only log if change exceeds logging threshold
                    if Constants.DEBUG and change_normalized > Constants.POT_LOG_THRESHOLD:
                        print(f"\nPot {i}: {self.last_normalized_values[i]:.3f} -> {normalized_new:.3f}")
                
        return changed_pots

    def read_all_pots(self):
        """Read all potentiometers and return their current normalized values"""
        all_pots = []
        for i in range(Constants.NUM_POTS):
            raw_value = self.multiplexer.read_channel(i)
            normalized_value = self.normalize_value(raw_value)
            
            # Update last values to ensure subsequent read_pots() works correctly
            self.last_reported_values[i] = raw_value
            self.last_normalized_values[i] = normalized_value
            
            # Mark as active to prevent filtering out in subsequent read_pots()
            self.is_active[i] = True
            
            all_pots.append((i, normalized_value))
            
            if Constants.DEBUG:
                print(f"Initial Pot {i}: {normalized_value:.3f}")
        
        return all_pots
