from constants import (
    MPE_MEMBER_PITCH_BEND_RANGE,
    MPE_MASTER_PITCH_BEND_RANGE,
    ZONE_START,
    ZONE_END,
    DEFAULT_CC_ASSIGNMENTS
)
from logging import log, TAG_CONFIG

class MPEConfigurator:
    """Handles MPE-specific configuration and setup"""
    def __init__(self, message_sender):
        self.message_sender = message_sender

    def configure_mpe(self):
        """Configure MPE zones and pitch bend ranges"""
        log(TAG_CONFIG, "Configuring MPE zones and pitch bend ranges")
            
        # Reset all channels first
        self.message_sender.send_message([0xB0, 121, 0])  # Reset all controllers
        self.message_sender.send_message([0xB0, 123, 0])  # All notes off
        
        # Configure MPE zone (RPN 6)
        self.message_sender.send_message([0xB0, 101, 0])  # RPN MSB
        self.message_sender.send_message([0xB0, 100, 6])  # RPN LSB (MCM)
        zone_size = ZONE_END - ZONE_START + 1
        self.message_sender.send_message([0xB0, 6, zone_size])
        log(TAG_CONFIG, f"MPE zone configured: {zone_size} channels")
        
        # Configure Manager Channel pitch bend range
        self.message_sender.send_message([0xB0, 101, 0])  # RPN MSB
        self.message_sender.send_message([0xB0, 100, 0])  # RPN LSB (pitch bend)
        self.message_sender.send_message([0xB0, 6, MPE_MASTER_PITCH_BEND_RANGE])
        log(TAG_CONFIG, f"Manager channel pitch bend range: {MPE_MASTER_PITCH_BEND_RANGE} semitones")
        
        # Configure Member Channel pitch bend range
        for channel in range(ZONE_START, ZONE_END + 1):
            self.message_sender.send_message([0xB0 | channel, 101, 0])  # RPN MSB
            self.message_sender.send_message([0xB0 | channel, 100, 0])  # RPN LSB (pitch bend)
            self.message_sender.send_message([0xB0 | channel, 6, MPE_MEMBER_PITCH_BEND_RANGE])
        log(TAG_CONFIG, f"Member channels pitch bend range: {MPE_MEMBER_PITCH_BEND_RANGE} semitones")

