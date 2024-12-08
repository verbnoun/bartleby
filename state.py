from connection import get_precise_time
from constants import POT_SCAN_INTERVAL, ENCODER_SCAN_INTERVAL

class StateManager:
    def __init__(self):
        self.current_time = 0
        self.last_pot_scan = 0
        self.last_encoder_scan = 0
        
    def update_time(self):
        self.current_time = get_precise_time()
        
    def should_scan_pots(self):
        return (self.current_time - self.last_pot_scan) >= (POT_SCAN_INTERVAL * 1_000_000_000)  # Convert to ns
        
    def should_scan_encoders(self):
        return (self.current_time - self.last_encoder_scan) >= (ENCODER_SCAN_INTERVAL * 1_000_000_000)  # Convert to ns
        
    def update_pot_scan_time(self):
        self.last_pot_scan = self.current_time
        
    def update_encoder_scan_time(self):
        self.last_encoder_scan = self.current_time
