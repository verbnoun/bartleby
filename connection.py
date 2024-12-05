import board
import time

class Constants:
    DEBUG = True
    SEE_HEARTBEAT = False
    
    # Connection
    DETECT_PIN = board.GP22
    COMMUNICATION_TIMEOUT = 5.0
    
    # New Connection Constants
    STARTUP_DELAY = 1.0  # Give devices time to initialize
    RETRY_DELAY = 0.25   # Delay between connection attempts
    ERROR_RECOVERY_DELAY = 0.5  # Delay after errors before retry
    BUFFER_CLEAR_TIMEOUT = 0.1  # Time to wait for buffer clearing
    MAX_CONFIG_RETRIES = 3
    
    # Message Types
    MSG_HELLO = "hello"
    MSG_CONFIG = "cc:"
    
    # MIDI CC for Handshake
    HANDSHAKE_CC = 119  # Undefined CC number
    HANDSHAKE_VALUE = 42  # Arbitrary value

    # Timing precision
    TIME_PRECISION = 9  # Nanosecond precision

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

class ConnectionManager:
    """
    Manages connection state and handshake protocol for Bartleby (Base Station).
    Receives text messages, sends MIDI responses.
    """
    # States
    STANDALONE = 0      # No active client
    HANDSHAKING = 1     # In handshake process
    CONNECTED = 2       # Fully connected and operational
    
    def __init__(self, text_uart, hardware_coordinator, midi_logic, transport_manager):
        self.uart = text_uart
        self.hardware = hardware_coordinator
        self.midi = midi_logic
        self.transport = transport_manager
        
        # Connection state
        self.state = self.STANDALONE
        self.last_message_time = 0
        self.config_received = False
        
        # Store CC mapping with names
        self.cc_mapping = {}  # Format: {pot_number: {'cc': cc_number, 'name': cc_name}}
        
        print("Bartleby connection manager initialized - listening for Candide")
        
    def update_state(self):
        """Check for timeouts and manage state transitions"""
        if self.state != self.STANDALONE:
            current_time = get_precise_time()
            if (current_time - self.last_message_time) > (Constants.COMMUNICATION_TIMEOUT * 1_000_000_000):  # Convert to ns
                print("Communication timeout - returning to standalone")
                self._reset_state()
                
    def handle_message(self, message):
        """Process incoming text messages"""
        if not message:
            return
            
        # Update last message time for timeout tracking
        self.last_message_time = get_precise_time()
        
        try:
            # Handle hello message
            if message.startswith("hello"):
                if self.state == self.STANDALONE:
                    print("Hello received - starting handshake")
                    self.transport.flush_buffers()
                    self.state = self.HANDSHAKING
                    self._send_handshake_cc()
                elif self.state == self.HANDSHAKING:
                    # Send handshake CC every time hello is received during handshaking
                    print("Hello received during handshake")
                    self._send_handshake_cc()
                return
                
            # Handle config message during handshake
            if self.state == self.HANDSHAKING and message.startswith("cc:"):
                print("Config received - parsing CC mapping")
                self._parse_cc_config(message)
                self.config_received = True
                self.state = self.CONNECTED
                self._send_current_hw_state()
                
                # Debug output of CC mapping if DEBUG is true
                if Constants.DEBUG:
                    print("\nReceived CC Configuration:")
                    for pot_num, mapping in self.cc_mapping.items():
                        print(f"Pot {pot_num}: CC {mapping['cc']} - {mapping['name']}")
                    print()  # Extra newline for readability
                return
                
            # Handle config message after connection established
            if self.state == self.CONNECTED and message.startswith("cc:"):
                print("Config update received - applying new CC mapping")
                self._parse_cc_config(message)
                # Pass the new CC configuration to MIDI logic
                self.midi.handle_config_message(message)
                # Send current pot values after receiving new config
                self._send_current_hw_state()
                # Debug output of CC mapping if DEBUG is true
                if Constants.DEBUG:
                    print("\nUpdated CC Configuration:")
                    for pot_num, mapping in self.cc_mapping.items():
                        print(f"Pot {pot_num}: CC {mapping['cc']} - {mapping['name']}")
                    print()  # Extra newline for readability
                return
                
            # Handle heartbeat in connected state
            if self.state == self.CONNECTED and message.startswith("♥︎"):
                if Constants.SEE_HEARTBEAT and Constants.DEBUG:
                    print(f"♥︎")
                return  # Just update last_message_time
                
        except UnicodeError as e:
            print(f"Error in message reading: {str(e)}")
            
    def _parse_cc_config(self, message):
        """Parse CC configuration message with names"""
        self.cc_mapping.clear()  # Clear existing mapping
        
        # Remove "cc:" prefix
        config_part = message[3:]
        if not config_part:
            return
            
        # Split into individual assignments
        assignments = config_part.split(',')
        for assignment in assignments:
            if not assignment:
                continue
                
            # Parse pot=cc:name format
            try:
                pot_part, rest = assignment.split('=')
                cc_part, name = rest.split(':') if ':' in rest else (rest, f"CC{rest}")
                
                pot_num = int(pot_part)
                cc_num = int(cc_part)
                
                self.cc_mapping[pot_num] = {
                    'cc': cc_num,
                    'name': name
                }
            except (ValueError, IndexError) as e:
                print(f"Error parsing CC assignment '{assignment}': {e}")
                continue
            
    def _send_handshake_cc(self):
        """Send handshake CC message"""
        try:
            message = [0xB0, Constants.HANDSHAKE_CC, Constants.HANDSHAKE_VALUE]
            self.midi.message_sender.send_message(message)
            print("Handshake CC sent")
        except Exception as e:
            print(f"Failed to send handshake CC: {str(e)}")
            self._reset_state()
            
    def _send_current_hw_state(self):
        """Send current hardware state as MIDI messages"""
        try:
            start_time = get_precise_time()
            
            # Force read of all pots during handshake
            all_pots = self.hardware.components['pots'].read_all_pots()
            
            # Convert all_pots to the format expected by midi.update()
            pot_changes = [(pot_index, 0, normalized_value) for pot_index, normalized_value in all_pots]
            
            # Send pot values
            if pot_changes:
                self.midi.update([], pot_changes, {})
                print(f"Sent {len(pot_changes)} pot values")
            
            # Send encoder position
            encoder_pos = self.hardware.components['encoders'].get_encoder_position(0)
            if encoder_pos != 0:
                self.midi.handle_octave_shift(encoder_pos)
                print(f"Current octave position sent: {encoder_pos}")
            
            # Pass the CC configuration to MIDI logic
            if self.cc_mapping:
                config_message = "cc:" + ",".join(["{0}={1}:{2}".format(pot, mapping["cc"], mapping["name"]) for pot, mapping in self.cc_mapping.items()])
                self.midi.handle_config_message(config_message)
                print("Sent CC configuration to MIDI logic")
                
            print(format_processing_time(start_time, "Hardware state synchronization"))
                
        except Exception as e:
            print(f"Failed to send hardware state: {str(e)}")
            
    def _reset_state(self):
        """Reset to initial state"""
        self.state = self.STANDALONE
        self.config_received = False
        self.last_message_time = 0
        self.cc_mapping.clear()
        self.transport.flush_buffers()
        
    def cleanup(self):
        """Clean up resources"""
        self._reset_state()
        
    def is_connected(self):
        """Check if fully connected"""
        return self.state == self.CONNECTED
