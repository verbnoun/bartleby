"""Connection management and handshake protocol for Bartleby."""

import board
import time
from constants import (
    DETECT_PIN, COMMUNICATION_TIMEOUT, STARTUP_DELAY,
    BUFFER_CLEAR_TIMEOUT, VALID_CARTRIDGES, ZONE_MANAGER
)
from logging import log, TAG_CONNECT

class ConnectionManager:
    """
    Manages connection state and handshake protocol for Bartleby (Base Station).
    Receives text messages, sends MIDI responses.
    """
    # Connection States
    STANDALONE = 0      # No active client
    CONNECTING = 1      # Initial handshake
    ATTACHED = 2        # Fully connected and operational
    
    # Config States
    DEFAULT = 0         # Using default CC assignments
    SETTING_CONFIG = 1  # Processing new config
    CONFIGURED = 2      # Using custom config
    
    # Config acknowledgment
    CONFIG_CC = 127     # CC number for config acknowledgment
    CONFIG_EMPTY = 0    # Value for empty config
    
    def __init__(self, text_uart, hardware_coordinator, midi_logic, transport_manager):
        try:
            self.uart = text_uart
            self.hardware = hardware_coordinator
            self.midi = midi_logic
            self.transport = transport_manager
            
            # Connection state
            self.state = self.STANDALONE
            self.last_message_time = time.monotonic()
            
            # Config state
            self.config_state = self.DEFAULT
            
            # Store cartridge and pot mapping info
            self.cartridge_name = None
            self.instrument_name = None
            self.pot_mapping = {}  # Format: {pot_number: {'cc': cc_number, 'control_name': name}}
            
            log(TAG_CONNECT, "Connection manager initialized - listening for Candide")
        except Exception as e:
            log(TAG_CONNECT, f"Failed to initialize connection manager: {str(e)}", is_error=True)
            raise
        
    def update_state(self):
        """Check for timeouts"""
        if self.state != self.STANDALONE:
            current_time = time.monotonic()
            time_since_last = current_time - self.last_message_time
            if time_since_last > COMMUNICATION_TIMEOUT:
                log(TAG_CONNECT, f"Communication timeout ({time_since_last:.1f}s) - returning to standalone")
                self._reset_state()
                
    def handle_message(self, message):
        """Process incoming text messages"""
        if not message:
            return
            
        # Any message updates last message time
        self.last_message_time = time.monotonic()
        
        try:
            # Handle ⚡ message - transition to ATTACHED if in CONNECTING and CONFIGURED
            if message.startswith("⚡"):
                if self.state == self.CONNECTING and self.config_state == self.CONFIGURED:
                    self.state = self.ATTACHED
                    log(TAG_CONNECT, "Received confirmation ⚡ - Connection state -> ATTACHED")
                return
            
            # Check if message starts with a valid cartridge name
            cartridge_name = message.split('|')[0] if '|' in message else ''
            if cartridge_name in VALID_CARTRIDGES:
                if self.state == self.STANDALONE:
                    log(TAG_CONNECT, "Valid cartridge detected - entering CONNECTING state")
                    self.state = self.CONNECTING
                    
                # Begin config process
                self.config_state = self.SETTING_CONFIG
                log(TAG_CONNECT, "Config state -> SETTING_CONFIG")
                
                # Parse config and send acknowledgment
                if self._parse_cc_config(message):
                    self.config_state = self.CONFIGURED
                    log(TAG_CONNECT, "Config state -> CONFIGURED")
                    log(TAG_CONNECT, "Waiting for confirmation ⚡")
                else:
                    # Failed config handling
                    if self.config_state != self.CONFIGURED:
                        # If not already configured, reset everything
                        self.config_state = self.DEFAULT
                        self.state = self.STANDALONE
                        log(TAG_CONNECT, "Config failed - returning to STANDALONE")
                    else:
                        # If already configured, keep existing config
                        log(TAG_CONNECT, "Config update failed - keeping existing configuration")
                return
                
            # Handle heartbeat
            if message.startswith("♡"):
                log(TAG_CONNECT, "♡", is_heartbeat=True)
                return
                
        except Exception as e:
            log(TAG_CONNECT, f"Error processing message: {str(e)}", is_error=True)
            
    def _parse_cc_config(self, message):
        """Parse CC configuration message"""
        try:
            self.pot_mapping.clear()
            
            # Parse format: "Candide|Working|cc" or "Candide|Prophet 5|cc|0=71:Low Pass Cutoff|1=22:Low Pass Resonance|..."
            parts = message.split('|')
            if len(parts) < 3:  # Need at least cartridge, instrument, and cc marker
                log(TAG_CONNECT, "Invalid config format")
                return False
                
            # Extract cartridge name, instrument name, and verify cc marker
            self.cartridge_name = parts[0]
            self.instrument_name = parts[1]
            if parts[2] != "cc":
                log(TAG_CONNECT, "Invalid config type")
                return False
                
            # If no mappings provided, that's okay - just clear existing mappings
            if len(parts) == 3:
                log(TAG_CONNECT, f"Empty CC Configuration parsed for {self.cartridge_name} ({self.instrument_name})")
                # Send empty config acknowledgment
                self.midi.update([], [(self.CONFIG_CC, 0, self.CONFIG_EMPTY)], {})
                log(TAG_CONNECT, f"Sent empty config ack: CC {self.CONFIG_CC} = {self.CONFIG_EMPTY}")
                # Send empty config to MIDI system
                return self.midi.handle_config_message("cc:")
                
            # Convert to MIDI system format
            # Need to strip control names for MIDI system
            midi_assignments = []
            
            # Process CC assignments with improved error handling
            for assignment in parts[3:]:
                if not assignment or '=' not in assignment or ':' not in assignment:
                    continue
                    
                try:
                    # First split on equals to get pot number
                    pot_part, rest = assignment.split('=', 1)
                    
                    # Then split rest on first colon only to get CC number and name
                    parts_after_equals = rest.split(':', 1)
                    if len(parts_after_equals) != 2:
                        log(TAG_CONNECT, f"Invalid format in CC assignment: {assignment}", is_error=True)
                        continue
                        
                    cc_part, control_name = parts_after_equals
                    
                    # Validate numbers before parsing
                    if not (pot_part.strip().isdigit() and cc_part.strip().isdigit()):
                        log(TAG_CONNECT, f"Invalid number format in CC assignment: {assignment}", is_error=True)
                        continue
                        
                    pot_num = int(pot_part.strip())
                    cc_num = int(cc_part.strip())
                    
                    # Store full mapping locally
                    self.pot_mapping[pot_num] = {
                        'cc': cc_num,
                        'control_name': control_name.strip()
                    }
                    
                    # Add stripped version for MIDI system
                    midi_assignments.append(f"{pot_num}={cc_num}")
                    
                except (ValueError, IndexError) as e:
                    log(TAG_CONNECT, f"Error parsing CC assignment '{assignment}': {str(e)}", is_error=True)
                    continue
            
            # Convert to MIDI system format and send
            midi_format = "cc:" + ",".join(midi_assignments)
            if self.midi.handle_config_message(midi_format):
                log(TAG_CONNECT, f"CC Configuration parsed for {self.cartridge_name} ({self.instrument_name}): {len(self.pot_mapping)} mappings")
                # For non-empty configs, just send current pot values as the reply
                self._send_pot_values()
                return True
            
            return False
            
        except Exception as e:
            log(TAG_CONNECT, f"Failed to parse config: {str(e)}", is_error=True)
            return False
            
    def _send_pot_values(self):
        """Send current pot values as MIDI messages"""
        try:
            # Only read pots that have CC mappings
            all_pots = self.hardware.components['pots'].read_all_pots()
            pot_changes = []
            
            for pot_index, normalized_value in all_pots:
                if pot_index in self.pot_mapping:
                    pot_changes.append((pot_index, 0, normalized_value))
            
            # Send pot values
            if pot_changes:
                self.midi.update([], pot_changes, {})
                log(TAG_CONNECT, f"Sent {len(pot_changes)} pot values")
                
        except Exception as e:
            log(TAG_CONNECT, f"Failed to send pot values: {str(e)}", is_error=True)
            
    def _reset_state(self):
        """Reset to initial state"""
        try:
            self.state = self.STANDALONE
            self.config_state = self.DEFAULT
            self.last_message_time = time.monotonic()
            self.cartridge_name = None
            self.instrument_name = None
            self.pot_mapping.clear()
            
            # Clear both UART and text protocol buffers
            self.transport.flush_buffers()
            if hasattr(self.uart, 'clear_buffer'):
                self.uart.clear_buffer()
            
            # Add a small delay to ensure we're ready for new messages
            time.sleep(0.1)  # 100ms delay
            
            log(TAG_CONNECT, "Reset to initial state")
        except Exception as e:
            log(TAG_CONNECT, f"Error during state reset: {str(e)}", is_error=True)
        
    def cleanup(self):
        """Clean up resources"""
        log(TAG_CONNECT, "Starting connection cleanup")
        try:
            self._reset_state()
            log(TAG_CONNECT, "Connection cleanup complete")
        except Exception as e:
            log(TAG_CONNECT, f"Error during cleanup: {str(e)}", is_error=True)
        
    def is_connected(self):
        """Check if fully connected"""
        return self.state == self.ATTACHED
        
    def get_cartridge_info(self):
        """Get current cartridge information for UI"""
        return {
            'name': self.cartridge_name,
            'instrument': self.instrument_name,
            'pots': self.pot_mapping
        }
    
    def get_pot_info(self, pot_number):
        """Get specific pot information for UI"""
        return self.pot_mapping.get(pot_number)
