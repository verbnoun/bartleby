import board
import storage
import usb_midi
import usb_cdc
import supervisor

# Enable auto-reload for development
supervisor.runtime.autoreload = True

# Disable default USB endpoints we won't use
storage.disable_usb_drive()  # Disable USB drive
usb_cdc.disable()           # Disable USB serial

# Configure USB pins for external USB-C port
board.CUSTOM_USB_DP = board.GP17  # D+
board.CUSTOM_USB_DM = board.GP18  # D-

# Enable USB MIDI mode
usb_midi.enable()