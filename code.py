import board
import busio
import digitalio
import time
import usb_midi
from hardware import (
    Multiplexer, KeyboardHandler, RotaryEncoderHandler, 
    PotentiometerHandler, Constants as HWConstants
)
from midi import MidiLogic

class Constants:
    # System Constants
    DEBUG = False
    LOG_GLOBAL = True
    LOG_HARDWARE = True
    LOG_MIDI = True
    LOG_MISC = True

    # Hardware Setup Delay
    SETUP_DELAY = 0.1

    # SPI Pins (Cartridge Interface)
    SPI_CLOCK = board.GP18
    SPI_MOSI = board.GP19
    SPI_MISO = board.GP16
    SPI_CS = board.GP17
    CART_DETECT = board.GP22

    # Scan Intervals (in seconds)
    POT_SCAN_INTERVAL = 0.02
    ENCODER_SCAN_INTERVAL = 0.001
    MAIN_LOOP_INTERVAL = 0.001

import board
import busio
import digitalio
import time

class SPIHandler:
    """Handles SPI communication to cartridge"""
    # Message Types (shared between Bartleby and Candide)
    HELLO_BART = 0xA0
    HI_CANDIDE = 0xA1
    
    def __init__(self):
        print("Initializing SPI Handler...")
        # Configure SPI bus (MIDI Controller is master)
        self.spi = busio.SPI(
            clock=Constants.SPI_CLOCK,
            MOSI=Constants.SPI_MOSI,
            MISO=Constants.SPI_MISO
        )
        self.cs = digitalio.DigitalInOut(Constants.SPI_CS)
        self.cs.direction = digitalio.Direction.OUTPUT
        self.cs.value = True  # Active low
        
        # Configure cartridge detect - now as OUTPUT
        self.detect = digitalio.DigitalInOut(Constants.CART_DETECT)
        self.detect.direction = digitalio.Direction.OUTPUT
        self.detect.value = True  # Show we're alive
        
        self.handshake_complete = False
        
        print(f"SPI Pins: CLK={Constants.SPI_CLOCK}, MOSI={Constants.SPI_MOSI}, MISO={Constants.SPI_MISO}, CS={Constants.SPI_CS}")
        print(f"Detect Pin: {Constants.CART_DETECT} set HIGH")
    
    def check_for_cartridge(self):
        """Check for cartridge saying hello"""
        buffer = bytearray(4)
        while not self.spi.try_lock():
            pass
        try:
            self.cs.value = False
            self.spi.readinto(buffer)
            self.cs.value = True
            
            if buffer[0] == self.HELLO_BART:
                print("Cartridge says: HELLO_BART")
                self.send_handshake_response()
                return True
        except Exception as e:
            print(f"SPI read error: {e}")
        finally:
            self.spi.unlock()
        return False
    
    def send_handshake_response(self):
        """Send confirmation back to cartridge"""
        print("Sending: HI_CANDIDE")
        self.send_midi_message(self.HI_CANDIDE, 0, 0, 0)
        self.handshake_complete = True
        print("Handshake complete! Ready for MIDI")

    def is_ready(self):
        """Check if handshake is complete"""
        return self.handshake_complete

    def send_midi_message(self, status_byte, data1, data2, data3=0):
        """Send a 4-byte MIDI message over SPI"""
        if not self.handshake_complete and status_byte not in [self.HELLO_BART, self.HI_CANDIDE]:
            print("No handshake yet, skipping MIDI send")
            return
            
        message = bytearray([status_byte, data1, data2, data3])
        print(f"SPI OUT: [{hex(status_byte)} {data1} {data2} {data3}]")
        
        while not self.spi.try_lock():
            pass
        try:
            self.cs.value = False
            self.spi.write(message)
        finally:
            self.cs.value = True
            self.spi.unlock()
            time.sleep(0.0001)  # Brief delay between messages
    
    def send_note_on(self, note, velocity, key_id):
        """Send note on message with key_id"""
        self.send_midi_message(0x90, note, velocity, key_id)
    
    def send_note_off(self, note, velocity, key_id):
        """Send note off message with key_id"""
        self.send_midi_message(0x80, note, velocity, key_id)
    
    def send_control_change(self, cc_number, value):
        """Send CC message"""
        self.send_midi_message(0xB0, cc_number, value)
    
    def cleanup(self):
        """Clean up resources"""
        try:
            self.detect.value = False  # Signal we're shutting down
            self.spi.deinit()
        except Exception as e:
            print(f"SPI cleanup error: {e}")

