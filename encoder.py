"""Button-based octave control."""

import digitalio
from logging import log, TAG_ENCODER

class OctaveButtonHandler:
    def __init__(self, up_pin, down_pin):
        """Initialize octave button handler"""
        try:
            log(TAG_ENCODER, "Initializing octave button handler")
            
            # Initialize buttons
            self.up_button = digitalio.DigitalInOut(up_pin)
            self.up_button.direction = digitalio.Direction.INPUT
            self.up_button.pull = digitalio.Pull.UP
            
            self.down_button = digitalio.DigitalInOut(down_pin)
            self.down_button.direction = digitalio.Direction.INPUT
            self.down_button.pull = digitalio.Pull.UP
            
            self.min_position = -3  # Allow down three octaves
            self.max_position = 3   # Allow up three octaves
            self.current_position = 0
            
            # Track previous button states
            self.last_up_state = True    # Pulled high when not pressed
            self.last_down_state = True  # Pulled high when not pressed
            
            log(TAG_ENCODER, "Initialized octave buttons")
            
        except Exception as e:
            log(TAG_ENCODER, f"Button initialization failed: {str(e)}", is_error=True)
            raise

    def reset_position(self):
        """Reset octave position to center"""
        try:
            self.current_position = 0
            log(TAG_ENCODER, "Reset octave position to 0")
        except Exception as e:
            log(TAG_ENCODER, f"Error resetting position: {str(e)}", is_error=True)

    def read_buttons(self):
        """Read buttons and return events if position changed"""
        events = []
        try:
            # Read current button states (False = pressed since pulled up)
            up_pressed = not self.up_button.value
            down_pressed = not self.down_button.value
            
            # Check for new button presses
            if up_pressed and not up_pressed == self.last_up_state:
                if self.current_position < self.max_position:
                    self.current_position += 1
                    events.append(('rotation', 0, 1, self.current_position))
                    log(TAG_ENCODER, f"Octave up: {self.current_position}")
                else:
                    log(TAG_ENCODER, f"At max octave: {self.current_position}")
                    
            if down_pressed and not down_pressed == self.last_down_state:
                if self.current_position > self.min_position:
                    self.current_position -= 1
                    events.append(('rotation', 0, -1, self.current_position))
                    log(TAG_ENCODER, f"Octave down: {self.current_position}")
                else:
                    log(TAG_ENCODER, f"At min octave: {self.current_position}")
            
            # Update button states
            self.last_up_state = up_pressed
            self.last_down_state = down_pressed
            
            return events
            
        except Exception as e:
            log(TAG_ENCODER, f"Error reading buttons: {str(e)}", is_error=True)
            return events

    def get_position(self):
        """Get current octave position"""
        try:
            log(TAG_ENCODER, f"Current octave position: {self.current_position}")
            return self.current_position
        except Exception as e:
            log(TAG_ENCODER, f"Error getting position: {str(e)}", is_error=True)
            return 0
