import board
import time
import digitalio
import analogio

class Constants:
    # ADC Constants 
    ADC_MAX = 65535
    ADC_MIN = 1
    
    # Pin Definitions
    KEYBOARD_L1A_MUX_SIG = board.GP26
    KEYBOARD_L1A_MUX_S0 = board.GP3
    KEYBOARD_L1A_MUX_S1 = board.GP4
    KEYBOARD_L1A_MUX_S2 = board.GP5
    KEYBOARD_L1A_MUX_S3 = board.GP6

    KEYBOARD_L1B_MUX_SIG = board.GP27
    KEYBOARD_L1B_MUX_S0 = board.GP7
    KEYBOARD_L1B_MUX_S1 = board.GP8
    KEYBOARD_L1B_MUX_S2 = board.GP9
    KEYBOARD_L1B_MUX_S3 = board.GP10

    KEYBOARD_L2_MUX_S0 = board.GP11
    KEYBOARD_L2_MUX_S1 = board.GP12
    KEYBOARD_L2_MUX_S2 = board.GP13
    KEYBOARD_L2_MUX_S3 = board.GP14

    CONTROL_MUX_SIG = board.GP28
    CONTROL_MUX_S0 = board.GP16
    CONTROL_MUX_S1 = board.GP17
    CONTROL_MUX_S2 = board.GP18
    CONTROL_MUX_S3 = board.GP19
    
    # Encoder GPIO Pins
    OCTAVE_ENC_CLK = board.GP20
    OCTAVE_ENC_DT = board.GP21
    INSTRUMENT_ENC_CLK = board.GP22
    INSTRUMENT_ENC_DT = board.GP15

    # Potentiometer Constants
    POT_THRESHOLD = 1500  # Threshold for initial pot activation
    POT_CHANGE_THRESHOLD = 400  # Threshold for subsequent changes when pot is active
    POT_LOWER_TRIM = 0.05
    POT_UPPER_TRIM = 0.0
    NUM_POTS = 14
    
    # Keyboard Handler Constants
    NUM_KEYS = 25
    NUM_CHANNELS = 50
    ALPHA = 0.05
    MAX_VK_RESISTANCE = 50000
    MIN_VK_RESISTANCE = 500
    ADC_RESISTANCE_SCALE = 5000 # Lower scaling factor to make more sensitive 

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
    
class KeyMultiplexer:
    def __init__(self, l1_sig_pin, l1_s0_pin, l1_s1_pin, l1_s2_pin, l1_s3_pin, 
                 l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin):
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
        pins = self.l1_select_pins if level == 1 else self.l2_select_pins
        for i, pin in enumerate(pins):
            pin.value = (channel >> i) & 1

    def read_channel(self):
        return self.sig.value

    def scan_keyboard(self):
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

class RotaryEncoderHandler:
    def __init__(self, octave_clk_pin, octave_dt_pin, instrument_clk_pin, instrument_dt_pin):
        # Create pins for each encoder
        self.encoder_pins = [
            (digitalio.DigitalInOut(octave_clk_pin), digitalio.DigitalInOut(octave_dt_pin)),
            (digitalio.DigitalInOut(instrument_clk_pin), digitalio.DigitalInOut(instrument_dt_pin))
        ]
        
        # Configure all pins as inputs with pull-ups
        for clk_pin, dt_pin in self.encoder_pins:
            for pin in (clk_pin, dt_pin):
                pin.direction = digitalio.Direction.INPUT
                pin.pull = digitalio.Pull.UP
        
        self.num_encoders = 2
        self.min_position = 0
        self.max_position = 3  # 4 modes (0-3)
        
        # Initialize state tracking
        self.encoder_positions = [0] * self.num_encoders
        self.last_states = [(True, True)] * self.num_encoders  # Store both CLK and DT states
        
        self.reset_all_encoder_positions()

    def reset_all_encoder_positions(self):
        for i in range(self.num_encoders):
            self.reset_encoder_position(i)

    def reset_encoder_position(self, encoder_num):
        if 0 <= encoder_num < self.num_encoders:
            self.encoder_positions[encoder_num] = 0
            # Read and store initial states
            clk_pin, dt_pin = self.encoder_pins[encoder_num]
            self.last_states[encoder_num] = (clk_pin.value, dt_pin.value)

    def read_encoder(self, encoder_num):
        if not 0 <= encoder_num < self.num_encoders:
            return []

        events = []
        clk_pin, dt_pin = self.encoder_pins[encoder_num]
        
        # Read current states
        clk_state = clk_pin.value
        dt_state = dt_pin.value
        
        # Get previous states
        last_clk, last_dt = self.last_states[encoder_num]
        
        # Only process if CLK has changed
        if clk_state != last_clk:
            # Determine direction based on CLK and DT states
            if clk_state == False:  # CLK falling edge
                direction = 1 if dt_state != last_dt else -1
                
                # Update position with bounds checking
                current_pos = self.encoder_positions[encoder_num]
                new_pos = max(self.min_position, min(self.max_position, 
                                                   current_pos + direction))
                
                # Only generate event if position actually changed
                if new_pos != current_pos:
                    self.encoder_positions[encoder_num] = new_pos
                    events.append(('rotation', encoder_num, direction, new_pos))
                    print(f"E{encoder_num}: Position: {current_pos} -> {new_pos}")
        
        # Save current states for next iteration
        self.last_states[encoder_num] = (clk_state, dt_state)
        
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

