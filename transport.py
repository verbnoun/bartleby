import busio
import time
from constants import MESSAGE_TIMEOUT, BUFFER_CLEAR_TIMEOUT
from connection import get_precise_time
from logging import log, TAG_TRANS

class TransportManager:
    """Manages shared UART instance for both text and MIDI communication"""
    def __init__(self, tx_pin, rx_pin, baudrate=31250, timeout=0.001):
        print("Initializing shared transport...")  # Keep critical system message
        log(TAG_TRANS, "Initializing UART configuration...")
        self.uart = busio.UART(
            tx=tx_pin,
            rx=rx_pin,
            baudrate=baudrate,
            timeout=timeout,
            bits=8,
            parity=None,
            stop=1
        )
        self.uart_initialized = True
        log(TAG_TRANS, "Transport initialized successfully")
        
    def get_uart(self):
        """Get the UART instance for text or MIDI use"""
        return self.uart
        
    def flush_buffers(self):
        """Clear any pending data in UART buffers"""
        if not self.uart_initialized:
            return
        try:
            start_time = get_precise_time()
            while (get_precise_time() - start_time) < (BUFFER_CLEAR_TIMEOUT * 1_000_000_000):  # Convert to ns
                if self.uart and self.uart.in_waiting:
                    self.uart.read()
                else:
                    break
        except Exception:
            # If we hit an error trying to flush, the UART is likely already deinitialized
            pass
        
    def cleanup(self):
        """Clean shutdown of transport"""
        if self.uart_initialized:
            try:
                self.flush_buffers()
                if self.uart:
                    self.uart.deinit()
            except Exception:
                # If we hit an error, the UART is likely already deinitialized
                pass
            finally:
                self.uart = None
                self.uart_initialized = False

class TextUart:
    """Handles text-based UART communication for receiving config only"""
    def __init__(self, uart):
        self.uart = uart
        self.buffer = bytearray()
        self.last_write = 0
        log(TAG_TRANS, "Text protocol initialized")

    def write(self, message):
        """Write text message with minimum delay between writes"""
        current_time = get_precise_time()
        delay_needed = (MESSAGE_TIMEOUT * 1_000_000_000) - (current_time - self.last_write)  # Convert to ns
        if delay_needed > 0:
            time.sleep(delay_needed / 1_000_000_000)  # Convert back to seconds
            
        if isinstance(message, str):
            message = message.encode('utf-8')
        result = self.uart.write(message)
        self.last_write = get_precise_time()
        return result

    def read(self):
        """Read available data and return complete messages, with improved resilience"""
        try:
            # If no data waiting, return None
            if not self.uart.in_waiting:
                return None

            # Read all available data
            data = self.uart.read()
            if not data:
                return None

            # Extend existing buffer
            self.buffer.extend(data)

            # Try to find a complete message (ending with newline)
            if b'\n' in self.buffer:
                # Split on first newline
                message, self.buffer = self.buffer.split(b'\n', 1)
                
                try:
                    # Attempt to decode and strip the message
                    decoded_message = message.decode('utf-8').strip()
                    
                    # Basic sanity check: message is not empty
                    if decoded_message:
                        return decoded_message
                except UnicodeDecodeError:
                    # If decoding fails, clear buffer to prevent accumulation of garbage
                    self.buffer = bytearray()
                    log(TAG_TRANS, "Received non-UTF8 data, buffer cleared", is_error=True)

            # No complete message, return None
            return None

        except Exception as e:
            # Catch any unexpected errors
            log(TAG_TRANS, f"Error in message reading: {e}", is_error=True)
            # Clear buffer to prevent repeated errors
            self.buffer = bytearray()
            return None

    def clear_buffer(self):
        """Clear the internal buffer"""
        self.buffer = bytearray()

    @property
    def in_waiting(self):
        try:
            return self.uart.in_waiting
        except Exception:
            return 0
