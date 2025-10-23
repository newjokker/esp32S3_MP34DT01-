import serial
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Configuration parameters
SERIAL_PORT = '/dev/cu.wchusbserial59090740691'  # Change to your serial port
BAUD_RATE = 1500000                      # Must match ESP32 baud rate
BUFFER_SIZE = 4096                       # Buffer size for better frequency resolution
SAMPLE_RATE = 48000                     # Sampling rate
PLOT_REFRESH_RATE = 300                  # Plot refresh rate (ms)
MAX_FREQ = 1000                         # Maximum frequency to display

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
ax_time.set_ylim(-40000, 40000)
ax_time.set_xlabel('Sample Points')
ax_time.set_ylabel('Amplitude')
ax_time.grid(True)

# Frequency domain plot settings
N = BUFFER_SIZE
xf = np.fft.fftfreq(N, 1/SAMPLE_RATE)[:N//2]
# Find index where frequency exceeds MAX_FREQ
max_idx = np.argmax(xf > MAX_FREQ) if any(xf > MAX_FREQ) else len(xf)
xf = xf[:max_idx]
line_freq, = ax_freq.plot(xf, np.zeros(len(xf)), 'r-', lw=1)  # Linear scale
ax_freq.set_title(f'Frequency Domain (FFT, 0-{MAX_FREQ}Hz)')
ax_freq.set_xlim(0, MAX_FREQ)
ax_freq.set_ylim(0, 2e6)              # Adjust based on your signal amplitude
ax_freq.set_xlabel('Frequency (Hz)')
ax_freq.set_ylabel('Magnitude')
ax_freq.grid(True)

# Data buffer
audio_buffer = np.zeros(BUFFER_SIZE, dtype=np.int16)

def init():
    """Initialize animation"""
    line_time.set_ydata(np.zeros(BUFFER_SIZE))
    line_freq.set_ydata(np.zeros(len(xf)))
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
        
        # Apply window function to reduce spectral leakage
        window = np.hanning(BUFFER_SIZE)
        windowed_data = audio_buffer * window
        
        # Calculate FFT
        fft_data = np.abs(np.fft.fft(windowed_data)[:N//2])
        fft_data = fft_data[:max_idx]  # Truncate to MAX_FREQ
        
        # Update frequency domain plot
        line_freq.set_ydata(fft_data)
    
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

plt.suptitle(f'ESP32 Audio Real-time Analysis (Sample Rate: {SAMPLE_RATE} Hz, Refresh: {PLOT_REFRESH_RATE}ms)')
plt.tight_layout()
plt.show()

# Close serial port
ser.close()
print("Serial port closed")