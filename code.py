"""Main program entry point for Bartleby synthesizer."""

import time
import sys
import random
import digitalio
from constants import (
    MAIN_LOOP_INTERVAL, UART_TX, UART_RX,
    UART_BAUDRATE, UART_TIMEOUT, CC_TIMBRE, TIMBRE_CENTER,
    STARTUP_DELAY, DETECT_PIN
)
from logging import (
    log, TAG_BARTLEBY, TAG_HW, TAG_MIDI, TAG_TRANS,
    COLOR_CYAN, COLOR_BLUE, COLOR_MAGENTA, COLOR_GREEN, COLOR_YELLOW, COLOR_RESET
)
from transport import TransportManager, TextUart
from state import StateManager
from coordinator import HardwareCoordinator
from connection import ConnectionManager
from midi import MidiLogic
from display import DisplayManager

def _cycle_log(message):
    """Special logging effect for startup messages."""
    COLORS = [COLOR_CYAN, COLOR_BLUE, COLOR_MAGENTA, COLOR_GREEN, COLOR_YELLOW]
    
    print("\033[s", end='', file=sys.stderr)
    
    for i in range(10):
        colored_text = ""
        for char in message:
            colored_text += random.choice(COLORS) + char
        
        if i == 0:
            print(f"{colored_text}{COLOR_RESET}", file=sys.stderr)
        else:
            print(f"\033[u\033[K{colored_text}{COLOR_RESET}", file=sys.stderr)
        time.sleep(0.1)

class Bartleby:
    def __init__(self):
        _cycle_log("\nWake Up Bartleby!\n")
        try:
            self.state_manager = StateManager()
            log(TAG_BARTLEBY, "State manager initialized")
            
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
            log(TAG_BARTLEBY, "Transport and MIDI systems initialized")
            
            # Initialize hardware first to set up detect pin
            self.hardware = HardwareCoordinator()
            log(TAG_BARTLEBY, "Hardware coordinator initialized")
            
            # Initialize displays independently
            self.displays = DisplayManager()
            if self.displays.is_ready():
                self.displays.show_text_all("Bartleby")  # Show initial greeting
            
            # Initialize connection manager with hardware's detect pin and display
            self.connection_manager = ConnectionManager(
                self.text_uart,
                self.hardware,
                self.midi,
                self.transport,
                self.displays
            )
            log(TAG_BARTLEBY, "Connection manager initialized")
            
            self._setup_initial_state()
        except Exception as e:
            log(TAG_BARTLEBY, f"Initialization failed: {str(e)}", is_error=True)
            raise

    def _handle_midi_config(self, message):
        self.connection_manager.handle_message(message)

    def _setup_initial_state(self):
        try:
            self.hardware.reset_encoders()
            log(TAG_BARTLEBY, "Encoders reset")
            
            # Force read of all pots during initialization but don't send MIDI
            initial_pots = self.hardware.components['pots'].read_all_pots()
            log(TAG_BARTLEBY, f"Initial pot values read: {initial_pots}")
            
            # Add startup delay to ensure both sides are ready
            time.sleep(STARTUP_DELAY)
            
            # Show wake message
            _cycle_log("\nBartleby (v1.0) is awake... (◕‿◕✿)\n")
            
            # Now that everything is initialized and ready, set up detect pin
            self.detect_pin = digitalio.DigitalInOut(DETECT_PIN)
            self.detect_pin.direction = digitalio.Direction.OUTPUT
            self.detect_pin.value = True
            log(TAG_BARTLEBY, "Detect pin enabled - ready for configuration")
            
        except Exception as e:
            log(TAG_BARTLEBY, f"Initial state setup failed: {str(e)}", is_error=True)
            raise

    def update(self):
        try:
            # Update current time
            self.state_manager.update_time()
            
            # Check connection states
            self.connection_manager.update_state()
            
            # Process hardware and MIDI
            changes = self.hardware.read_hardware_state(self.state_manager)
            
            # Process incoming messages
            if self.text_uart.in_waiting:
                message = self.text_uart.read()
                if message:
                    try:
                        if not message.startswith('♡'):
                            log(TAG_BARTLEBY, f"Received message: '{message}'")
                        self.connection_manager.handle_message(message)
                    except Exception as e:
                        log(TAG_BARTLEBY, f"Error processing message '{message}': {str(e)}", is_error=True)

            # Handle encoder events and MIDI updates
            if changes['encoders']:
                self.hardware.handle_encoder_events(changes['encoders'], self.midi)
            
            # Process MIDI updates and display changes
            if changes['keys'] or changes['pots'] or changes['encoders']:
                self.midi.update(
                    changes['keys'],
                    changes['pots'],
                    {}  # Empty config since we're not using instrument settings
                )
                
                # Update displays if pots changed
                if changes['pots'] and self.displays.is_ready():
                    # Get current normalized values for all pots
                    all_pots = self.hardware.components['pots'].last_normalized_values
                    
                    # Update each display with its 4 pot values
                    for display_idx in range(4):  # Update first 4 displays
                        start_idx = display_idx * 4
                        display_pots = all_pots[start_idx:start_idx + 4]
                        self.displays.show_pot_values(display_idx, display_pots)
            
            return True
                
        except KeyboardInterrupt:
            return False
        except Exception as e:
            log(TAG_BARTLEBY, f"Error in main loop: {str(e)}", is_error=True)
            return False

    def run(self):
        log(TAG_BARTLEBY, "Starting main loop...")
        try:
            while self.update():
                time.sleep(MAIN_LOOP_INTERVAL)
        finally:
            self.cleanup()

    def cleanup(self):
        log(TAG_BARTLEBY, "Starting cleanup sequence...")
        try:
            if hasattr(self, 'detect_pin'):
                log(TAG_HW, "Cleaning up detect pin...")
                self.detect_pin.value = False
                self.detect_pin.deinit()
            if self.connection_manager:
                self.connection_manager.cleanup()
            if self.midi:
                log(TAG_MIDI, "Cleaning up MIDI...")
                self.midi.cleanup()
            if self.transport:
                log(TAG_TRANS, "Cleaning up transport...")
                self.transport.cleanup()
            _cycle_log("\nBartleby goes to sleep... ( ◡_◡)ᶻ 𝗓 𐰁\n")
        except Exception as e:
            log(TAG_BARTLEBY, f"Error during cleanup: {str(e)}", is_error=True)

    def play_greeting(self):
        """Play greeting chime using MPE"""
        log(TAG_MIDI, "Playing MPE greeting sequence")
        try:    
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
                
                log(TAG_MIDI, f"Played greeting note {idx+1}/4: {note}")
        except Exception as e:
            log(TAG_MIDI, f"Error playing greeting sequence: {str(e)}", is_error=True)

def main():
    try:
        controller = Bartleby()
        controller.run()
    except Exception as e:
        log(TAG_BARTLEBY, f"Fatal error: {str(e)}", is_error=True)

if __name__ == "__main__":
    main()
