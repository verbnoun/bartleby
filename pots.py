from constants import (
    DEBUG, ADC_MAX, ADC_MIN,
    POT_THRESHOLD, POT_CHANGE_THRESHOLD,
    POT_LOWER_TRIM, POT_UPPER_TRIM,
    NUM_POTS, POT_LOG_THRESHOLD
)

class PotentiometerHandler:
    def __init__(self, multiplexer):
        """Initialize potentiometer handler with multiplexer"""
        self.multiplexer = multiplexer
        self.last_reported_values = [0] * NUM_POTS
        self.last_normalized_values = [0.0] * NUM_POTS
        self.is_active = [False] * NUM_POTS
        self.last_change = [0] * NUM_POTS

    def normalize_value(self, value):
        """Convert ADC value to normalized range (0.0-1.0)"""
        clamped_value = max(min(value, ADC_MAX), ADC_MIN)
        normalized = (clamped_value - ADC_MIN) / (ADC_MAX - ADC_MIN)
        if normalized < POT_LOWER_TRIM:
            normalized = 0
        elif normalized > (1 - POT_UPPER_TRIM):
            normalized = 1
        else:
            normalized = (normalized - POT_LOWER_TRIM) / (1 - POT_LOWER_TRIM - POT_UPPER_TRIM)
        return round(normalized, 3)  # Reduced precision to help with noise

    def read_pots(self):
        """Read all potentiometers and return changed values"""
        changed_pots = []
        for i in range(NUM_POTS):
            raw_value = self.multiplexer.read_channel(i)
            normalized_new = self.normalize_value(raw_value)
            change = abs(raw_value - self.last_reported_values[i])
            change_normalized = abs(normalized_new - self.last_normalized_values[i])

            if self.is_active[i]:
                # Only report changes if they exceed the change threshold
                if change > POT_CHANGE_THRESHOLD:
                    # Only report if normalized value has actually changed
                    if normalized_new != self.last_normalized_values[i]:
                        changed_pots.append((i, self.last_normalized_values[i], normalized_new))
                        self.last_reported_values[i] = raw_value
                        self.last_normalized_values[i] = normalized_new
                        self.last_change[i] = change
                        
                        # Only log if change exceeds logging threshold
                        if DEBUG and change_normalized > POT_LOG_THRESHOLD:
                            print(f"\nPot {i}: {self.last_normalized_values[i]:.3f} -> {normalized_new:.3f}")
                            
                elif change < POT_THRESHOLD:
                    self.is_active[i] = False
            elif change > POT_THRESHOLD:
                self.is_active[i] = True
                if normalized_new != self.last_normalized_values[i]:
                    changed_pots.append((i, self.last_normalized_values[i], normalized_new))
                    self.last_reported_values[i] = raw_value
                    self.last_normalized_values[i] = normalized_new
                    self.last_change[i] = change
                    
                    # Only log if change exceeds logging threshold
                    if DEBUG and change_normalized > POT_LOG_THRESHOLD:
                        print(f"\nPot {i}: {self.last_normalized_values[i]:.3f} -> {normalized_new:.3f}")
                
        return changed_pots

    def read_all_pots(self):
        """Read all potentiometers and return their current normalized values"""
        all_pots = []
        for i in range(NUM_POTS):
            raw_value = self.multiplexer.read_channel(i)
            normalized_value = self.normalize_value(raw_value)
            
            # Update last values to ensure subsequent read_pots() works correctly
            self.last_reported_values[i] = raw_value
            self.last_normalized_values[i] = normalized_value
            
            # Mark as active to prevent filtering out in subsequent read_pots()
            self.is_active[i] = True
            
            all_pots.append((i, normalized_value))
            
            if DEBUG:
                print(f"Initial Pot {i}: {normalized_value:.3f}")
        
        return all_pots
