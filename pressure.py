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
                
                # Log statistics every 1000 samples
                if self.samples_collected % 1000 == 0:
                    avg_resistance = self.resistance_sum / self.samples_collected
                    log(TAG_PRESSUR, f"Resistance stats after {self.samples_collected} samples:")
                    log(TAG_PRESSUR, f"  Min: {self.min_seen_resistance:.0f} ohms")
                    log(TAG_PRESSUR, f"  Max: {self.max_seen_resistance:.0f} ohms")
                    log(TAG_PRESSUR, f"  Avg: {avg_resistance:.0f} ohms")
            
            # Log unusual resistance values
            if resistance < MIN_VK_RESISTANCE * 0.5:  # Much lower than expected
                log(TAG_PRESSUR, f"Unusually low resistance: {resistance:.0f} ohms")
            elif MIN_VK_RESISTANCE < resistance < MAX_VK_RESISTANCE:
                if resistance < MIN_VK_RESISTANCE * 1.1:  # Near minimum
                    log(TAG_PRESSUR, f"Near minimum resistance: {resistance:.0f} ohms")
                elif resistance > MAX_VK_RESISTANCE * 0.9:  # Near maximum
                    log(TAG_PRESSUR, f"Near maximum resistance: {resistance:.0f} ohms")
                    
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
            
            # Invert and enhance lower range sensitivity with power function
            # Power = 0.5 gives square root curve:
            # - More gradual change in high resistance (light pressure) range
            # - Still reaches maximum values with enough pressure
            normalized = math.pow(1.0 - log_normalized, 3)
            
            # Log normalization pairs every 100th sample
            if self.samples_collected % 100 == 0:
                log(TAG_PRESSUR, f"Normalization: {resistance:.0f} ohms -> {normalized:.3f}")
            
            # Clamp to valid range
            result = max(0.0, min(1.0, normalized))
            
            # Log significant pressure values
            if result > 0.9:  # Near maximum pressure
                log(TAG_PRESSUR, f"High pressure detected: {result:.3f}")
            
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
            
            # Log position calculations every 100th sample
            if self.samples_collected % 100 == 0:
                log(TAG_PRESSUR, f"Position calc - L:{left_norm:.3f} R:{right_norm:.3f} -> Pos:{position:.3f}")
                
            return position
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error calculating position L:{left_norm:.3f} R:{right_norm:.3f}: {str(e)}", is_error=True)
            return 0.0

    def calculate_pressure(self, left_norm, right_norm):
        """Calculate total pressure (0.0-1.0) from normalized L/R values"""
        try:
            pressure = max(left_norm, right_norm)
            
            # Log pressure calculations every 100th sample
            if self.samples_collected % 100 == 0:
                log(TAG_PRESSUR, f"Pressure calc - L:{left_norm:.3f} R:{right_norm:.3f} -> P:{pressure:.3f}")
            
            # Log significant pressure imbalances
            if min(left_norm, right_norm) < max(left_norm, right_norm) * 0.5:
                log(TAG_PRESSUR, f"Large pressure imbalance - L:{left_norm:.3f} R:{right_norm:.3f}")
                
            return pressure
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error calculating pressure L:{left_norm:.3f} R:{right_norm:.3f}: {str(e)}", is_error=True)
            return 0.0
