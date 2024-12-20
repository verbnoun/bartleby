"""OLED display management through I2C multiplexer."""

import time
import busio
import board
from adafruit_ssd1306 import SSD1306_I2C
from adafruit_tca9548a import TCA9548A
from constants import (
    I2C_SDA, I2C_SCL, I2C_MUX_ADDRESS, OLED_ADDRESS,
    OLED_WIDTH, OLED_HEIGHT, OLED_CHANNELS, SCREEN_ROTATIONS, SCREEN_ORDER
)
from logging import log

# Create a new logging tag for display operations
TAG_DISPLAY = "DISPLAY "  # Must be 8 chars (spaces ok)

class ConfigData:
    def __init__(self):
        self.cartridge = ""
        self.status = ""
        self.mappings = {}  # pot_num -> (cc_num, label)

class DisplayManager:
    def _format_pot_label(self, label):
        """Format a pot label: capitalize first letter, remove other vowels, cap at 9 chars."""
        if not label:
            return label
            
        # Capitalize first letter
        result = label[0].upper()
        # Remove vowels from rest
        rest = ''.join(c for c in label[1:] if c.lower() not in 'aeiou')
        return (result + rest)[:9]  # Cap at 9 chars
        
    def _get_pot_label(self, pot_num):
        """Get the label for a pot - either config label or default P## label."""
        if self.config and pot_num in self.config.mappings:
            cc_num, label = self.config.mappings[pot_num]
            return self._format_pot_label(label)
        return f"P{pot_num:02d}"
        
    def _get_pot_value(self, pot_num):
        """Get the value string for a pot - either CC:## - 0.00 or just 0.00."""
        if self.config and pot_num in self.config.mappings:
            cc_num, _ = self.config.mappings[pot_num]
            return f"CC:{cc_num:02d}-{self.pot_values[pot_num]:.2f}"
        return f"{self.pot_values[pot_num]:.2f}"
        

    def set_config(self, config_string):
        """Parse config string and update display configuration.
        
        Format: Cartridge|Status|cc|0=85:Attack Level|1=73:Attack Time|...
        """
        try:
            log(TAG_DISPLAY, f"Received config string: {config_string}")
            
            # Create new config
            self.config = ConfigData()
            parts = config_string.split('|')
            if len(parts) >= 3:
                self.config.cartridge = parts[0]
                self.config.status = parts[1]
                
                # Parse control mappings
                if len(parts) > 3:
                    mapped_pots = []
                    for mapping in parts[3:]:
                        if '=' in mapping and ':' in mapping:
                            pot_part, label = mapping.split(':', 1)
                            pot_num, cc_num = map(int, pot_part.split('='))
                            self.config.mappings[pot_num] = (cc_num, label)
                            mapped_pots.append(pot_num)
            
            log(TAG_DISPLAY, f"Parsed config: {self.config.cartridge} ({len(self.config.mappings)} pot mappings)")
            
            # Enable config display mode for displays with mapped pots
            displays_with_mappings = 0
            for i in range(len(self.show_config)):
                display_position = next(pos for pos, d in enumerate(self.displays) if d['channel'] == SCREEN_ORDER[i])
                top_pot = display_position * 2
                bottom_pot = 8 + (display_position * 2)
                # Check if any pots for this display are mapped
                has_mapping = (top_pot in self.config.mappings or 
                             (top_pot + 1) in self.config.mappings or
                             bottom_pot in self.config.mappings or
                             (bottom_pot + 1) in self.config.mappings)
                self.show_config[i] = has_mapping
                if has_mapping:
                    displays_with_mappings += 1
            
            log(TAG_DISPLAY, f"Updating {displays_with_mappings} displays with mapped controls")
            
            # Update all displays
            self.update_all_displays()
            
            log(TAG_DISPLAY, "Config applied successfully")
            
        except Exception as e:
            log(TAG_DISPLAY, f"Error parsing config: {str(e)}", is_error=True)
            self.config = None
            
    def update_all_displays(self):
        """Update all displays with current config and pot values."""
        try:
            # Update first 4 displays with pot values and labels
            for i in range(min(4, len(self.displays))):
                self.update_display_with_config(i)
            
            # Update last display with status
            if len(self.displays) > 4:
                self.show_status_screen(4)
                
        except Exception as e:
            log(TAG_DISPLAY, f"Error updating displays: {str(e)}", is_error=True)
            
    def show_status_screen(self, display_index):
        """Show status screen on specified display."""
        try:
            if self.config and 0 <= display_index < len(self.displays):
                display_info = self.displays[display_index]
                self._select_channel(display_info['channel'])
                display = display_info['display']
                
                display.fill(0)
                display.text("Bartleby", 0, 8, 1)
                display.text("+", 0, 24, 1)
                if self.config.cartridge:
                    display.text(self.config.cartridge, 0, 40, 1)
                if self.config.status:
                    display.text(self.config.status, 0, 56, 1)
                display.show()
                
        except Exception as e:
            log(TAG_DISPLAY, f"Error showing status screen: {str(e)}", is_error=True)
            
    def update_display_with_config(self, display_index):
        """Update a display with pot values and optional config labels."""
        try:
            if 0 <= display_index < len(self.displays):
                display_info = self.displays[display_index]
                self._select_channel(display_info['channel'])
                display = display_info['display']
                
                display.fill(0)
                
                # Find physical position (0-4) based on channel number
                physical_position = SCREEN_ORDER.index(display_info['channel'])
                
                # Calculate pot numbers for this display based on physical position
                # Physical position 0 (leftmost): pots 0,1 and 8,9
                # Physical position 1: pots 2,3 and 10,11
                # Physical position 2: pots 4,5 and 12,13
                # Physical position 3: pots 6,7 and 14,15
                top_pot = physical_position * 2  # 0,2,4,6
                bottom_pot = physical_position * 2 + 8  # 8,10,12,14
                
                log(TAG_DISPLAY, f"Updating display {display_index} (channel {display_info['channel']}, physical {physical_position}) with pots {top_pot},{top_pot+1} and {bottom_pot},{bottom_pot+1}")
                
                # Left column
                display.text(self._get_pot_label(top_pot), 0, 0, 1)
                display.text(self._get_pot_value(top_pot), 0, 8, 1)
                display.text(self._get_pot_label(bottom_pot), 0, 24, 1)
                display.text(self._get_pot_value(bottom_pot), 0, 32, 1)
                
                # Right column
                display.text(self._get_pot_label(top_pot + 1), 69, 0, 1)
                display.text(self._get_pot_value(top_pot + 1), 69, 8, 1)
                display.text(self._get_pot_label(bottom_pot + 1), 69, 24, 1)
                display.text(self._get_pot_value(bottom_pot + 1), 69, 32, 1)
                
                display.show()
                
        except Exception as e:
            log(TAG_DISPLAY, f"Error updating display with config: {str(e)}", is_error=True)

    def __init__(self):
        """Initialize I2C multiplexer and OLED displays."""
        try:
            self.config = None
            self.pot_values = [0.0] * 16  # Store current pot values
            self.show_config = [False] * 5  # Track if each display is showing config
            log(TAG_DISPLAY, "Initializing display manager")
            
            # Initialize displays array
            self.displays = []
            
            # Initialize I2C bus and multiplexer
            self.i2c = busio.I2C(I2C_SCL, I2C_SDA)
            self.mux = TCA9548A(self.i2c, address=I2C_MUX_ADDRESS)
            
            # Initialize displays in specified order
            for display_idx, channel in enumerate(SCREEN_ORDER):
                try:
                    # Select channel on multiplexer
                    if self.i2c.try_lock():
                        try:
                            self.i2c.writeto(I2C_MUX_ADDRESS, bytes([1 << channel]))
                            time.sleep(0.001)  # Reduced delay - same as main loop interval
                        finally:
                            self.i2c.unlock()
                    
                    # Create the OLED display object using main I2C bus
                    display = SSD1306_I2C(
                        OLED_WIDTH, OLED_HEIGHT,
                        self.i2c,
                        addr=OLED_ADDRESS
                    )
                    
                    # Set rotation for this display
                    display.rotation = SCREEN_ROTATIONS[channel]
                    
                    # Store display with its channel number and logical index
                    self.displays.append({
                        'display': display,
                        'channel': channel,
                        'logical_index': display_idx  # Store position in SCREEN_ORDER
                    })
                    log(TAG_DISPLAY, f"Initialized display on channel {channel}")
                    
                except Exception as e:
                    log(TAG_DISPLAY, f"Failed to initialize display on channel {channel}: {str(e)}", is_error=True)
            
            log(TAG_DISPLAY, f"Display manager initialization complete. {len(self.displays)} displays ready")
            
            # Brief delay to show greeting
            time.sleep(0.5)
            
            # Show initial values (all zeros) on first 4 displays
            log(TAG_DISPLAY, "Showing initial pot values")
            for i in range(min(4, len(self.displays))):
                self.update_display_with_config(i)
            
            # Keep last display showing Bartleby until config arrives
            if len(self.displays) > 4:
                display_info = self.displays[4]
                self._select_channel(display_info['channel'])
                display = display_info['display']
                display.fill(0)
                display.text("Bartleby", 0, 8, 1)
                display.text("+", 0, 24, 1)
                display.show()
                log(TAG_DISPLAY, "Status display initialized")
            
        except Exception as e:
            log(TAG_DISPLAY, f"Display manager initialization failed: {str(e)}", is_error=True)
            raise

    def _select_channel(self, channel):
        """Select multiplexer channel with proper locking."""
        if self.i2c.try_lock():
            try:
                self.i2c.writeto(I2C_MUX_ADDRESS, bytes([1 << channel]))
                time.sleep(0.001)  # Reduced delay - same as main loop interval
            finally:
                self.i2c.unlock()

    def clear_display(self, display_index):
        """Clear a specific display."""
        try:
            if 0 <= display_index < len(self.displays):
                display_info = self.displays[display_index]
                self._select_channel(display_info['channel'])
                display_info['display'].fill(0)
                display_info['display'].show()
            else:
                log(TAG_DISPLAY, f"Invalid display index: {display_index}", is_error=True)
        except Exception as e:
            log(TAG_DISPLAY, f"Error clearing display {display_index}: {str(e)}", is_error=True)

    def clear_all_displays(self):
        """Clear all displays."""
        try:
            for i in range(len(self.displays)):
                self.clear_display(i)
            log(TAG_DISPLAY, "All displays cleared")
        except Exception as e:
            log(TAG_DISPLAY, f"Error clearing all displays: {str(e)}", is_error=True)

    def show_text(self, display_index, text, x=0, y=32):
        """Show text on a specific display."""
        try:
            if 0 <= display_index < len(self.displays):
                display_info = self.displays[display_index]
                self._select_channel(display_info['channel'])
                display = display_info['display']
                display.fill(0)
                display.text(str(text), x, y, 1)
                display.show()
                log(TAG_DISPLAY, f"Updated display {display_index} with text: {text}")
            else:
                log(TAG_DISPLAY, f"Invalid display index: {display_index}", is_error=True)
        except Exception as e:
            log(TAG_DISPLAY, f"Error showing text on display {display_index}: {str(e)}", is_error=True)

    def show_text_all(self, text):
        """Show the same text on all displays."""
        try:
            for i in range(len(self.displays)):
                self.show_text(i, text)
            log(TAG_DISPLAY, f"Updated all displays with text: {text}")
        except Exception as e:
            log(TAG_DISPLAY, f"Error showing text on all displays: {str(e)}", is_error=True)
            
    def show_bar(self, display_index, value, x=0, y=45, width=128, height=10):
        """Show a progress bar on a display.
        
        Args:
            display_index: Which display to update
            value: Value between 0 and 1 to show
            x, y: Position of bar
            width, height: Size of bar
        """
        try:
            if 0 <= display_index < len(self.displays):
                display_info = self.displays[display_index]
                self._select_channel(display_info['channel'])
                display = display_info['display']
                
                # Clear bar area only (don't affect text above)
                display.fill_rect(x, y, width, height, 0)
                
                # Draw filled portion
                fill_width = int(width * max(0, min(1, value)))  # Clamp value between 0-1
                if fill_width > 0:
                    display.fill_rect(x, y, fill_width, height, 1)
                display.show()
                
                log(TAG_DISPLAY, f"Updated bar on display {display_index} to {value:.2f}")
            else:
                log(TAG_DISPLAY, f"Invalid display index: {display_index}", is_error=True)
        except Exception as e:
            log(TAG_DISPLAY, f"Error showing bar on display {display_index}: {str(e)}", is_error=True)

    def is_ready(self):
        """Check if displays are initialized and ready."""
        return len(self.displays) > 0

    def get_display_count(self):
        """Return the number of initialized displays."""
        return len(self.displays)
    
    def update_pot_value(self, pot_num, value):
        """Update a single pot value and mark its display for refresh.
        
        Args:
            pot_num: Which pot changed (0-15)
            value: New normalized value (0.0-1.0)
        """
        try:
            if 0 <= pot_num < 16:
                # Update stored value
                self.pot_values[pot_num] = value
                
                # Calculate which display position (0-3) this pot belongs to
                # Pots 0,1 -> position 0
                # Pots 2,3 -> position 1
                # Pots 4,5 -> position 2
                # Pots 6,7 -> position 3
                # Same pattern for pots 8-15
                display_position = (pot_num % 8) // 2
                
                # Get the channel number for this position from SCREEN_ORDER
                channel = SCREEN_ORDER[display_position]
                
                log(TAG_DISPLAY, f"Mapping pot {pot_num} -> display position {display_position} -> channel {channel}")
                
                # Find the display index that has this channel
                display_index = None
                for i, display in enumerate(self.displays):
                    if display['channel'] == channel:
                        display_index = i
                        break
                
                log(TAG_DISPLAY, f"Found display index {display_index} for pot {pot_num}")
                
                # Update display if found and initialized
                if display_index is not None and 0 <= display_index < len(self.displays):
                    self.update_display_with_config(display_index)
                    log(TAG_DISPLAY, f"Updated display {display_index} (channel {channel}, position {display_position}) for pot {pot_num}")
                
        except Exception as e:
            log(TAG_DISPLAY, f"Error updating pot {pot_num}: {str(e)}", is_error=True)
        
    def deinit(self):
        """Clean up resources."""
        try:
            # Clear all displays
            self.clear_all_displays()
            
            # Clean up I2C resources
            if hasattr(self, 'i2c'):
                try:
                    self.i2c.deinit()
                except:
                    pass
                    
            log(TAG_DISPLAY, "Display manager deinitialized")
        except Exception as e:
            log(TAG_DISPLAY, f"Error during display manager cleanup: {str(e)}", is_error=True)