class KeyboardHandler:
    def __init__(self, l1a_multiplexer, l1b_multiplexer, l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin):
        self.l1a_mux = l1a_multiplexer
        self.l1b_mux = l1b_multiplexer
        
        # Initialize level 2 select pins following KeyMultiplexer pattern
        self.l2_select_pins = [
            digitalio.DigitalInOut(pin) for pin in (l2_s0_pin, l2_s1_pin, l2_s2_pin, l2_s3_pin)
        ]
        for pin in self.l2_select_pins:
            pin.direction = digitalio.Direction.OUTPUT
            pin.value = False
            
        self.key_states = [(0, 0)] * Constants.NUM_KEYS
        self.active_keys = []
        self.key_hardware_data = {}
        
    def adc_to_resistance(self, adc_value):
        voltage = (adc_value / Constants.ADC_MAX) * 3.3
        if voltage >= 3.0:  # More lenient threshold for "no touch"
            return float('inf')
        return Constants.ADC_RESISTANCE_SCALE * voltage / (3.3 - voltage)
        
    def normalize_resistance(self, resistance):
        if resistance >= Constants.MAX_VK_RESISTANCE:
            return 0
        if resistance <= Constants.MIN_VK_RESISTANCE:
            return 1
        return (Constants.MAX_VK_RESISTANCE - resistance) / (Constants.MAX_VK_RESISTANCE - Constants.MIN_VK_RESISTANCE)
        
    def set_l2_channel(self, channel):
        for i, pin in enumerate(self.l2_select_pins):
            pin.value = (channel >> i) & 1
            
    def read_keys(self):
        changed_keys = []
        current_active_keys = []
        self.key_hardware_data.clear()
        
        # Read first 5 keys (1-5) from L2 Mux A through L1 Mux A channel 0
        key_index = 0  # Start with key 1 (zero-based index)
        for channel in range(1, 11, 2):  # Channels 1-10 in pairs
            self.set_l2_channel(channel)
            time.sleep(0.0001)  # Allow mux to settle
            left_value = self.l1a_mux.read_channel(0)  # Read through L1A channel 0
            
            self.set_l2_channel(channel + 1)
            time.sleep(0.0001)
            right_value = self.l1a_mux.read_channel(0)
            
            self._process_key_reading(key_index, left_value, right_value, current_active_keys, changed_keys)
            key_index += 1
            
        # Read next 7 keys (6-12) directly from L1 Mux A
        for channel in range(1, 15, 2):  # Channels 1-14 in pairs
            left_value = self.l1a_mux.read_channel(channel)
            right_value = self.l1a_mux.read_channel(channel + 1)
            self._process_key_reading(key_index, left_value, right_value, current_active_keys, changed_keys)
            key_index += 1
            
        # Read next 7 keys (13-19) directly from L1 Mux B
        for channel in range(1, 15, 2):  # Channels 1-14 in pairs
            left_value = self.l1b_mux.read_channel(channel)
            right_value = self.l1b_mux.read_channel(channel + 1)
            self._process_key_reading(key_index, left_value, right_value, current_active_keys, changed_keys)
            key_index += 1
            
        # Read final 6 keys (20-25) from L2 Mux B through L1 Mux B channel 0
        for channel in range(1, 13, 2):  # Channels 1-12 in pairs
            self.set_l2_channel(channel)
            time.sleep(0.0001)
            left_value = self.l1b_mux.read_channel(0)  # Read through L1B channel 0
            
            self.set_l2_channel(channel + 1)
            time.sleep(0.0001)
            right_value = self.l1b_mux.read_channel(0)
            
            self._process_key_reading(key_index, left_value, right_value, current_active_keys, changed_keys)
            key_index += 1
            
        self._update_active_keys(current_active_keys)
        return changed_keys
        
    def _process_key_reading(self, key_index, left_value, right_value, current_active_keys, changed_keys):
        left_resistance = self.adc_to_resistance(left_value)
        right_resistance = self.adc_to_resistance(right_value)
        
        left_normalized = self.normalize_resistance(left_resistance)
        right_normalized = self.normalize_resistance(right_resistance)
        
        if left_normalized > 0.1 or right_normalized > 0.1:
            # print(f"Key {key_index}: L={left_value} R={right_value}")
            current_active_keys.append(key_index)
            
        self.key_hardware_data[key_index] = (left_normalized, right_normalized)
        
        if (left_normalized, right_normalized) != self.key_states[key_index]:
            self.key_states[key_index] = (left_normalized, right_normalized)
            changed_keys.append((key_index, left_normalized, right_normalized))
            
    def _update_active_keys(self, current_active_keys):
        self.active_keys = current_active_keys
        
    def format_key_hardware_data(self):
        return {k: {"L": v[0], "R": v[1]} for k, v in self.key_hardware_data.items()}
        
    @staticmethod
    def calculate_pitch_bend(left_pressure, right_pressure):
        pressure_diff = right_pressure - left_pressure
        max_pressure = max(left_pressure, right_pressure)
        if max_pressure == 0:
            return 0
        normalized_diff = pressure_diff / max_pressure
        return max(-1, min(1, normalized_diff))  # Ensure the result is between -1 and 1
