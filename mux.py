import time
import digitalio
import analogio

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
