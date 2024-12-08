"""Pressure sensor processing and MPE calculations."""

import math
from constants import (
    MAX_VK_RESISTANCE, MIN_VK_RESISTANCE,
    REST_VOLTAGE_THRESHOLD, ADC_RESISTANCE_SCALE,
    PRESSURE_FLOOR, PRESSURE_CEILING, ENVELOPE_CURVE
)
from logging import log, TAG_PRESSUR

class PressureSensorProcessor:
    def __init__(self):
        try:
            log(TAG_PRESSUR, "Initializing pressure sensor processor")
            log(TAG_PRESSUR, f"Resistance range: {MIN_VK_RESISTANCE:.0f} to {MAX_VK_RESISTANCE:.0f} ohms")
            log(TAG_PRESSUR, f"Pressure range: {PRESSURE_FLOOR:.2f} to {PRESSURE_CEILING:.2f}")
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
        """Convert resistance to normalized pressure value (0.0-1.0) using logarithmic curve"""
        try:
            if resistance >= MAX_VK_RESISTANCE:
                return 0
            if resistance <= MIN_VK_RESISTANCE:
                return 1
                
            # Calculate logarithmic normalization
            log_min = math.log(MIN_VK_RESISTANCE)
            log_max = math.log(MAX_VK_RESISTANCE)
            log_value = math.log(resistance)
            
            # Inverse the normalization since resistance decreases with pressure
            normalized = 1.0 - ((log_value - log_min) / (log_max - log_min))
            
            # Apply envelope
            result = self.apply_envelope(normalized)
            
            # Log significant pressure values
            if result > 0.9:  # Near maximum pressure
                log(TAG_PRESSUR, f"High pressure detected: {result:.3f}")
            
            return result
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error normalizing resistance {resistance}: {str(e)}", is_error=True)
            return 0.0

    def apply_envelope(self, raw_pressure):
        """Apply envelope to expand limited pressure range"""
        try:
            # Clamp to floor/ceiling
            if raw_pressure < PRESSURE_FLOOR:
                return 0.0
            if raw_pressure > PRESSURE_CEILING:
                return 1.0
                
            # Normalize to new range
            normalized = (raw_pressure - PRESSURE_FLOOR) / (PRESSURE_CEILING - PRESSURE_FLOOR)
            
            # Apply curve
            curved = math.pow(normalized, ENVELOPE_CURVE)
            
            # Log significant envelope adjustments
            if abs(curved - raw_pressure) > 0.3:  # Large envelope effect
                log(TAG_PRESSUR, f"Large envelope adjustment: {raw_pressure:.3f} -> {curved:.3f}")
            
            return max(0.0, min(1.0, curved))
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error applying envelope to {raw_pressure}: {str(e)}", is_error=True)
            return 0.0

    def calculate_position(self, left_norm, right_norm):
        """Calculate relative position (-1.0 to 1.0) from normalized L/R values"""
        try:
            total = left_norm + right_norm
            if total == 0:
                return 0
                
            position = (right_norm - left_norm) / total
            
            # Log extreme positions
            if abs(position) > 0.9:  # Near edges
                log(TAG_PRESSUR, f"Extreme position detected: {position:.3f}")
                
            return position
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error calculating position L:{left_norm:.3f} R:{right_norm:.3f}: {str(e)}", is_error=True)
            return 0.0

    def calculate_pressure(self, left_norm, right_norm):
        """Calculate total pressure (0.0-1.0) from normalized L/R values"""
        try:
            pressure = max(left_norm, right_norm)
            
            # Log significant pressure imbalances
            if min(left_norm, right_norm) < max(left_norm, right_norm) * 0.5:
                log(TAG_PRESSUR, f"Large pressure imbalance - L:{left_norm:.3f} R:{right_norm:.3f}")
                
            return pressure
            
        except Exception as e:
            log(TAG_PRESSUR, f"Error calculating pressure L:{left_norm:.3f} R:{right_norm:.3f}: {str(e)}", is_error=True)
            return 0.0
