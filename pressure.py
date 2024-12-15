"""Pressure sensor processing and MPE calculations."""

import math
from constants import (
    MAX_VK_RESISTANCE, MIN_VK_RESISTANCE,
    REST_VOLTAGE_THRESHOLD, ADC_RESISTANCE_SCALE
)
from logging import log, TAG_PRESSUR

class PressureSensorProcessor:
    def __init__(self):
        try:
            log(TAG_PRESSUR, "Initializing pressure sensor processor")
            log(TAG_PRESSUR, f"Resistance range: {MIN_VK_RESISTANCE:.0f} to {MAX_VK_RESISTANCE:.0f} ohms")
            self.min_seen_resistance = float('inf')
            self.max_seen_resistance = 0
            self.samples_collected = 0
            self.resistance_sum = 0
        except Exception as e:
            log(TAG_PRESSUR, f"Failed to initialize pressure processor: {str(e)}", is_error=True)
            raise

    def adc_to_resistance(self, adc_value):
        """Convert ADC reading to resistance value"""
        try:
            voltage = (adc_value / 65535) * 3.3  # ADC_MAX is 65535
            if voltage >= REST_VOLTAGE_THRESHOLD:
                return float('inf')
            
            resistance = ADC_RESISTANCE_SCALE * voltage / (3.3 - voltage)
            
            # Track resistance range statistics
            if resistance < float('inf'):
                self.min_seen_resistance = min(self.min_seen_resistance, resistance)
                self.max_seen_resistance = max(self.max_seen_resistance, resistance)
                self.resistance_sum += resistance
                self.samples_collected += 1
                
            return resistance
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error converting ADC {adc_value} to resistance: {str(e)}", is_error=True)
            return float('inf')
        
    def normalize_resistance(self, resistance):
        """Convert resistance to normalized pressure value (0.0-1.0) using enhanced logarithmic scaling"""
        try:
            if resistance >= MAX_VK_RESISTANCE:
                return 0
            if resistance <= MIN_VK_RESISTANCE:
                return 1
                
            # Calculate basic logarithmic normalization
            log_normalized = math.log(resistance/MIN_VK_RESISTANCE) / math.log(MAX_VK_RESISTANCE/MIN_VK_RESISTANCE)
            
            # Invert and enhance lower range sensitivity
            normalized = math.pow(1.0 - log_normalized, 3)
            
            # Clamp to valid range
            result = max(0.0, min(1.0, normalized))
            
            return result
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error normalizing resistance {resistance}: {str(e)}", is_error=True)
            return 0.0

    def calculate_position(self, left_norm, right_norm):
        """Calculate relative position (-1.0 to 1.0) from normalized L/R values"""
        try:
            total = left_norm + right_norm
            if total == 0:
                return 0
                
            position = (right_norm - left_norm) / total
            
            # Log only the final normalized position
            log(TAG_PRESSUR, f"Position: {position:.3f}")
                
            return position
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error calculating position: {str(e)}", is_error=True)
            return 0.0

    def calculate_pressure(self, left_norm, right_norm):
        """Calculate total pressure (0.0-1.0) from normalized L/R values"""
        try:
            pressure = max(left_norm, right_norm)
            return pressure
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error calculating pressure: {str(e)}", is_error=True)
            return 0.0
