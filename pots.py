"""Potentiometer handling and value normalization."""

from constants import (
    ADC_MAX, ADC_MIN,
    POT_THRESHOLD, POT_CHANGE_THRESHOLD,
    POT_LOWER_TRIM, POT_UPPER_TRIM,
    NUM_POTS, POT_LOG_THRESHOLD
)
from logging import log, TAG_POTS

class PotentiometerHandler:
    def __init__(self, multiplexer):
        """Initialize potentiometer handler with multiplexer"""
        try:
            log(TAG_POTS, f"Initializing potentiometer handler for {NUM_POTS} pots")
            self.multiplexer = multiplexer
            self.last_reported_values = [0] * NUM_POTS
            self.last_normalized_values = [0.0] * NUM_POTS
            self.is_active = [False] * NUM_POTS
            self.last_change = [0] * NUM_POTS
            log(TAG_POTS, "Potentiometer handler initialized")
        except Exception as e:
            log(TAG_POTS, f"Failed to initialize potentiometer handler: {str(e)}", is_error=True)
            raise

    def normalize_value(self, value):
        """Convert ADC value to normalized range (0.0-1.0)"""
        try:
            clamped_value = max(min(value, ADC_MAX), ADC_MIN)
            normalized = (clamped_value - ADC_MIN) / (ADC_MAX - ADC_MIN)
            
            if normalized < POT_LOWER_TRIM:
                normalized = 0
            elif normalized > (1 - POT_UPPER_TRIM):
                normalized = 1
            else:
                normalized = (normalized - POT_LOWER_TRIM) / (1 - POT_LOWER_TRIM - POT_UPPER_TRIM)
            
            return round(normalized, 3)  # Reduced precision to help with noise
        except Exception as e:
            log(TAG_POTS, f"Error normalizing value {value}: {str(e)}", is_error=True)
            return 0.0

    def read_pots(self):
        """Read all potentiometers and return changed values"""
        changed_pots = []
        try:
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
                            
                            # Log significant changes
                            if change_normalized > POT_LOG_THRESHOLD:
                                log(TAG_POTS, f"Pot {i} changed: {self.last_normalized_values[i]:.3f} -> {normalized_new:.3f}")
                                
                    elif change < POT_THRESHOLD:
                        if self.is_active[i]:  # Only log transition to inactive
                            log(TAG_POTS, f"Pot {i} became inactive")
                        self.is_active[i] = False
                elif change > POT_THRESHOLD:
                    if not self.is_active[i]:  # Only log transition to active
                        log(TAG_POTS, f"Pot {i} became active")
                    self.is_active[i] = True
                    if normalized_new != self.last_normalized_values[i]:
                        changed_pots.append((i, self.last_normalized_values[i], normalized_new))
                        self.last_reported_values[i] = raw_value
                        self.last_normalized_values[i] = normalized_new
                        self.last_change[i] = change
                        
                        # Log significant changes
                        if change_normalized > POT_LOG_THRESHOLD:
                            log(TAG_POTS, f"Pot {i} changed: {self.last_normalized_values[i]:.3f} -> {normalized_new:.3f}")
            
            if changed_pots:
                log(TAG_POTS, f"Detected {len(changed_pots)} pot changes")
            return changed_pots
            
        except Exception as e:
            log(TAG_POTS, f"Error reading pots: {str(e)}", is_error=True)
            return []

    def read_all_pots(self):
        """Read all potentiometers and return their current normalized values"""
        all_pots = []
        try:
            log(TAG_POTS, "Reading all pot values")
            for i in range(NUM_POTS):
                raw_value = self.multiplexer.read_channel(i)
                normalized_value = self.normalize_value(raw_value)
                
                # Update last values to ensure subsequent read_pots() works correctly
                self.last_reported_values[i] = raw_value
                self.last_normalized_values[i] = normalized_value
                
                # Mark as active to prevent filtering out in subsequent read_pots()
                self.is_active[i] = True
                
                all_pots.append((i, normalized_value))
                log(TAG_POTS, f"Initial Pot {i} value: {normalized_value:.3f}")
            
            log(TAG_POTS, f"Read {len(all_pots)} pot values")
            return all_pots
            
        except Exception as e:
            log(TAG_POTS, f"Error reading all pots: {str(e)}", is_error=True)
            return []
