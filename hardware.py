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

    # Key Detection
    ACTIVATION_THRESHOLD = 0.02    # Initial key activation
    RELEASE_THRESHOLD = 0.01       # Key release detection
    
    # Processing
    POSITION_CENTER_WEIGHT = 0.3   # Position curve shaping
    PRESSURE_CURVE = 0.5          # Pressure response curve
    STRIKE_SCALING = 1.2          # Strike velocity scaling

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

import time
import digitalio
import analogio

class KeyMultiplexer:
    """Handles multiplexer bank switching and key pair reading with timing diagnostics"""
    
    # Bank identifiers (in scan order)
    BANK_L2A = 0  # Keys 0-4
    BANK_L1A = 1  # Keys 5-11
    BANK_L1B = 2  # Keys 12-18
    BANK_L2B = 3  # Keys 19-24
    
    def __init__(self, sig_a_pin, sig_b_pin, 
                 l1a_s0_pin, l1a_s1_pin, l1a_s2_pin, l1a_s3_pin,
                 l1b_s0_pin, l1b_s1_pin, l1b_s2_pin, l1b_s3_pin,
                 l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin):
                 
        # Initialize signal pins
        self.sig_a = analogio.AnalogIn(sig_a_pin)
        self.sig_b = analogio.AnalogIn(sig_b_pin)
        
        # Initialize all pins in one loop
        self.select_pins = {}
        for name, pins in {
            'L1A': (l1a_s0_pin, l1a_s1_pin, l1a_s2_pin, l1a_s3_pin),
            'L1B': (l1b_s0_pin, l1b_s1_pin, l1b_s2_pin, l1b_s3_pin),
            'L2': (l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin)
        }.items():
            self.select_pins[name] = []
            for pin in pins:
                io = digitalio.DigitalInOut(pin)
                io.direction = digitalio.Direction.OUTPUT
                io.value = False
                self.select_pins[name].append(io)
        
        # Track current state
        self.current_bank = None
        self.current_channel = None
        self.pin_states = {
            'L1A': [False] * 4,
            'L1B': [False] * 4,
            'L2': [False] * 4
        }
        
        # Bank configuration lookup
        self.bank_config = {
            self.BANK_L2A: ('L2', 'sig_a', (1, 5)),    # Keys 0-4:  channels 1-10
            self.BANK_L1A: ('L1A', 'sig_a', (1, 7)),   # Keys 5-11: channels 1-14
            self.BANK_L1B: ('L1B', 'sig_b', (1, 7)),   # Keys 12-18: channels 1-14
            self.BANK_L2B: ('L2', 'sig_b', (1, 6))     # Keys 19-24: channels 1-12
        }
        
        # Buffer for last read values
        self.last_values = {}
        
    def _set_channel_pins(self, pin_group, channel):
        """Set a group of select pins to represent a channel number"""
        if Constants.DEBUG:
            start_time = time.monotonic()
            
        # Calculate new pin states
        new_states = [bool((channel >> i) & 1) for i in range(4)]
        group_key = 'L1A' if pin_group == self.select_pins['L1A'] else 'L1B' if pin_group == self.select_pins['L1B'] else 'L2'
        
        # Only update pins that changed
        if new_states != self.pin_states[group_key]:
            for i, (pin, new_state) in enumerate(zip(pin_group, new_states)):
                if new_state != self.pin_states[group_key][i]:
                    pin.value = new_state
            self.pin_states[group_key] = new_states

        if Constants.DEBUG:
            print(f"[timing] Pin set time: {(time.monotonic() - start_time)*1000:.3f}ms")
            
    def read_bank(self, bank):
        """Read all key pairs in a bank sequentially"""
        if Constants.DEBUG:
            start_time = time.monotonic()
            
        # Get bank configuration
        pin_group_name, sig_name, (start_ch, num_pairs) = self.bank_config[bank]
        sig_pin = self.sig_a if sig_name == 'sig_a' else self.sig_b
        pin_group = self.select_pins[pin_group_name]
        
        # Switch bank if needed
        if bank != self.current_bank:
            if Constants.DEBUG:
                switch_start = time.monotonic()
                
            # Reset only if actually switching
            for group in self.select_pins.values():
                for pin in group:
                    pin.value = False
            for group in self.pin_states:
                self.pin_states[group] = [False] * 4
            self.current_bank = bank
            self.current_channel = None
            
            if Constants.DEBUG:
                switch_time = time.monotonic() - switch_start
                print(f"[timing] Bank switch to {bank} took: {switch_time*1000:.3f}ms")
                print(f"[timing] Time since last switch: {(switch_start - start_time)*1000:.3f}ms")
        
        readings = []
        # Read each channel pair
        for pair_idx in range(num_pairs):
            left_ch = start_ch + (pair_idx * 2)
            right_ch = left_ch + 1
            read_time = time.monotonic()
            
            # Set and read left channel
            self._set_channel_pins(pin_group, left_ch)
            left_value = sig_pin.value
            
            # Set and read right channel
            self._set_channel_pins(pin_group, right_ch)
            right_value = sig_pin.value
            
            if Constants.DEBUG:
                print(f"[timing] Key pair read at bank {bank} channel {left_ch}")
                print(f"[timing] Read time: {(time.monotonic() - read_time)*1000:.3f}ms")
                print(f"[values] Left: {left_value}, Right: {right_value}")
                
            readings.append((left_value, right_value, read_time))
            
        if Constants.DEBUG:
            scan_time = time.monotonic() - start_time
            print(f"[timing] Bank {bank} scan ({num_pairs} pairs) took: {scan_time*1000:.3f}ms")
            
        return readings

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
    """Represents the physical state of a key with normalized values"""
    # State definitions
    INACTIVE = 'inactive'
    INITIAL_CONTACT = 'contact'
    ACTIVE = 'active' 
    RELEASE = 'release'

    def __init__(self):
        self.state = self.INACTIVE
        self.values = {
            'pressure': 0.0,   # Overall pressure (0.0-1.0)
            'position': 0.0,   # Left/right position (-1.0 to 1.0)
            'strike': 0.0      # Initial strike velocity (0.0-1.0)
        }
        self.last_update = 0
        
