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
    
    # MIDI message sizes
    PROTOCOL_MSG_SIZE = 4
    MIDI_MSG_SIZE = 4

class SPIHandler:
    """Handles SPI communication for base station with proper sync and timing"""
    # Protocol markers
    SYNC_REQUEST = 0xF0
    SYNC_ACK = 0xF1
    HELLO_BART = 0xA0
    HI_CANDIDE = 0xA1
    PROTOCOL_VERSION = 0x01

    # Message types
    MSG_TYPE_PROTOCOL = 0x00
    MSG_TYPE_MIDI = 0x01

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
        self.midi_queue = []
        
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
            baudrate=50000,  #50kHz
            polarity=1,
            phase=1
        )

        # SPI test during init
        print("\n=== Testing SPI Clock ===")
        test_data = bytearray([0xAA, 0x55, 0xAA, 0x55])
        print("Starting clock test... Check SCK (GP18) with scope")
        time.sleep(1)  # Give time to get scope ready
        try:
            # First test CS manually
            print("Testing CS control...")
            for i in range(4):
                self.cs.value = False
                print("CS LOW")
                time.sleep(3)
                self.cs.value = True
                print("CS HIGH")
                time.sleep(3)
                
            # Then test clock with data
            print("\nTesting Clock - 6 transfers...")
            for i in range(6):
                print(f"Transfer {i+1}")
                self.cs.value = False
                with self.spi_device as spi:
                    spi.write(test_data)
                self.cs.value = True
                time.sleep(3)
                
        except Exception as e:
            print(f"Test error: {str(e)}")
            self.cs.value = True  # Ensure CS released
            
        print("=== SPI Test Complete ===\n")
        
        # Separate buffers for protocol and MIDI
        self._protocol_out = bytearray(Constants.PROTOCOL_MSG_SIZE)
        self._protocol_in = bytearray(Constants.PROTOCOL_MSG_SIZE)
        self._midi_out = bytearray(Constants.MIDI_MSG_SIZE)
        self._midi_in = bytearray(Constants.MIDI_MSG_SIZE)
        
        print(f"[Base {time.monotonic():.3f}] SPI initialized, waiting for cartridge")

    def check_connection(self):
        """Main connection state machine"""
        current_time = time.monotonic()
        
        # Detect state changes
        cart_present = self.detect.value
        if cart_present and self.state == self.DISCONNECTED:
            print(f"\n[Base {current_time:.3f}] Cartridge detected - Starting sync")
            self.state = self.SYNC_STARTED
            self.sync_attempts = 0
            time.sleep(0.01)  # Give cartridge time to initialize
            return self._attempt_sync()
            
        elif not cart_present and self.state != self.DISCONNECTED:
            print(f"[Base {current_time:.3f}] Cartridge removed")
            self.reset_state()
            return False
            
        # Handle existing connection
        if self.state == self.SYNC_STARTED:
            if (current_time - self.last_sync_time) > 0.5:  # Retry every 500ms
                return self._attempt_sync()
        elif self.state == self.SYNC_COMPLETE:
            return self._start_handshake()
        elif self.state == self.CONNECTED:
            self._process_midi_queue()
            
            # Periodic connection verification
            if (current_time - self.last_sync_time) > 1.0:
                if not self._verify_connection():
                    print(f"[Base {current_time:.3f}] Connection verification failed")
                    self.reset_state()
                    return False
                self.last_sync_time = current_time
                
        return self.state == self.CONNECTED
    
    def _attempt_sync(self):
        """Attempt clock/protocol sync with cartridge"""
        current_time = time.monotonic()
        self.last_sync_time = current_time
        self.sync_attempts += 1

        if self.sync_attempts > 10:
            print(f"[Base {current_time:.3f}] Too many sync attempts - resetting")
            self.reset_state()
            return False

        try:
            # Prepare sync request - order of bytes fixed
            self._protocol_out[0] = self.SYNC_REQUEST  # Protocol marker first
            self._protocol_out[1] = self.PROTOCOL_VERSION
            self._protocol_out[2] = self.MSG_TYPE_PROTOCOL # Message type moved
            self._protocol_out[3] = 0

            # Single transaction
            with self.spi_device as spi:
                spi.write_readinto(self._protocol_out, self._protocol_in)
                
            print(f"[Base {current_time:.3f}] Write/Read: sent={list(self._protocol_out)} received={list(self._protocol_in)}")
            
            if (self._protocol_in[0] == self.MSG_TYPE_PROTOCOL and
                self._protocol_in[1] == self.SYNC_ACK and
                self._protocol_in[2] == self.PROTOCOL_VERSION):
                print(f"[Base {current_time:.3f}] Sync successful!")
                self.state = self.SYNC_COMPLETE
                return True

        except Exception as e:
            print(f"[Base {current_time:.3f}] Sync error: {str(e)}")

        return False
    
    def _start_handshake(self):
        """Begin handshake after successful sync"""
        current_time = time.monotonic()
        try:
            with self.spi_device as spi:
                spi.readinto(self._protocol_in)
                
            if (self._protocol_in[0] == self.MSG_TYPE_PROTOCOL and
                self._protocol_in[1] == self.HELLO_BART):
                return self._send_hi_candide()
                    
        except Exception as e:
            print(f"[Base {current_time:.3f}] Handshake error: {str(e)}")
            self.reset_state()
            
        return False

    def _send_hi_candide(self):
        """Complete handshake with HI_CANDIDE response"""
        current_time = time.monotonic()
        try:
            self._protocol_out[0] = self.MSG_TYPE_PROTOCOL
            self._protocol_out[1] = self.HI_CANDIDE
            self._protocol_out[2] = 0
            self._protocol_out[3] = 0
            
            with self.spi_device as spi:
                spi.write(self._protocol_out)
            
            self.state = self.CONNECTED
            print(f"[Base {current_time:.3f}] Connection established!")
            return True
                
        except Exception as e:
            print(f"[Base {current_time:.3f}] Response error: {str(e)}")
            self.reset_state()
            return False

    def _verify_connection(self):
        """Verify cartridge is still responding"""
        if self.state != self.CONNECTED:
            return False
            
        try:
            self._protocol_out[0] = self.MSG_TYPE_PROTOCOL
            self._protocol_out[1] = self.SYNC_REQUEST
            self._protocol_out[2] = 0
            self._protocol_out[3] = 0
            
            with self.spi_device as spi:
                spi.write_readinto(self._protocol_out, self._protocol_in)
            
            return (self._protocol_in[0] == self.MSG_TYPE_PROTOCOL and 
                   self._protocol_in[1] == self.SYNC_ACK)
                
        except Exception:
            return False

    def _process_midi_queue(self):
        """Process any pending MIDI messages"""
        if not self.midi_queue:
            return
            
        try:
            msg = self.midi_queue.pop(0)
            self._midi_out[0] = self.MSG_TYPE_MIDI
            self._midi_out[1:] = msg
            
            with self.spi_device as spi:
                spi.write(self._midi_out)
                
        except Exception as e:
            print(f"[Base {time.monotonic():.3f}] MIDI send error: {str(e)}")

    def queue_midi_message(self, msg):
        """Add MIDI message to transmission queue"""
        if len(msg) <= 3:  # Ensure message fits in remaining buffer space
            self.midi_queue.append(msg)

    def reset_state(self):
        """Reset to initial state"""
        self.state = self.DISCONNECTED
        self.sync_attempts = 0
        self.midi_queue.clear()
        print(f"[Base {time.monotonic():.3f}] Reset to initial state")

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
        
        if self.spi.is_ready():
            print("Cartridge detected!")
            
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")

    def _handle_encoder_events(self, encoder_events):
        """Process encoder state changes"""
        for event in encoder_events:
            if event[0] == 'rotation':
                _, direction = event[1:3]  
                midi_events = self.midi.handle_octave_shift(direction)
                print(f"Octave shifted {direction}: new position {self.hardware['encoders'].get_encoder_position(0)}")
                for event in midi_events:
                    self._send_midi_event(event)

    def _send_midi_event(self, event):
        """Send MIDI event to both USB and SPI"""
        print(f"Sending MIDI event: {event}")
        event_type, *params = event

        # Send to cartridge via SPI
        if self.spi.is_ready():
            if event_type == 'note_on':
                note, velocity, key_id = params
                self.spi.queue_midi_message(bytearray([0x90, note, velocity]))
            elif event_type == 'note_off':
                note, velocity, key_id = params
                self.spi.queue_midi_message(bytearray([0x80, note, velocity]))
            elif event_type == 'control_change':
                cc_num, value, _ = params
                self.spi.queue_midi_message(bytearray([0xB0, cc_num,value]))

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
            
            # Process MIDI events if hardware has changed and we're connected
            if any(changes.values()) and self.spi.is_ready():
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