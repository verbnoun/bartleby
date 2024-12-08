import board
import time
from constants import (
    DEBUG, DETECT_PIN, COMMUNICATION_TIMEOUT, STARTUP_DELAY,
    BUFFER_CLEAR_TIMEOUT, MSG_CONFIG
)

def get_precise_time():
    """Get high precision time measurement in nanoseconds"""
    return time.monotonic_ns()

def format_processing_time(start_time, operation=None):
    """Format processing time with nanosecond precision and optional operation description"""
    elapsed_ns = get_precise_time() - start_time
    elapsed_ms = elapsed_ns / 1_000_000  # Convert ns to ms
    if operation:
        return f"{operation} took {elapsed_ms:.3f}ms"
    return f"Processing took {elapsed_ms:.3f}ms"

def _log(message, state=None):
    """Log messages with optional state transition info"""
    if state:
        print(f"[STATE] {state}: {message}")
    else:
        print(message)

class ConnectionManager:
    """
    Manages connection state and handshake protocol for Bartleby (Base Station).
    Receives text messages, sends MIDI responses.
    """
    # States
    STANDALONE = 0      # No active client
    CONNECTED = 1       # Fully connected and operational
    
    def __init__(self, text_uart, hardware_coordinator, midi_logic, transport_manager):
        self.uart = text_uart
        self.hardware = hardware_coordinator
        self.midi = midi_logic
        self.transport = transport_manager
        
        # Connection state
        self.state = self.STANDALONE
        self.last_message_time = time.monotonic()
        
        # Store CC mapping
        self.cc_mapping = {}  # Format: {pot_number: {'cc': cc_number}}
        
        _log("Bartleby connection manager initialized - listening for Candide", "STANDALONE")
        
    def update_state(self):
        """Check for timeouts"""
        if self.state != self.STANDALONE:
            current_time = time.monotonic()
            time_since_last = current_time - self.last_message_time
            if time_since_last > COMMUNICATION_TIMEOUT:
                _log(f"Communication timeout ({time_since_last:.1f}s) - returning to standalone", "-> STANDALONE")
                self._reset_state()
                
    def handle_message(self, message):
        """Process incoming text messages"""
        if not message:
            return
            
        # Any message updates last message time
        self.last_message_time = time.monotonic()
        
        try:
            # Handle config message
            if message.startswith(MSG_CONFIG):
                if self.state == self.STANDALONE:
                    _log("Config received - parsing CC mapping", "STANDALONE -> CONNECTED")
                else:
                    _log("Config update received - applying new CC mapping", "CONNECTED")
                
                # Parse config and send pot values
                if self._parse_cc_config(message):
                    self.state = self.CONNECTED
                    self._send_pot_values()
                return
                
            # Handle heartbeat
            if message.startswith("♡"):
                if DEBUG:
                    _log("♡", "CONNECTED")
                return
                
        except Exception as e:
            print(f"Error in message reading: {str(e)}")
            
    def _parse_cc_config(self, message):
        """Parse CC configuration message"""
        try:
            self.cc_mapping.clear()
            
            # Remove "cc|" prefix and parse assignments
            config_part = message[3:]
            if not config_part:
                return False
                
            # Convert the new format to the format expected by MIDI system
            # New format: "cc|0=85|1=73|2=75|3=66|4=72"
            # Convert to: "cc:0=85,1=73,2=75,3=66,4=72"
            assignments = config_part.split('|')
            midi_format = "cc:" + ",".join(assignments)
            
            # Send to MIDI system for processing
            if self.midi.handle_config_message(midi_format):
                # Store locally for our reference
                for assignment in assignments:
                    if not assignment:
                        continue
                    try:
                        pot_part, cc_part = assignment.split('=')
                        pot_num = int(pot_part)
                        cc_num = int(cc_part)
                        self.cc_mapping[pot_num] = {'cc': cc_num}
                    except (ValueError, IndexError) as e:
                        print(f"Error parsing CC assignment '{assignment}': {e}")
                        continue
                
                # Debug output
                if DEBUG and self.cc_mapping:
                    print("\nReceived CC Configuration:")
                    for pot_num, mapping in self.cc_mapping.items():
                        print(f"Pot {pot_num}: CC {mapping['cc']}")
                    print()
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Failed to parse config: {str(e)}")
            return False
            
    def _send_pot_values(self):
        """Send current pot values as MIDI messages"""
        try:
            # Only read pots that have CC mappings
            all_pots = self.hardware.components['pots'].read_all_pots()
            pot_changes = []
            
            for pot_index, normalized_value in all_pots:
                if pot_index in self.cc_mapping:
                    pot_changes.append((pot_index, 0, normalized_value))
            
            # Send pot values
            if pot_changes:
                self.midi.update([], pot_changes, {})
                _log(f"Sent {len(pot_changes)} pot values", "CONNECTED")
                
        except Exception as e:
            print(f"Failed to send pot values: {str(e)}")
            
    def _reset_state(self):
        """Reset to initial state"""
        self.state = self.STANDALONE
        self.last_message_time = time.monotonic()
        self.cc_mapping.clear()
        self.transport.flush_buffers()
        _log("Reset to initial state", "-> STANDALONE")
        
    def cleanup(self):
        """Clean up resources"""
        self._reset_state()
        
    def is_connected(self):
        """Check if fully connected"""
        return self.state == self.CONNECTED
