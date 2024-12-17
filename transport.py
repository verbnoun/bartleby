"""Transport management for UART communication in Bartleby."""

import busio
import time
from constants import MESSAGE_TIMEOUT, BUFFER_CLEAR_TIMEOUT
from logging import log, TAG_TRANS

class TransportManager:
    """Manages shared UART instance for both text and MIDI communication"""
    def __init__(self, tx_pin, rx_pin, baudrate=31250, timeout=0.001):
        log(TAG_TRANS, "Initializing shared transport manager")
        try:
            log(TAG_TRANS, f"Configuring UART: baudrate={baudrate}, timeout={timeout}")
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
            log(TAG_TRANS, "UART configuration successful")
        except Exception as e:
            log(TAG_TRANS, f"Failed to initialize UART: {str(e)}", is_error=True)
            self.uart_initialized = False
            raise
        
    def get_uart(self):
        """Get the UART instance for text or MIDI use"""
        if not self.uart_initialized:
            log(TAG_TRANS, "Attempted to get UART before initialization", is_error=True)
            return None
        return self.uart
        
    def flush_buffers(self):
        """Clear any pending data in UART buffers"""
        if not self.uart_initialized:
            log(TAG_TRANS, "Skipping buffer flush - UART not initialized")
            return
            
        try:
            log(TAG_TRANS, "Flushing UART buffers")
            start_time = time.monotonic()
            while (time.monotonic() - start_time) < BUFFER_CLEAR_TIMEOUT:
                if self.uart and self.uart.in_waiting:
                    self.uart.read()
                else:
                    break
            log(TAG_TRANS, "Buffer flush complete")
        except Exception as e:
            log(TAG_TRANS, f"Error during buffer flush: {str(e)}", is_error=True)
        
    def cleanup(self):
        """Clean shutdown of transport - only flush buffers, don't deinit UART"""
        if self.uart_initialized:
            log(TAG_TRANS, "Starting transport cleanup")
            try:
                self.flush_buffers()
                log(TAG_TRANS, "Transport cleanup complete")
            except Exception as e:
                log(TAG_TRANS, f"Error during cleanup: {str(e)}", is_error=True)

