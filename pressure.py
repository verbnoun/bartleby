import math
from constants import (
    MAX_VK_RESISTANCE, MIN_VK_RESISTANCE,
    REST_VOLTAGE_THRESHOLD, ADC_RESISTANCE_SCALE,
    PRESSURE_FLOOR, PRESSURE_CEILING, ENVELOPE_CURVE
)

class PressureSensorProcessor:
    def adc_to_resistance(self, adc_value):
        """Convert ADC reading to resistance value"""
        voltage = (adc_value / 65535) * 3.3  # ADC_MAX is 65535
        if voltage >= REST_VOLTAGE_THRESHOLD:
            return float('inf')
        return ADC_RESISTANCE_SCALE * voltage / (3.3 - voltage)
        
    def normalize_resistance(self, resistance):
        """Convert resistance to normalized pressure value (0.0-1.0) using logarithmic curve"""
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
        return self.apply_envelope(normalized)

    def apply_envelope(self, raw_pressure):
        """Apply envelope to expand limited pressure range"""
        # Clamp to floor/ceiling
        if raw_pressure < PRESSURE_FLOOR:
            return 0.0
        if raw_pressure > PRESSURE_CEILING:
            return 1.0
            
        # Normalize to new range
        normalized = (raw_pressure - PRESSURE_FLOOR) / (PRESSURE_CEILING - PRESSURE_FLOOR)
        
        # Apply curve
        curved = math.pow(normalized, ENVELOPE_CURVE)
        
        return max(0.0, min(1.0, curved))

    def calculate_position(self, left_norm, right_norm):
        """Calculate relative position (-1.0 to 1.0) from normalized L/R values"""
        total = left_norm + right_norm
        if total == 0:
            return 0
        return (right_norm - left_norm) / total

    def calculate_pressure(self, left_norm, right_norm):
        """Calculate total pressure (0.0-1.0) from normalized L/R values"""
        return max(left_norm, right_norm)