class ConfigurationManager:
    """Manages instrument configuration state and CC mappings"""
    # States
    DEFAULT = 0
    SETTING_CONFIG = 1
    CONFIGURED = 2
    
    def __init__(self, hardware_coordinator, midi_logic):
        try:
            log(TAG_CONFIG, "Initializing Configuration Manager")
            self.state = self.DEFAULT
            self.hardware = hardware_coordinator
            self.midi = midi_logic
            
            # Configuration storage
            self.cartridge_name = None
            self.instrument_name = None
            self.pot_mapping = {}
            
            # Initialize with defaults
            self._load_default_config()
            log(TAG_CONFIG, "Configuration Manager initialized in DEFAULT state")
        except Exception as e:
            log(TAG_CONFIG, f"Failed to initialize Configuration Manager: {str(e)}", is_error=True)
            raise
    
    def _load_default_config(self):
        """Load default CC assignments"""
        try:
            log(TAG_CONFIG, "Loading default configuration")
            self.cartridge_name = None
            self.instrument_name = None
            self.pot_mapping.clear()
            for pot, cc in DEFAULT_CC_ASSIGNMENTS.items():
                self.pot_mapping[pot] = {
                    'cc': cc,
                    'control_name': f'Control {cc}'
                }
            self.state = self.DEFAULT
            log(TAG_CONFIG, f"Loaded default configuration with {len(self.pot_mapping)} CC mappings")
        except Exception as e:
            log(TAG_CONFIG, f"Error loading default configuration: {str(e)}", is_error=True)
            raise
        
    def begin_config(self, config_message):
        """Start configuration process"""
        try:
            previous_state = self.state
            log(TAG_CONFIG, f"Beginning configuration (current state: {previous_state})")
            
            self.state = self.SETTING_CONFIG
            log(TAG_CONFIG, "State -> SETTING_CONFIG")
            
            success = self._parse_config(config_message)
            
            if success:
                self.state = self.CONFIGURED
                log(TAG_CONFIG, "State -> CONFIGURED")
                self._send_pot_values()
                log(TAG_CONFIG, f"Configuration complete: {self.cartridge_name} ({self.instrument_name})")
            else:
                if previous_state == self.CONFIGURED:
                    # Keep existing config if already configured
                    self.state = self.CONFIGURED
                    log(TAG_CONFIG, "Configuration failed - keeping existing configuration")
                else:
                    # Revert to defaults if not yet configured
                    log(TAG_CONFIG, "Configuration failed - reverting to defaults")
                    self._load_default_config()
            
            return success
            
        except Exception as e:
            log(TAG_CONFIG, f"Error during configuration: {str(e)}", is_error=True)
            return False
            
    def _parse_config(self, message):
        """Parse configuration message"""
        try:
            log(TAG_CONFIG, "Parsing configuration message")
            
            # Parse format: "Cartridge|Instrument|cc|0=71:Low Pass Cutoff|..."
            parts = message.split('|')
            if len(parts) < 3:
                log(TAG_CONFIG, "Invalid config format - insufficient parts", is_error=True)
                return False
                
            # Extract cartridge and instrument names
            new_cartridge = parts[0]
            new_instrument = parts[1]
            
            if parts[2] != "cc":
                log(TAG_CONFIG, "Invalid config type - expected 'cc'", is_error=True)
                return False
                
            # Create temporary mapping for validation
            temp_mapping = {}
            midi_assignments = []
            
            # Process CC assignments
            for assignment in parts[3:]:
                if not assignment or '=' not in assignment or ':' not in assignment:
                    continue
                    
                try:
                    pot_part, rest = assignment.split('=', 1)
                    cc_part, control_name = rest.split(':', 1)
                    
                    pot_num = int(pot_part.strip())
                    cc_num = int(cc_part.strip())
                    
                    temp_mapping[pot_num] = {
                        'cc': cc_num,
                        'control_name': control_name.strip()
                    }
                    midi_assignments.append(f"{pot_num}={cc_num}")
                    
                except ValueError as e:
                    log(TAG_CONFIG, f"Error parsing assignment '{assignment}': {str(e)}", is_error=True)
                    continue
            
            # Validate with MIDI system
            midi_format = "cc:" + ",".join(midi_assignments)
            if self.midi.handle_config_message(midi_format):
                # Apply validated config
                self.cartridge_name = new_cartridge
                self.instrument_name = new_instrument
                self.pot_mapping = temp_mapping
                log(TAG_CONFIG, f"Successfully parsed {len(temp_mapping)} CC mappings")
                return True
                
            log(TAG_CONFIG, "MIDI system rejected configuration", is_error=True)
            return False
            
        except Exception as e:
            log(TAG_CONFIG, f"Error parsing configuration: {str(e)}", is_error=True)
            return False
            
    def _send_pot_values(self):
        """Send current pot values after config change"""
        try:
            log(TAG_CONFIG, "Reading current pot values")
            all_pots = self.hardware.components['pots'].read_all_pots()
            pot_changes = []
            
            for pot_index, normalized_value in all_pots:
                if pot_index in self.pot_mapping:
                    pot_changes.append((pot_index, 0, normalized_value))
            
            if pot_changes:
                self.midi.update([], pot_changes, {})
                log(TAG_CONFIG, f"Sent {len(pot_changes)} initial pot values")
                
        except Exception as e:
            log(TAG_CONFIG, f"Error sending pot values: {str(e)}", is_error=True)
            
    def get_config_info(self):
        """Get current configuration information"""
        return {
            'state': self.state,
            'cartridge': self.cartridge_name,
            'instrument': self.instrument_name,
            'mappings': self.pot_mapping
        }
