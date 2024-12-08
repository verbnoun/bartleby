"""Connection management and handshake protocol for Bartleby."""

import board
import time
from constants import (
    DETECT_PIN, COMMUNICATION_TIMEOUT, STARTUP_DELAY,
    BUFFER_CLEAR_TIMEOUT, MSG_CONFIG
)
from logging import log, TAG_CONNECT

class ConnectionManager:
    """
    Manages connection state and handshake protocol for Bartleby (Base Station).
    Receives text messages, sends MIDI responses.
    """
    # States
    STANDALONE = 0      # No active client
    CONNECTED = 1       # Fully connected and operational
    
    def __init__(self, text_uart, hardware_coordinator, midi_logic, transport_manager):
        try:
            self.uart = text_uart
            self.hardware = hardware_coordinator
            self.midi = midi_logic
            self.transport = transport_manager
            
            # Connection state
            self.state = self.STANDALONE
            self.last_message_time = time.monotonic()
            
            # Store CC mapping
            self.cc_mapping = {}  # Format: {pot_number: {'cc': cc_number}}
            
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
            # Handle config message
            if message.startswith(MSG_CONFIG):
                if self.state == self.STANDALONE:
                    log(TAG_CONNECT, "Config received - parsing CC mapping")
                else:
                    log(TAG_CONNECT, "Config update received - applying new CC mapping")
                
                # Parse config and send pot values
                if self._parse_cc_config(message):
                    self.state = self.CONNECTED
                    self._send_pot_values()
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
            self.cc_mapping.clear()
            
            # Remove "cc|" prefix and parse assignments
            config_part = message[3:]
            if not config_part:
                log(TAG_CONNECT, "Empty config received")
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
                        log(TAG_CONNECT, f"Error parsing CC assignment '{assignment}': {str(e)}", is_error=True)
                        continue
                
                log(TAG_CONNECT, f"CC Configuration parsed: {len(self.cc_mapping)} mappings")
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
                if pot_index in self.cc_mapping:
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
            self.last_message_time = time.monotonic()
            self.cc_mapping.clear()
            self.transport.flush_buffers()
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
        return self.state == self.CONNECTED