class TextUart:
    """Handles text-based UART communication for receiving config only"""
    def __init__(self, uart):
        try:
            self.uart = uart
            self.buffer = bytearray()
            self.last_write = 0
            self.message_start_time = None
            log(TAG_TRANS, "Text protocol initialized")
        except Exception as e:
            log(TAG_TRANS, f"Failed to initialize text protocol: {str(e)}", is_error=True)
            raise

    def write(self, message):
        """Write text message with minimum delay between writes"""
        try:
            current_time = time.monotonic()
            delay_needed = MESSAGE_TIMEOUT - (current_time - self.last_write)
            if delay_needed > 0:
                time.sleep(delay_needed)
                
            if isinstance(message, str):
                message = message.encode('utf-8')
            result = self.uart.write(message)
            self.last_write = time.monotonic()
            # Only log non-heartbeat messages by default
            if not message.startswith(b'\xe2\x99\xa1'):  # UTF-8 encoding of ♡
                log(TAG_TRANS, f"Wrote message of {len(message)} bytes")
            else:
                log(TAG_TRANS, "♡", is_heartbeat=True)
            return result
        except Exception as e:
            log(TAG_TRANS, f"Error writing message: {str(e)}", is_error=True)
            return 0

    def read(self):
        """Read available data and return complete messages, handling format [n[message]n]"""
        try:
            # If no data waiting, return None
            if not self.uart.in_waiting:
                return None

            # Read all available data
            data = self.uart.read()
            if not data:
                return None

            # Start timing when we first see data
            if self.message_start_time is None:
                self.message_start_time = time.monotonic()

            # Extend existing buffer
            self.buffer.extend(data)

            # Look for start of message
            while b'[' in self.buffer:
                start_idx = self.buffer.find(b'[')
                
                # Need at least 4 chars for minimal message [n[]]
                if len(self.buffer) < start_idx + 4:
                    # Check if we've been waiting too long for a complete message
                    if self.message_start_time and (time.monotonic() - self.message_start_time) > MESSAGE_TIMEOUT:
                        self.buffer = bytearray()
                        self.message_start_time = None
                    return None

                # Check if we have counter and second bracket
                if not self.buffer[start_idx + 1:start_idx + 2].isdigit():
                    # Invalid format, remove this start bracket and continue
                    self.buffer = self.buffer[start_idx + 1:]
                    continue

                if self.buffer[start_idx + 2:start_idx + 3] != b'[':
                    # Invalid format, remove this start bracket and continue
                    self.buffer = self.buffer[start_idx + 1:]
                    continue

                # Get the counter digit
                counter = self.buffer[start_idx + 1:start_idx + 2].decode()
                
                # Look for matching end sequence
                end_sequence = f"]{counter}]\n".encode()
                end_idx = self.buffer.find(end_sequence, start_idx + 3)
                
                if end_idx == -1:
                    # Check if we've been waiting too long for the end sequence
                    if self.message_start_time and (time.monotonic() - self.message_start_time) > MESSAGE_TIMEOUT:
                        self.buffer = bytearray()
                        self.message_start_time = None
                    # No complete message yet
                    if len(self.buffer) > 1024:  # Add safety limit to prevent buffer overflow
                        self.buffer = self.buffer[start_idx + 1:]
                    return None

                try:
                    # Extract message between inner brackets
                    message_bytes = self.buffer[start_idx + 3:end_idx]
                    
                    # Remove processed message from buffer
                    self.buffer = self.buffer[end_idx + len(end_sequence):]
                    
                    # Reset message start time
                    self.message_start_time = None
                    
                    # Decode the complete message
                    message = message_bytes.decode('utf-8')
                    
                    # Special handling for CC config messages
                    if '|cc|' in message:
                        parts = message.split('|')
                        if len(parts) > 3 and parts[2] == 'cc':
                            # Reconstruct message ensuring CC assignments are properly formatted
                            header = parts[:3]  # Cartridge, instrument, cc marker
                            cc_parts = []
                            
                            # Process CC assignments
                            for part in parts[3:]:
                                if not part:  # Skip empty parts
                                    continue
                                try:
                                    # First split on equals to get pot number
                                    if '=' not in part:
                                        continue
                                    pot_str, rest = part.split('=', 1)
                                    
                                    # Then split rest on first colon only
                                    if ':' not in rest:
                                        continue
                                    cc_str, name = rest.split(':', 1)
                                    
                                    # Validate numbers
                                    pot_num = int(pot_str)
                                    cc_num = int(cc_str)
                                    
                                    # Only add if all parts are valid
                                    cc_parts.append(f"{pot_num}={cc_num}:{name}")
                                except (ValueError, IndexError) as e:
                                    log(TAG_TRANS, f"Skipping invalid CC assignment: {part}", is_error=True)
                                    continue
                            
                            # Reconstruct message only if we have valid CC parts
                            if cc_parts:
                                message = f"{parts[0]}|{parts[1]}|cc|{'|'.join(cc_parts)}"
                            else:
                                log(TAG_TRANS, "No valid CC assignments found", is_error=True)
                                continue
                    
                    # Log appropriately
                    if message == '♡':
                        log(TAG_TRANS, "♡", is_heartbeat=True)
                    else:
                        log(TAG_TRANS, f"Received message: {message}")
                    
                    return message
                    
                except UnicodeDecodeError:
                    # If we can't decode the message, skip to next start bracket
                    self.buffer = self.buffer[start_idx + 1:]
                    continue

            return None

        except Exception as e:
            log(TAG_TRANS, f"Error in message reading: {str(e)}", is_error=True)
            self.buffer = bytearray()
            self.message_start_time = None
            return None

    def clear_buffer(self):
        """Clear the internal buffer"""
        try:
            self.buffer = bytearray()
            self.message_start_time = None
            log(TAG_TRANS, "Message buffer cleared")
        except Exception as e:
            log(TAG_TRANS, f"Error clearing buffer: {str(e)}", is_error=True)

    @property
    def in_waiting(self):
        try:
            return self.uart.in_waiting
        except Exception as e:
            log(TAG_TRANS, f"Error checking in_waiting: {str(e)}", is_error=True)
            return 0
