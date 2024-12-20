"""OLED display management through I2C multiplexer."""

import time
import busio
import board
from adafruit_ssd1306 import SSD1306_I2C
from adafruit_tca9548a import TCA9548A
from constants import (
    I2C_SDA, I2C_SCL, I2C_MUX_ADDRESS, OLED_ADDRESS,
    OLED_WIDTH, OLED_HEIGHT, OLED_CHANNELS
)
from logging import log

# Create a new logging tag for display operations
TAG_DISPLAY = "DISPLAY "  # Must be 8 chars (spaces ok)

class DisplayManager:
    def __init__(self):
        """Initialize I2C multiplexer and OLED displays."""
        try:
            log(TAG_DISPLAY, "Initializing display manager")
            
            # Initialize displays array
            self.displays = []
            
            # Initialize I2C bus and multiplexer
            self.i2c = busio.I2C(I2C_SCL, I2C_SDA)
            self.mux = TCA9548A(self.i2c, address=I2C_MUX_ADDRESS)
            
            # Initialize displays on each channel
            for channel in OLED_CHANNELS:
                try:
                    # Select channel on multiplexer
                    if self.i2c.try_lock():
                        try:
                            self.i2c.writeto(I2C_MUX_ADDRESS, bytes([1 << channel]))
                            time.sleep(0.1)  # Allow channel to settle
                        finally:
                            self.i2c.unlock()
                    
                    # Create the OLED display object using main I2C bus
                    display = SSD1306_I2C(
                        OLED_WIDTH, OLED_HEIGHT,
                        self.i2c,
                        addr=OLED_ADDRESS
                    )
                    
                    # Store display with its channel number
                    self.displays.append({
                        'display': display,
                        'channel': channel
                    })
                    log(TAG_DISPLAY, f"Initialized display on channel {channel}")
                    
                except Exception as e:
                    log(TAG_DISPLAY, f"Failed to initialize display on channel {channel}: {str(e)}", is_error=True)
            
            log(TAG_DISPLAY, f"Display manager initialization complete. {len(self.displays)} displays ready")
            
        except Exception as e:
            log(TAG_DISPLAY, f"Display manager initialization failed: {str(e)}", is_error=True)
            raise

    def _select_channel(self, channel):
        """Select multiplexer channel with proper locking."""
        if self.i2c.try_lock():
            try:
                self.i2c.writeto(I2C_MUX_ADDRESS, bytes([1 << channel]))
                time.sleep(0.1)  # Allow channel to settle
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
