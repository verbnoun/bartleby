import board
import busio
import digitalio
import time
from hardware import (
    Multiplexer, KeyboardHandler, RotaryEncoderHandler, 
    PotentiometerHandler, Constants as HWConstants
)
from midi import MidiLogic
from connection import ConnectionManager, Constants as ConnConstants, get_precise_time, format_processing_time

class Constants:
    DEBUG = True
    SEE_HEARTBEAT = False
    
    # Hardware Setup
    SETUP_DELAY = 0.1
    
    # UART/MIDI Pins
    UART_TX = board.GP16
    UART_RX = board.GP17
    
    # Timing Intervals
    POT_SCAN_INTERVAL = 0.02
    ENCODER_SCAN_INTERVAL = 0.001
    MAIN_LOOP_INTERVAL = 0.001
    MESSAGE_TIMEOUT = 0.05

    # MIDI Settings
    UART_BAUDRATE = 31250
    UART_TIMEOUT = 0.001

class TransportManager:
    """Manages shared UART instance for both text and MIDI communication"""
    def __init__(self, tx_pin, rx_pin, baudrate=31250, timeout=0.001):
        print("Initializing shared transport...")
        self.uart = busio.UART(
            tx=tx_pin,
            rx=rx_pin,
            baudrate=baudrate,
            timeout=timeout,
            bits=8,
            parity=None,
            stop=1
        )
        self.uart_initialized = True
        print("Transport initialized")
        
    def get_uart(self):
        """Get the UART instance for text or MIDI use"""
        return self.uart
        
    def flush_buffers(self):
        """Clear any pending data in UART buffers"""
        if not self.uart_initialized:
            return
        try:
            start_time = get_precise_time()
            while (get_precise_time() - start_time) < (ConnConstants.BUFFER_CLEAR_TIMEOUT * 1_000_000_000):  # Convert to ns
                if self.uart and self.uart.in_waiting:
                    self.uart.read()
                else:
                    break
        except Exception:
            # If we hit an error trying to flush, the UART is likely already deinitialized
            pass
        
    def cleanup(self):
        """Clean shutdown of transport"""
        if self.uart_initialized:
            try:
                self.flush_buffers()
                if self.uart:
                    self.uart.deinit()
            except Exception:
                # If we hit an error, the UART is likely already deinitialized
                pass
            finally:
                self.uart = None
                self.uart_initialized = False

class TextUart:
    """Handles text-based UART communication for receiving config only"""
    def __init__(self, uart):
        self.uart = uart
        self.buffer = bytearray()
        self.last_write = 0
        print("Text protocol initialized")

    def write(self, message):
        """Write text message with minimum delay between writes"""
        current_time = get_precise_time()
        delay_needed = (Constants.MESSAGE_TIMEOUT * 1_000_000_000) - (current_time - self.last_write)  # Convert to ns
        if delay_needed > 0:
            time.sleep(delay_needed / 1_000_000_000)  # Convert back to seconds
            
        if isinstance(message, str):
            message = message.encode('utf-8')
        result = self.uart.write(message)
        self.last_write = get_precise_time()
        return result

    def read(self):
        """Read available data and return complete messages, with improved resilience"""
        try:
            # If no data waiting, return None
            if not self.uart.in_waiting:
                return None

            # Read all available data
            data = self.uart.read()
            if not data:
                return None

            # Extend existing buffer
            self.buffer.extend(data)

            # Try to find a complete message (ending with newline)
            if b'\n' in self.buffer:
                # Split on first newline
                message, self.buffer = self.buffer.split(b'\n', 1)
                
                try:
                    # Attempt to decode and strip the message
                    decoded_message = message.decode('utf-8').strip()
                    
                    # Basic sanity check: message is not empty
                    if decoded_message:
                        return decoded_message
                except UnicodeDecodeError:
                    # If decoding fails, clear buffer to prevent accumulation of garbage
                    self.buffer = bytearray()
                    print("Received non-UTF8 data, buffer cleared")

            # No complete message, return None
            return None

        except Exception as e:
            # Catch any unexpected errors
            print(f"Error in message reading: {e}")
            # Clear buffer to prevent repeated errors
            self.buffer = bytearray()
            return None

    def clear_buffer(self):
        """Clear the internal buffer"""
        self.buffer = bytearray()

    @property
    def in_waiting(self):
        try:
            return self.uart.in_waiting
        except Exception:
            return 0

