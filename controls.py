from constants import (
    DEFAULT_CC_ASSIGNMENTS,
    ZONE_MANAGER
)
from logging import log, TAG_CONTROL

class ControllerManager:
    """Manages controller assignments and configuration for pots"""
    def __init__(self):
        self.controller_assignments = DEFAULT_CC_ASSIGNMENTS.copy()

    def reset_to_defaults(self):
        """Reset all controller assignments to default values"""
        self.controller_assignments = DEFAULT_CC_ASSIGNMENTS.copy()
        log(TAG_CONTROL, "Controller assignments reset to defaults")

    def get_controller_for_pot(self, pot_number):
        """Get the controller number assigned to a pot"""
        return self.controller_assignments.get(pot_number, pot_number)

    def handle_config_message(self, message):
        """Handle configuration message from Candide
        Format: cc:0=74:Piano Decay,1=71:Filter Resonance
        Returns True if successful, False if invalid format
        """
        try:
            if not message.startswith("cc:"):
                return False

            # Reset all assignments to CC0 first
            self.controller_assignments.clear()
            for i in range(14):  # 0-13
                self.controller_assignments[i] = 0

            # Process assignments from message
            assignments = message[3:].split(',')
            max_pot = -1
            for assignment in assignments:
                if '=' not in assignment:
                    continue
                pot, cc_info = assignment.split('=')
                # Split cc_info to handle cases with or without name
                cc_parts = cc_info.split(':')
                cc_num = int(cc_parts[0])
                pot_num = int(pot)
                max_pot = max(max_pot, pot_num)
                
                if 0 <= pot_num <= 13 and 0 <= cc_num <= 127:
                    self.controller_assignments[pot_num] = cc_num
                    log(TAG_CONTROL, f"Assigned Pot {pot_num} to CC {cc_num}")

            # Ensure all pots after the last assigned one are set to CC0
            for i in range(max_pot + 1, 14):
                self.controller_assignments[i] = 0
                log(TAG_CONTROL, f"Set Pot {i} to CC0 (unassigned)")

            return True

        except Exception as e:
            print(f"Error parsing controller config: {str(e)}")
            return False

class MidiControlProcessor:
    """Handles MIDI control change processing with configurable assignments"""
    def __init__(self):
        self.controller_config = ControllerManager()

    def process_controller_changes(self, changed_pots):
        """Process controller changes and generate MIDI events"""
        midi_events = []
        for pot_index, old_value, new_value in changed_pots:
            controller_number = self.controller_config.get_controller_for_pot(pot_index)
            # Ensure new_value is in 0-1 range before scaling to MIDI range
            new_value = max(0.0, min(1.0, new_value))
            # Scale to MIDI range and clamp to ensure valid CC value
            midi_value = min(127, max(0, int(new_value * 127)))
            midi_events.append(('control_change', controller_number, midi_value))
            log(TAG_CONTROL, f"Controller {pot_index} changed: CC{controller_number}={midi_value}")
        return midi_events

    def handle_config_message(self, message):
        """Process configuration message from Candide"""
        return self.controller_config.handle_config_message(message)

    def reset_to_defaults(self):
        """Reset controller assignments to defaults"""
        self.controller_config.reset_to_defaults()
