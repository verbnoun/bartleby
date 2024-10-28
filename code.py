import board
import busio
import digitalio
import time
from adafruit_bus_device.spi_device import SPIDevice
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

class SPIHandler:
    """Handles SPI communication for base station with proper sync and timing"""
    # Protocol markers
    SYNC_REQUEST = 0xF0
    SYNC_ACK = 0xF1
    HELLO_BART = 0xA0
    HI_CANDIDE = 0xA1
    PROTOCOL_VERSION = 0x01

    # States
    DISCONNECTED = 0
    SYNC_STARTED = 1
    SYNC_COMPLETE = 2
    HANDSHAKE_STARTED = 3
    CONNECTED = 4
    
    def __init__(self):
        print("Initializing SPI Handler (Base Station)...")
        
        self.state = self.DISCONNECTED
        self.sync_attempts = 0
        self.last_sync_time = 0
        
        # Configure detect pin as INPUT for cartridge detection
        self.detect = digitalio.DigitalInOut(Constants.CART_DETECT)
        self.detect.direction = digitalio.Direction.INPUT
        self.detect.pull = digitalio.Pull.DOWN
        
        # Configure SPI - Base station is master
        self.spi_bus = busio.SPI(
            clock=Constants.SPI_CLOCK,
            MOSI=Constants.SPI_MOSI,
            MISO=Constants.SPI_MISO
        )
        
        # Configure chip select as DigitalInOut
        self.cs = digitalio.DigitalInOut(Constants.SPI_CS)
        self.cs.direction = digitalio.Direction.OUTPUT
        self.cs.value = True  # Active low, so initialize high
        
        # Create SPIDevice instance with properly configured chip select
        self.spi_device = SPIDevice(
            self.spi_bus,
            chip_select=self.cs,
            baudrate=1000000,  # 1MHz to match Candide
            polarity=0,
            phase=0
        )
        
        self._out_buffer = bytearray(4)
        self._in_buffer = bytearray(4)
        
        print("[Base] SPI initialized, waiting for cartridge")

    def check_connection(self):
        """Main connection state machine"""
        current_time = time.monotonic()
        
        # Detect state changes
        cart_present = self.detect.value
        if cart_present and self.state == self.DISCONNECTED:
            print("\n[Base] Cartridge detected - Starting sync")
            self.state = self.SYNC_STARTED
            self.sync_attempts = 0
            time.sleep(0.01)  # Give cartridge time to initialize
            return self._attempt_sync()
            
        elif not cart_present and self.state != self.DISCONNECTED:
            print("[Base] Cartridge removed")
            self.reset_state()
            return False
            
        # Handle existing connection
        if self.state == self.SYNC_STARTED:
            if (current_time - self.last_sync_time) > 0.5:  # Retry every 500ms
                return self._attempt_sync()
        elif self.state == self.SYNC_COMPLETE:
            return self._start_handshake()
        elif self.state == self.CONNECTED:
            # Periodic connection verification
            if (current_time - self.last_sync_time) > 1.0:
                if not self._verify_connection():
                    print("[Base] Connection verification failed")
                    self.reset_state()
                    return False
                self.last_sync_time = current_time
                
        return self.state == self.CONNECTED
    
    def _attempt_sync(self):
        """Attempt clock/protocol sync with cartridge"""
        self.last_sync_time = time.monotonic()
        self.sync_attempts += 1

        if self.sync_attempts > 10:
            print("[Base] Too many sync attempts - resetting")
            self.reset_state()
            return False

        try:
            # Prepare sync request
            self._out_buffer[0] = self.SYNC_REQUEST
            self._out_buffer[1] = self.PROTOCOL_VERSION
            self._out_buffer[2] = 0
            self._out_buffer[3] = 0

            # Single transaction - no sleep between write/read
            with self.spi_device as spi:
                spi.write_readinto(self._out_buffer, self._in_buffer)
                
            print(f"[Base] Write/Read: sent={list(self._out_buffer)} received={list(self._in_buffer)}")
            
            if (self._in_buffer[0] == self.SYNC_ACK and
                self._in_buffer[1] == self.PROTOCOL_VERSION):
                print("[Base] Sync successful!")
                self.state = self.SYNC_COMPLETE
                return True

        except Exception as e:
            print(f"[Base] Sync error: {str(e)}")

        return False
    
    def _start_handshake(self):
        """Begin handshake after successful sync"""
        try:
            # Wait for HELLO_BART in a single transaction
            with self.spi_device as spi:
                spi.readinto(self._in_buffer)
                
            if self._in_buffer[0] == self.HELLO_BART:
                return self._send_hi_candide()
                    
        except Exception as e:
            print(f"[Base] Handshake error: {str(e)}")
            self.reset_state()
            
        return False

    def _send_hi_candide(self):
        """Complete handshake with HI_CANDIDE response"""
        try:
            self._out_buffer = bytearray([self.HI_CANDIDE, 0, 0, 0])
            
            with self.spi_device as spi:
                spi.write(self._out_buffer)
                time.sleep(0.01)  # Give Candide time to process
            
            self.state = self.CONNECTED
            print("[Base] Connection established!")
            return True
                
        except Exception as e:
            print(f"[Base] Response error: {str(e)}")
            self.reset_state()
            return False

    def _verify_connection(self):
        """Verify cartridge is still responding"""
        if self.state != self.CONNECTED:
            return False
            
        try:
            self._out_buffer = bytearray([self.SYNC_REQUEST, 0, 0, 0])
            
            with self.spi_device as spi:
                spi.write(self._out_buffer)
                time.sleep(0.01)  # Wait for Candide to process
                spi.readinto(self._in_buffer)
            
            return self._in_buffer[0] == self.SYNC_ACK
                
        except Exception:
            return False

    def reset_state(self):
        """Reset to initial state"""
        self.state = self.DISCONNECTED
        self.sync_attempts = 0
        print("[Base] Reset to initial state")

    def is_ready(self):
        """Check if connection is established"""
        return self.state == self.CONNECTED

    def cleanup(self):
        """Clean shutdown"""
        self.reset_state()
        time.sleep(0.1)
        self.spi_bus.deinit()

class Bartleby:
    def __init__(self):
        print("\nInitializing Bartleby...")
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

            # Check for cartridge connection
            if not self.spi.is_ready():
                self.spi.check_connection()

            # Only process MIDI if we have changes
            # if any(changes.values()):
            #     # Generate MIDI events
            #     midi_events = self.midi.update(
            #         changes['keys'],
            #         changes['pots'],
            #         {}  # Empty config since we're not using instrument settings
            #     )
                
            #     # Send each MIDI event
            #     for event in midi_events:
            #         self._send_midi_event(event)
            
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