class StateManager:
    def __init__(self):
        self.current_time = 0
        self.last_pot_scan = 0
        self.last_encoder_scan = 0
        
    def update_time(self):
        self.current_time = get_precise_time()
        
    def should_scan_pots(self):
        return (self.current_time - self.last_pot_scan) >= (Constants.POT_SCAN_INTERVAL * 1_000_000_000)  # Convert to ns
        
    def should_scan_encoders(self):
        return (self.current_time - self.last_encoder_scan) >= (Constants.ENCODER_SCAN_INTERVAL * 1_000_000_000)  # Convert to ns
        
    def update_pot_scan_time(self):
        self.last_pot_scan = self.current_time
        
    def update_encoder_scan_time(self):
        self.last_encoder_scan = self.current_time

class HardwareCoordinator:
    def __init__(self):
        print("Setting up hardware...")
        # Set up detect pin as output HIGH to signal presence
        self.detect_pin = digitalio.DigitalInOut(ConnConstants.DETECT_PIN)
        self.detect_pin.direction = digitalio.Direction.OUTPUT
        self.detect_pin.value = True
        
        # Initialize components
        self.components = self._initialize_components()
        time.sleep(Constants.SETUP_DELAY)
        
    def _initialize_components(self):
        control_mux = Multiplexer(
            HWConstants.CONTROL_MUX_SIG,
            HWConstants.CONTROL_MUX_S0,
            HWConstants.CONTROL_MUX_S1,
            HWConstants.CONTROL_MUX_S2,
            HWConstants.CONTROL_MUX_S3
        )
        
        keyboard = self._setup_keyboard()
        encoders = RotaryEncoderHandler(
            HWConstants.OCTAVE_ENC_CLK,
            HWConstants.OCTAVE_ENC_DT
        )
        
        return {
            'control_mux': control_mux,
            'keyboard': keyboard,
            'encoders': encoders,
            'pots': PotentiometerHandler(control_mux)
        }
    
    def _setup_keyboard(self):
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
    
    def read_hardware_state(self, state_manager):
        changes = {
            'keys': [],
            'pots': [],
            'encoders': []
        }
        
        # Always read keys at full speed
        start_time = get_precise_time()
        changes['keys'] = self.components['keyboard'].read_keys()
        if Constants.DEBUG:
            if changes['keys']:
                print(format_processing_time(start_time, "Key state read"))
        
        # Read pots at interval
        if state_manager.should_scan_pots():
            start_time = get_precise_time()
            changes['pots'] = self.components['pots'].read_pots()
            if Constants.DEBUG:
                if changes['pots']:
                    print(format_processing_time(start_time, "Potentiometer scan"))
            state_manager.update_pot_scan_time()
        
        # Read encoders at interval
        if state_manager.should_scan_encoders():
            start_time = get_precise_time()
            for i in range(self.components['encoders'].num_encoders):
                new_events = self.components['encoders'].read_encoder(i)
                if new_events:
                    changes['encoders'].extend(new_events)
            if changes['encoders']:
                print(format_processing_time(start_time, "Encoder scan"))
            state_manager.update_encoder_scan_time()
            
        return changes
    
    def handle_encoder_events(self, encoder_events, midi):
        start_time = get_precise_time()
        for event in encoder_events:
            if event[0] == 'rotation':
                _, direction = event[1:3]
                midi.handle_octave_shift(direction)
                if Constants.DEBUG:
                    print(f"Octave shifted {direction}: new position {self.components['encoders'].get_encoder_position(0)}")
                    print(format_processing_time(start_time, "Octave shift processing"))
    
    def reset_encoders(self):
        self.components['encoders'].reset_all_encoder_positions()

