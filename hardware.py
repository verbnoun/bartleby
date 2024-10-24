import board
import time
import digitalio
import analogio

class Constants:
    # ADC Constants 
    ADC_MAX = 65535
    ADC_MIN = 1

    
    # Pin Definitions
    ROTENC_MUX_SIG = board.GP28
    ROTENC_MUX_S0 = board.GP3
    ROTENC_MUX_S1 = board.GP4
    ROTENC_MUX_S2 = board.GP5
    ROTENC_MUX_S3 = board.GP6
 
    POT_MUX_SIG = board.GP27
    POT_MUX_S0 = board.GP7
    POT_MUX_S1 = board.GP8
    POT_MUX_S2 = board.GP9
    POT_MUX_S3 = board.GP10
    
    KEYBOARD_L1_MUX_SIG = board.GP26
    KEYBOARD_L1_MUX_S0 = board.GP11
    KEYBOARD_L1_MUX_S1 = board.GP12
    KEYBOARD_L1_MUX_S2 = board.GP13
    KEYBOARD_L1_MUX_S3 = board.GP14

    KEYBOARD_L2_MUX_S0 = board.GP16
    KEYBOARD_L2_MUX_S1 = board.GP17
    KEYBOARD_L2_MUX_S2 = board.GP18
    KEYBOARD_L2_MUX_S3 = board.GP19
    
    # Potentiometer Constants
    POT_THRESHOLD = 800
    POT_LOWER_TRIM = 0.05
    POT_UPPER_TRIM = 0.0
    NUM_POTS = 10
    
    # Keyboard Handler Constants
    NUM_KEYS = 25
    NUM_CHANNELS = 50
    ALPHA = 0.05
    MAX_VK_RESISTANCE = 10000
    MIN_VK_RESISTANCE = 5000
    ADC_RESISTANCE_SCALE = 5000 # Lower scaling factor to make more sensitive 

    
    # Timing Constants
    UPDATE_INTERVAL = 0.001

class Multiplexer:
    def __init__(self, sig_pin, s0_pin, s1_pin, s2_pin, s3_pin):
        self.sig = analogio.AnalogIn(sig_pin)
        self.select_pins = [
            digitalio.DigitalInOut(pin) for pin in (s0_pin, s1_pin, s2_pin, s3_pin)
        ]
        for pin in self.select_pins:
            pin.direction = digitalio.Direction.OUTPUT

    def select_channel(self, channel):
        for i, pin in enumerate(self.select_pins):
            pin.value = (channel >> i) & 1

    def read_channel(self, channel):
        self.select_channel(channel)
        return self.sig.value
    
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
    def __init__(self, multiplexer, num_encoders=4):
        self.multiplexer = multiplexer
        self.num_encoders = num_encoders
        self.clk_last_states = [False] * num_encoders
        self.encoder_positions = [0] * num_encoders
        self.channel_read_delay = 0.0001
        self.min_position = 0
        self.max_position = 3  # 4 modes (0-3)
        self.reset_all_encoder_positions()

    def reset_all_encoder_positions(self):
        for i in range(self.num_encoders):
            self.reset_encoder_position(i)

    def reset_encoder_position(self, encoder_num):
        self.encoder_positions[encoder_num] = 0
        self.clk_last_states[encoder_num] = False

    def read_encoder(self, encoder_num):
        events = []
        base_channel = encoder_num * 3

        clk_state = self._read_digital(base_channel)
        time.sleep(self.channel_read_delay)
        dt_state = self._read_digital(base_channel + 1)
        time.sleep(self.channel_read_delay)

        # print(f"ENC {encoder_num}: CLK={clk_state} DT={dt_state}")

        if clk_state != self.clk_last_states[encoder_num]:
            direction = -1 if dt_state != clk_state else 1
            new_position = self.encoder_positions[encoder_num] + direction
            new_position = max(self.min_position, min(self.max_position, new_position))
            self.encoder_positions[encoder_num] = new_position
            events.append(('rotation', encoder_num, direction, new_position))
            # self._log_rotation(encoder_num, direction)

        self.clk_last_states[encoder_num] = clk_state
        return events

    def _read_digital(self, channel):
        value = self.multiplexer.read_channel(channel)
        return value > 32767

    def get_encoder_position(self, encoder_num):
        return self.encoder_positions[encoder_num]

class PotentiometerHandler:
    def __init__(self, multiplexer):
        self.multiplexer = multiplexer
        self.last_reported_values = [0] * Constants.NUM_POTS
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
        
        return round(normalized, 5)

    def read_pots(self):
        changed_pots = []

        for i in range(Constants.NUM_POTS):
            raw_value = self.multiplexer.read_channel(i)

            # print(f"POT {i}: {raw_value}")

            change = abs(raw_value - self.last_reported_values[i])

            if self.is_active[i]:
                if change != 0:
                    normalized_old = self.normalize_value(self.last_reported_values[i])
                    normalized_new = self.normalize_value(raw_value)
                    changed_pots.append((i, normalized_old, normalized_new))
                    self.last_reported_values[i] = raw_value
                    self.last_change[i] = change
                    pot_values = [self.normalize_value(val) for val in self.last_reported_values]
                elif change < Constants.POT_THRESHOLD:
                    self.is_active[i] = False
            elif change > Constants.POT_THRESHOLD:
                self.is_active[i] = True
                normalized_old = self.normalize_value(self.last_reported_values[i])
                normalized_new = self.normalize_value(raw_value)
                changed_pots.append((i, normalized_old, normalized_new))
                self.last_reported_values[i] = raw_value
                self.last_change[i] = change
                pot_values = [self.normalize_value(val) for val in self.last_reported_values]

        return changed_pots

class KeyboardHandler:
    def __init__(self, key_multiplexer):
        self.key_multiplexer = key_multiplexer
        self.channels = {}
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

    def read_keys(self):
        changed_keys = []
        current_active_keys = []
        self.key_hardware_data.clear()

        raw_values = self.key_multiplexer.scan_keyboard()
        
        for i in range(Constants.NUM_KEYS):  
            left_channel = i * 2
            right_channel = i * 2 + 1
            
            if left_channel < len(raw_values) and right_channel < len(raw_values):
                left_resistance = self.adc_to_resistance(raw_values[left_channel])
                right_resistance = self.adc_to_resistance(raw_values[right_channel])

                print(f"Key {i}: L={left_resistance}Ω R={right_resistance}Ω")

                left_normalized = self.normalize_resistance(left_resistance)
                right_normalized = self.normalize_resistance(right_resistance)

                if left_normalized > 0.1 or right_normalized > 0.1:
                    current_active_keys.append(i)

                self.key_hardware_data[i] = (left_normalized, right_normalized)

                if (left_normalized, right_normalized) != self.key_states[i]:
                    self.key_states[i] = (left_normalized, right_normalized)
                    changed_keys.append((i, left_normalized, right_normalized))

        self._update_active_keys(current_active_keys)
        return changed_keys

    def _update_active_keys(self, current_active_keys):
        self.active_keys = current_active_keys

    def _format_key_hardware_data(self):
        return {k: {"L": v[0], "R": v[1]} for k, v in self.key_hardware_data.items()}

    @staticmethod
    def calculate_pitch_bend(left_pressure, right_pressure):
        pressure_diff = right_pressure - left_pressure
        max_pressure = max(left_pressure, right_pressure)
        if max_pressure == 0:
            return 0
        normalized_diff = pressure_diff / max_pressure
        return max(-1, min(1, normalized_diff))  # Ensure the result is between -1 and 1
