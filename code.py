import time
from constants import (
    DEBUG, MAIN_LOOP_INTERVAL, UART_TX, UART_RX,
    UART_BAUDRATE, UART_TIMEOUT, CC_TIMBRE, TIMBRE_CENTER,
    STARTUP_DELAY
)
from logging import log, TAG_MAIN, TAG_HW, TAG_MIDI, TAG_TRANS
from connection import get_precise_time, format_processing_time
from transport import TransportManager, TextUart
from state import StateManager
from coordinator import HardwareCoordinator
from connection import ConnectionManager
from midi import MidiLogic

class Bartleby:
    def __init__(self):
        print("\nWake Up Bartleby!")  # Keep critical system message
        self.state_manager = StateManager()
        
        # Initialize shared transport first
        self.transport = TransportManager(
            tx_pin=UART_TX,
            rx_pin=UART_RX,
            baudrate=UART_BAUDRATE,
            timeout=UART_TIMEOUT
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
        
        # Force read of all pots during initialization but don't send MIDI
        initial_pots = self.hardware.components['pots'].read_all_pots()
        
        # Log initial pot values for debugging only
        if initial_pots and DEBUG:
            log(TAG_MAIN, f"Initial pot values read: {initial_pots}")
        
        # Add startup delay to ensure both sides are ready
        time.sleep(STARTUP_DELAY)
        print("\nBartleby (v1.0) is awake... (◕‿◕✿)")  # Keep critical system message

    def update(self):
        try:
            # Update current time
            self.state_manager.update_time()
            
            # Check connection states
            self.connection_manager.update_state()
            
            # Process hardware and MIDI
            start_time = get_precise_time()
            changes = self.hardware.read_hardware_state(self.state_manager)
            
            # Process incoming messages
            if self.text_uart.in_waiting:
                message = self.text_uart.read()
                if message:
                    try:
                        if DEBUG and not message.startswith('♡'):
                            log(TAG_MAIN, f"Received message: '{message}'")
                        self.connection_manager.handle_message(message)
                    except Exception as e:
                        if str(e):
                            log(TAG_MAIN, f"Received non-text data: {message}", is_error=True)

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
                if DEBUG:
                    log(TAG_MAIN, format_processing_time(start_time, "Total time"))
            
            return True
                
        except KeyboardInterrupt:
            return False
        except Exception as e:
            log(TAG_MAIN, f"Error in main loop: {str(e)}", is_error=True)
            return False

    def run(self):
        print("Starting main loop...")  # Keep critical system message
        try:
            while self.update():
                time.sleep(MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        print("Starting cleanup sequence...")  # Keep critical system message
        if hasattr(self.hardware, 'detect_pin'):
            log(TAG_HW, "Cleaning up hardware...")
            self.hardware.detect_pin.value = False
            self.hardware.detect_pin.deinit()
        if self.connection_manager:
            self.connection_manager.cleanup()
        if self.midi:
            log(TAG_MIDI, "Cleaning up MIDI...")
            self.midi.cleanup()
        if self.transport:
            log(TAG_TRANS, "Cleaning up transport...")
            self.transport.cleanup()
        print("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁")  # Keep critical system message

    def play_greeting(self):
        """Play greeting chime using MPE"""
        if DEBUG:
            log(TAG_MIDI, "Playing MPE greeting sequence")
            
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
            self.midi.message_sender.send_message([0xB0 | channel, CC_TIMBRE, TIMBRE_CENTER])
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