class Bartleby:
    def __init__(self):
        # System components
        self.hardware = None
        self.midi = None
        self.spi = None
        
        # Timing state
        self.current_time = 0
        self.last_pot_scan = 0
        self.last_encoder_scan = 0
        
        # Run setup
        self._setup_hardware()
        self._setup_midi()
        self._setup_initial_state()
        
    def _setup_hardware(self):
        """Initialize all hardware components"""
        self.hardware = {
            'control_mux': Multiplexer(
                HWConstants.CONTROL_MUX_SIG,
                HWConstants.CONTROL_MUX_S0,
                HWConstants.CONTROL_MUX_S1,
                HWConstants.CONTROL_MUX_S2,
                HWConstants.CONTROL_MUX_S3
            ),
            'keyboard': self._setup_keyboard(),
            'encoders': RotaryEncoderHandler(
                HWConstants.OCTAVE_ENC_CLK,
                HWConstants.OCTAVE_ENC_DT
            )
        }
        
        # Create pot handler after mux is ready
        self.hardware['pots'] = PotentiometerHandler(self.hardware['control_mux'])
        time.sleep(Constants.SETUP_DELAY)  # Allow hardware to stabilize

    def _setup_keyboard(self):
        """Initialize keyboard multiplexers and handler"""
        keyboard_l1a = Multiplexer(
            HWConstants.KEYBOARD_L1A_MUX_SIG,
            HWConstants.KEYBOARD_L1A_MUX_S0,
            HWConstants.KEYBOARD_L1A_MUX_S1,
            HWConstants.KEYBOARD_L1A_MUX_S2,
            HWConstants.KEYBOARD_L1A_MUX_S3
        )
        
        keyboard_l1b = Multiplexer(
            HWConstants.KEYBOARD_L1B_MUX_SIG,
            HWConstants.KEYBOARD_L1B_MUX_S0,
            HWConstants.KEYBOARD_L1B_MUX_S1,
            HWConstants.KEYBOARD_L1B_MUX_S2,
            HWConstants.KEYBOARD_L1B_MUX_S3
        )
        
        return KeyboardHandler(
            keyboard_l1a,
            keyboard_l1b,
            HWConstants.KEYBOARD_L2_MUX_S0,
            HWConstants.KEYBOARD_L2_MUX_S1,
            HWConstants.KEYBOARD_L2_MUX_S2,
            HWConstants.KEYBOARD_L2_MUX_S3
        )

    def _setup_midi(self):
        """Initialize MIDI and SPI"""
        self.midi = MidiLogic()
        self.spi = SPIHandler()

    def _setup_initial_state(self):
        """Set initial system state"""
        self.hardware['encoders'].reset_all_encoder_positions()
        
        # Log initial volume pot value
        initial_volume = self.hardware['pots'].normalize_value(
            self.hardware['control_mux'].read_channel(0)
        )
        print(f"P0: Volume: {0.0:.2f} -> {initial_volume:.2f}")
        
        if self.spi.is_ready():  # Changed from is_cartridge_present()
            print("Cartridge detected!")
            
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")

    def _handle_encoder_events(self, encoder_events):
        """Process encoder state changes"""
        for event in encoder_events:
            if event[0] == 'rotation':
                _, direction = event[1:3]  
                midi_events = self.midi.handle_octave_shift(direction)
                print(f"Octave shifted {direction}: new position {self.hardware['encoders'].get_encoder_position(0)}")
                # Send any MIDI events generated by octave shift
                for event in midi_events:
                    self._send_midi_event(event)

    def _send_midi_event(self, event):

        print(f"Sending MIDI event: {event}")


        """Send MIDI event to both USB and SPI"""
        event_type, *params = event
        if event_type == 'note_on':
            note, velocity, key_id = params
            self.spi.send_note_on(note, velocity, key_id)
        elif event_type == 'note_off':
            note, velocity, key_id = params
            self.spi.send_note_off(note, velocity, key_id)
        elif event_type == 'control_change':
            cc_num, value, _ = params
            self.spi.send_control_change(cc_num, value)

        # Also send to USB MIDI
        self.midi.send_midi_event(event)

    def process_hardware(self):
        """Read and process all hardware inputs"""
        self.current_time = time.monotonic()
        changes = {
            'keys': [],
            'pots': [],
            'encoders': []
        }
        
        # Always read keys at full speed
        changes['keys'] = self.hardware['keyboard'].read_keys()
        
        # Read pots at medium interval
        if self.current_time - self.last_pot_scan >= Constants.POT_SCAN_INTERVAL:
            changes['pots'] = self.hardware['pots'].read_pots()
            if changes['pots']:
                # Handle volume pot (pot 0) separately
                for pot_id, old_value, new_value in changes['pots'][:]:
                    if pot_id == 0:
                        print(f"P0: Volume: {old_value:.2f} -> {new_value:.2f}")
                        changes['pots'].remove((pot_id, old_value, new_value))
            self.last_pot_scan = self.current_time
        
        # Read encoders at fastest interval
        if self.current_time - self.last_encoder_scan >= Constants.ENCODER_SCAN_INTERVAL:
            for i in range(self.hardware['encoders'].num_encoders):
                new_events = self.hardware['encoders'].read_encoder(i)
                if new_events:
                    changes['encoders'].extend(new_events)
            if changes['encoders']:
                self._handle_encoder_events(changes['encoders'])
            self.last_encoder_scan = self.current_time
            
        return changes

    def update(self):
        """Main update loop - returns False if should stop"""
        try:
            # Process all hardware
            changes = self.process_hardware()

            # check for cart
            if not self.spi.is_ready():
                self.spi.check_for_cartridge()

            # Only process MIDI if we have changes
            if any(changes.values()):
                # Generate MIDI events
                midi_events = self.midi.update(
                    changes['keys'],
                    changes['pots'],
                    {}  # Empty config since we're not using instrument settings
                )
                
                # Send each MIDI event
                for event in midi_events:
                    self._send_midi_event(event)
            
            return True
            
        except KeyboardInterrupt:
            return False
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            return False

    def run(self):
        """Main run loop"""
        try:
            while self.update():
                time.sleep(Constants.MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean shutdown"""
        if self.spi:
            self.spi.cleanup()
        print("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁")

def main():
    controller = Bartleby()
    controller.run()

if __name__ == "__main__":
    main()