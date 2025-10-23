import serial
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import time

# Configuration parameters
SERIAL_PORT = '/dev/cu.wchusbserial59090740691'  # Change to your serial port
BAUD_RATE = 1500000                      # Must match ESP32 baud rate
BUFFER_SIZE = 4096                       # Buffer size for better frequency resolution
SAMPLE_RATE = 48000                     # Sampling rate
PLOT_REFRESH_RATE = 300                  # Plot refresh rate (ms)
MAX_FREQ = 1200                         # Maximum frequency to display

# Initialize serial port
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"Successfully connected to serial port {SERIAL_PORT}")
    
    # 清空串口缓冲区
    ser.reset_input_buffer()
    time.sleep(0.1)  # 等待缓冲区清空
    
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

# 同步状态变量
sync_lost = False
sync_attempts = 0
MAX_SYNC_ATTEMPTS = 10

def find_sync():
    """寻找数据同步点"""
    global sync_attempts
    
    print("寻找数据同步点...")
    sync_buffer = bytearray()
    
    # 读取足够的数据来寻找同步模式
    while len(sync_buffer) < BUFFER_SIZE * 4:
        sync_buffer.extend(ser.read(ser.in_waiting or 1))
    
    # 寻找可能的同步模式（连续几个接近0的采样值）
    best_position = 0
    best_score = 0
    
    for start in range(0, len(sync_buffer) - BUFFER_SIZE * 2, 2):
        try:
            # 尝试从不同位置解析数据
            test_data = np.frombuffer(sync_buffer[start:start + BUFFER_SIZE * 2], dtype=np.int16)
            
            # 计算同步分数：数据不应该全是极值
            extreme_count = np.sum(np.abs(test_data) > 30000)
            zero_crossings = np.sum(np.diff(np.signbit(test_data)))
            
            score = zero_crossings - extreme_count * 10
            
            if score > best_score:
                best_score = score
                best_position = start
        
        except ValueError:
            continue
    
    # 丢弃最佳位置之前的数据
    if best_position > 0:
        ser.read(best_position)
        print(f"丢弃 {best_position} 字节数据以实现同步")
    
    return best_score > 0

def init():
    """Initialize animation"""
    line_time.set_ydata(np.zeros(BUFFER_SIZE))
    line_freq.set_ydata(np.zeros(len(xf)))
    return line_time, line_freq

def update(frame):
    """Update plots"""
    global audio_buffer, sync_lost, sync_attempts
    
    # 检查同步状态
    if sync_lost and sync_attempts < MAX_SYNC_ATTEMPTS:
        if find_sync():
            sync_lost = False
            print("同步恢复成功")
        else:
            sync_attempts += 1
        return line_time, line_freq
    
    # Read data from serial port
    bytes_to_read = BUFFER_SIZE * 2
    raw_data = ser.read(bytes_to_read)
    
    if len(raw_data) == bytes_to_read:
        try:
            # Convert to numpy array
            audio_buffer = np.frombuffer(raw_data, dtype=np.int16)
            
            # 检查数据是否合理（同步检测）
            max_val = np.max(np.abs(audio_buffer))
            zero_crossings = np.sum(np.diff(np.signbit(audio_buffer)))
            
            # 如果数据全是极值或没有过零，认为同步丢失
            if max_val > 32000 and zero_crossings < 10:
                sync_lost = True
                sync_attempts = 0
                print("检测到同步丢失，尝试重新同步...")
                return line_time, line_freq
            
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
            
        except Exception as e:
            print(f"数据处理错误: {e}")
            sync_lost = True
    
    elif len(raw_data) > 0:
        # 读取到不完整的数据包，丢弃并重新同步
        print(f"收到不完整数据包: {len(raw_data)}/{bytes_to_read} 字节")
        sync_lost = True
    
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

try:
    plt.show()
except KeyboardInterrupt:
    print("程序被用户中断")

# Close serial port
ser.close()
print("Serial port closed")