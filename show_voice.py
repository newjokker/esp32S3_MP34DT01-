import serial
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

# Configuration parameters
SERIAL_PORT = '/dev/cu.wchusbserial59090740691'  # Change to your serial port
BAUD_RATE = 460800                      # Must match ESP32 baud rate
BUFFER_SIZE = 1024                      # Buffer size, match ESP32 code
SAMPLE_RATE = 16000                     # Sampling rate
PLOT_REFRESH_RATE = 30                  # Plot refresh rate (ms)

# Initialize serial port
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Successfully connected to serial port {SERIAL_PORT}")
except serial.SerialException as e:
    print(f"Failed to open serial port {SERIAL_PORT}: {e}")
    exit(1)

# Create figure and subplots
fig, (ax_time, ax_freq) = plt.subplots(2, 1, figsize=(12, 8))
plt.subplots_adjust(hspace=0.5)

# Time domain plot settings
x_time = np.arange(0, BUFFER_SIZE)
line_time, = ax_time.plot(x_time, np.zeros(BUFFER_SIZE), 'b-', lw=1)
ax_time.set_title('Time Domain Signal')
ax_time.set_xlim(0, BUFFER_SIZE)
# ax_time.set_ylim(-32768, 32767)  # 16-bit signed integer range
ax_time.set_ylim(-40000, 40000)  # 16-bit signed integer range
ax_time.set_xlabel('Sample Points')
ax_time.set_ylabel('Amplitude')
ax_time.grid(True)

# Frequency domain plot settings
N = BUFFER_SIZE
xf = np.linspace(0, SAMPLE_RATE//2, N//2)
line_freq, = ax_freq.plot(xf, np.zeros(N//2), 'r-', lw=1)
ax_freq.set_title('Frequency Domain (FFT)')
ax_freq.set_xlim(1, 4000)  # Show audible frequency range
ax_freq.set_ylim(0, 5*1e6)              # Adjust based on actual signal
ax_freq.set_xlabel('Frequency (Hz)')
ax_freq.set_ylabel('Magnitude')
ax_freq.grid(True)

# Data buffer
audio_buffer = np.zeros(BUFFER_SIZE, dtype=np.int16)

def init():
    """Initialize animation"""
    line_time.set_ydata(np.zeros(BUFFER_SIZE))
    line_freq.set_ydata(np.zeros(BUFFER_SIZE//2))
    return line_time, line_freq

def update(frame):
    """Update plots"""
    global audio_buffer
    
    # Read data from serial port
    raw_data = ser.read(BUFFER_SIZE * 2)  # 2 bytes per sample
    
    if len(raw_data) == BUFFER_SIZE * 2:
        # Convert to numpy array
        audio_buffer = np.frombuffer(raw_data, dtype=np.int16)
        
        # Update time domain plot
        line_time.set_ydata(audio_buffer)
        
        # Calculate FFT
        fft_data = np.abs(np.fft.fft(audio_buffer))[:N//2]
        
        # Smoothing (optional)
        fft_smoothed = np.convolve(fft_data, np.ones(5)/5, mode='same')
        
        # Update frequency domain plot
        line_freq.set_ydata(fft_smoothed)
    
    return line_time, line_freq

# Create animation
ani = FuncAnimation(
    fig, 
    update, 
    init_func=init,
    interval=PLOT_REFRESH_RATE, 
    blit=True,
    cache_frame_data=False
)

plt.suptitle('ESP32 Audio Real-time Analysis (Sample Rate: {} Hz)'.format(SAMPLE_RATE))
plt.tight_layout()
plt.show()

# Close serial port
ser.close()
print("Serial port closed")