class KeyboardHandler:
    """Handles keyboard scanning and key state management with timing diagnostics"""
    
    def __init__(self, key_multiplexer, data_processor):
        self.multiplexer = key_multiplexer
        self.processor = data_processor
        self.key_states = [KeyState() for _ in range(Constants.NUM_KEYS)]
        
        # Mapping of banks to key indices
        self.bank_key_map = {
            KeyMultiplexer.BANK_L2A: (0, 5),    # Keys 0-4
            KeyMultiplexer.BANK_L1A: (5, 12),   # Keys 5-11
            KeyMultiplexer.BANK_L1B: (12, 19),  # Keys 12-18
            KeyMultiplexer.BANK_L2B: (19, 25)   # Keys 19-24
        }
        
        # State buffers to reduce processing
        self.pressure_buffer = [0.0] * Constants.NUM_KEYS
        self.position_buffer = [0.0] * Constants.NUM_KEYS
        self.last_event_time = [0.0] * Constants.NUM_KEYS
        
    def read_keys(self):
        """Read all keys and generate events for changes"""
        events = []
        
        if Constants.DEBUG:
            scan_start = time.monotonic()
            print(f"\n[scan] Starting full keyboard scan at {scan_start:.2f}")
        
        # Scan banks in optimized order
        for bank in [KeyMultiplexer.BANK_L2A, KeyMultiplexer.BANK_L1A, 
                    KeyMultiplexer.BANK_L1B, KeyMultiplexer.BANK_L2B]:
            start_idx, end_idx = self.bank_key_map[bank]
            readings = self.multiplexer.read_bank(bank)
            
            # Process each key pair's readings
            for pair_idx, (left_raw, right_raw, read_time) in enumerate(readings):
                key_idx = start_idx + pair_idx
                if key_idx >= end_idx:
                    continue
                    
                # Convert ADC values
                left_r = self._adc_to_resistance(left_raw)
                right_r = self._adc_to_resistance(right_raw)
                
                # Process sensor data
                process_start = time.monotonic()
                key_data = self.processor.process_key_data(
                    left_r, right_r,
                    self.key_states[key_idx]
                )
                
                if Constants.DEBUG:
                    process_time = time.monotonic() - process_start
                    print(f"[timing] Key {key_idx} processing took: {process_time*1000:.3f}ms")
                    print(f"[timing] Total key latency: {(process_time - read_time)*1000:.3f}ms")
                
                # Check for state changes using buffers
                new_events = self._process_key_state(
                    key_idx, 
                    key_data,
                    read_time,
                    process_start
                )
                events.extend(new_events)
                
        if Constants.DEBUG:
            total_scan_time = time.monotonic() - scan_start
            print(f"[scan] Complete keyboard scan took: {total_scan_time*1000:.3f}ms")
            if events:
                print(f"[events] Generated {len(events)} events")
                
        return events
        
    def _process_key_state(self, key_idx, key_data, read_time, process_time):
        """Process key state changes using buffered values"""
        events = []
        key_state = self.key_states[key_idx]
        
        # Check pressure change against buffer
        pressure_change = abs(key_data['pressure'] - self.pressure_buffer[key_idx])
        position_change = abs(key_data['pitch_bend'] - self.position_buffer[key_idx])
        
        # State machine with buffered values
        if key_state.state == KeyState.INACTIVE:
            if key_data['pressure'] > Constants.ACTIVATION_THRESHOLD:
                if Constants.DEBUG:
                    print(f"[state] Key {key_idx} activated")
                    print(f"[timing] Activation latency: {(process_time - read_time)*1000:.3f}ms")
                    
                events.append((key_idx, KeyState.INITIAL_CONTACT, {
                    'strike': key_data['velocity'] / 127.0,
                    'detection_time': read_time,
                    'process_time': process_time
                }))
                key_state.state = KeyState.INITIAL_CONTACT
                
        elif key_state.state == KeyState.INITIAL_CONTACT:
            if key_data['pressure'] < Constants.RELEASE_THRESHOLD:
                key_state.state = KeyState.INACTIVE
            else:
                key_state.state = KeyState.ACTIVE
                events.append((key_idx, KeyState.ACTIVE, {
                    'pressure': key_data['pressure'],
                    'position': key_data['pitch_bend'],
                    'detection_time': read_time,
                    'process_time': process_time
                }))
                
        elif key_state.state == KeyState.ACTIVE:
            if key_data['pressure'] < Constants.RELEASE_THRESHOLD:
                if Constants.DEBUG:
                    print(f"[state] Key {key_idx} released")
                    print(f"[timing] Release latency: {(process_time - read_time)*1000:.3f}ms")
                    
                key_state.state = KeyState.RELEASE
                events.append((key_idx, KeyState.RELEASE, {
                    'pressure': 0.0,
                    'detection_time': read_time,
                    'process_time': process_time
                }))
            elif pressure_change > 0.01 or position_change > 0.01:
                if Constants.DEBUG:
                    print(f"[state] Key {key_idx} pressure/position update")
                    print(f"[timing] Update latency: {(process_time - read_time)*1000:.3f}ms")
                    
                events.append((key_idx, KeyState.ACTIVE, {
                    'pressure': key_data['pressure'],
                    'position': key_data['pitch_bend'],
                    'detection_time': read_time,
                    'process_time': process_time
                }))
                
        elif key_state.state == KeyState.RELEASE:
            key_state.state = KeyState.INACTIVE
            
        # Update buffers
        self.pressure_buffer[key_idx] = key_data['pressure']
        self.position_buffer[key_idx] = key_data['pitch_bend']
        self.last_event_time[key_idx] = process_time
            
        return events
        
    def _adc_to_resistance(self, adc_value):
        """Convert ADC reading to resistance value"""
        voltage = (adc_value / Constants.ADC_MAX) * 3.3
        if voltage >= Constants.REST_VOLTAGE_THRESHOLD:
            return float('inf')
        return Constants.ADC_RESISTANCE_SCALE * voltage / (3.3 - voltage)
