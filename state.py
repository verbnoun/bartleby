"""State management for timing and scanning intervals."""

import time
from constants import POT_SCAN_INTERVAL, ENCODER_SCAN_INTERVAL
from logging import log, TAG_STATE

class StateManager:
    def __init__(self):
        try:
            self.current_time = 0
            self.last_pot_scan = 0
            self.last_encoder_scan = 0
            log(TAG_STATE, "State manager initialized")
        except Exception as e:
            log(TAG_STATE, f"Failed to initialize state manager: {str(e)}", is_error=True)
            raise
        
    def update_time(self):
        """Update current time reference"""
        try:
            previous_time = self.current_time
            self.current_time = time.monotonic()
            
            # Log significant time jumps (more than 1 second)
            if previous_time > 0:  # Skip first update
                time_jump = self.current_time - previous_time
                if time_jump > 1.0:
                    log(TAG_STATE, f"Time jump detected: {time_jump:.2f}s")
        except Exception as e:
            log(TAG_STATE, f"Error updating time: {str(e)}", is_error=True)
        
    def should_scan_pots(self):
        """Check if enough time has passed to scan pots"""
        try:
            time_since_scan = self.current_time - self.last_pot_scan
            should_scan = time_since_scan >= POT_SCAN_INTERVAL
            return should_scan
        except Exception as e:
            log(TAG_STATE, f"Error checking pot scan timing: {str(e)}", is_error=True)
            return False
        
    def should_scan_encoders(self):
        """Check if enough time has passed to scan encoders"""
        try:
            time_since_scan = self.current_time - self.last_encoder_scan
            should_scan = time_since_scan >= ENCODER_SCAN_INTERVAL
            return should_scan
        except Exception as e:
            log(TAG_STATE, f"Error checking encoder scan timing: {str(e)}", is_error=True)
            return False
        
    def update_pot_scan_time(self):
        """Update last pot scan time"""
        try:
            previous_scan = self.last_pot_scan
            self.last_pot_scan = self.current_time
        except Exception as e:
            log(TAG_STATE, f"Error updating pot scan time: {str(e)}", is_error=True)
        
    def update_encoder_scan_time(self):
        """Update last encoder scan time"""
        try:
            previous_scan = self.last_encoder_scan
            self.last_encoder_scan = self.current_time
        except Exception as e:
            log(TAG_STATE, f"Error updating encoder scan time: {str(e)}", is_error=True)