class Bartleby:
    def __init__(self):
        print("\nWake Up Bartleby!")
        self.state_manager = StateManager()
        
        # Initialize shared transport first
        self.transport = TransportManager(
            tx_pin=Constants.UART_TX,
            rx_pin=Constants.UART_RX,
            baudrate=Constants.UART_BAUDRATE,
            timeout=Constants.UART_TIMEOUT
        )
        
        # Get shared UART for text and MIDI
        shared_uart = self.transport.get_uart()
        self.text_uart = TextUart(shared_uart)
        self.midi = MidiLogic(
            transport_manager=self.transport,
            midi_callback=self._handle_midi_config
        )
        
        # Initialize hardware first to set up detect pin
        self.hardware = HardwareCoordinator()
        
        # Initialize connection manager with hardware's detect pin
        self.connection_manager = ConnectionManager(
            self.text_uart,
            self.hardware,
            self.midi,
            self.transport
        )
        
        self._setup_initial_state()

    def _handle_midi_config(self, message):
        self.connection_manager.handle_message(message)

    def _setup_initial_state(self):
        self.hardware.reset_encoders()
        
        # Force read of all pots during initialization
        initial_pots = self.hardware.components['pots'].read_all_pots()
        
        # Optional: Send initial pot values during initialization
        if initial_pots and Constants.DEBUG:
            print(f"Initial pot values read: {initial_pots}")
        
        # Add startup delay to ensure both sides are ready
        time.sleep(ConnConstants.STARTUP_DELAY)
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")

    def update(self):
        try:
            # Update current time
            self.state_manager.update_time()
            
            # Check connection states
            self.connection_manager.update_state()
            
            # Process hardware and MIDI
            start_time = get_precise_time()
            changes = self.hardware.read_hardware_state(self.state_manager)
            
            # In Bartleby.update():
            if self.text_uart.in_waiting:
                message = self.text_uart.read()
                if message:
                    try:
                        if Constants.DEBUG and not message.startswith('♥︎'):
                            print(f"Received message: '{message}'")
                        self.connection_manager.handle_message(message)
                    except Exception as e:
                        if str(e):
                            print(f"Received non-text data: {message}")

            # Handle encoder events and MIDI updates
            if changes['encoders']:
                self.hardware.handle_encoder_events(changes['encoders'], self.midi)
            
            # Process MIDI updates with timing
            if changes['keys'] or changes['pots'] or changes['encoders']:
                # Log total time from hardware detection to MIDI sent
                hw_detect_time = get_precise_time()
                self.midi.update(
                    changes['keys'],
                    changes['pots'],
                    {}  # Empty config since we're not using instrument settings
                )
                if Constants.DEBUG:
                    print(format_processing_time(start_time, "Total time"))
            
            return True
                
        except KeyboardInterrupt:
            return False
        except Exception as e:
            print(f"Error in main loop: {str(e)}")
            return False

    def run(self):
        print("Starting main loop...")
        try:
            while self.update():
                time.sleep(Constants.MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        print("Starting cleanup sequence...")
        if hasattr(self.hardware, 'detect_pin'):
            print("Cleaning up hardware...")
            self.hardware.detect_pin.value = False
            self.hardware.detect_pin.deinit()
        if self.connection_manager:
            self.connection_manager.cleanup()
        if self.midi:
            print("Cleaning up MIDI...")
            self.midi.cleanup()
        if self.transport:
            print("Cleaning up transport...")
            self.transport.cleanup()
        print("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁")

    def play_greeting(self):
        """Play greeting chime using MPE"""
        if Constants.DEBUG:
            print("Playing MPE greeting sequence")
            
        base_key_id = -1
        base_pressure = 0.75
        
        greeting_notes = [60, 64, 67, 72]
        velocities = [0.6, 0.7, 0.8, 0.9]
        durations = [0.2, 0.2, 0.2, 0.4]
        
        for idx, (note, velocity, duration) in enumerate(zip(greeting_notes, velocities, durations)):
            key_id = base_key_id - idx
            channel = self.midi.channel_manager.allocate_channel(key_id)
            note_state = self.midi.channel_manager.add_note(key_id, note, channel, int(velocity * 127))
            
            # Send in MPE order: CC74 → Pressure → Pitch Bend → Note On
            self.midi.message_sender.send_message([0xB0 | channel, Constants.CC_TIMBRE, Constants.TIMBRE_CENTER])
            self.midi.message_sender.send_message([0xD0 | channel, int(base_pressure * 127)])
            self.midi.message_sender.send_message([0xE0 | channel, 0x00, 0x40])  # Center pitch bend
            self.midi.message_sender.send_message([0x90 | channel, note, int(velocity * 127)])
            
            time.sleep(duration)
            
            self.midi.message_sender.send_message([0xD0 | channel, 0])  # Zero pressure
            self.midi.message_sender.send_message([0x80 | channel, note, 0])
            self.midi.channel_manager.release_note(key_id)
            
            time.sleep(0.05)

def main():
    controller = Bartleby()
    controller.run()

if __name__ == "__main__":
    main()
