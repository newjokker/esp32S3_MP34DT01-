import sounddevice as sd
import numpy as np
import serial
import time
import sys
import math
from scipy import signal
import warnings
warnings.filterwarnings("ignore")

# 与ESP32代码匹配的配置
SERIAL_PORT = '/dev/cu.wchusbserial59090740691'
BAUD_RATE = 1500000
SAMPLE_RATE = 48000
CHANNELS = 1
BUFFER_SIZE = 1024  # 与ESP32的BUFFER_SIZE一致

# ========== 简化的用户参数 ==========
# 先简化参数，确保基本功能正常
GAIN_DB = 20.0                     # 增益分贝值
FILTER_TYPE = 'bandpass'          # 只使用简单的滤波器类型
FREQ_LOW = 100.0                  # 低切频率
FREQ_HIGH = 3000.0                # 高切频率
# 暂时禁用高级功能
COMPRESSION_ENABLED = False       # 暂时禁用压缩
NOISE_REDUCTION_ENABLED = False   # 暂时禁用噪声抑制
VOICE_ENHANCE_ENABLED = False     # 暂时禁用语增强
SHOW_SPECTRUM = False             # 暂时禁用频谱显示
# ===================================

class SimpleAudioProcessor:
    """简化版音频处理器，确保实时性"""
    def __init__(self, sample_rate=SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.nyquist = sample_rate / 2.0
        
        # 初始化简单的滤波器
        self.b = None
        self.a = None
        self.zi = None
        
        # 初始化增益
        self.gain_linear = 10 ** (GAIN_DB / 20.0)
        
        self._init_filter()
        print("=" * 50)
        print("简化版音频处理器初始化")
        print(f"采样率: {sample_rate}Hz")
        print(f"滤波器: {FILTER_TYPE} ({FREQ_LOW}-{FREQ_HIGH}Hz)")
        print(f"增益: {GAIN_DB:.1f}dB ({self.gain_linear:.1f}x)")
        print("=" * 50)
    
    def _init_filter(self):
        """初始化简单的滤波器"""
        if FILTER_TYPE == 'none':
            return
            
        if FILTER_TYPE == 'bandpass':
            low = FREQ_LOW / self.nyquist
            high = FREQ_HIGH / self.nyquist
            if low < 1.0 and high < 1.0 and low < high:
                self.b, self.a = signal.butter(4, [low, high], btype='bandpass')
                self.zi = signal.lfilter_zi(self.b, self.a)
        elif FILTER_TYPE == 'lowpass':
            norm_freq = FREQ_HIGH / self.nyquist
            if norm_freq < 1.0:
                self.b, self.a = signal.butter(4, norm_freq, btype='low')
                self.zi = signal.lfilter_zi(self.b, self.a)
        elif FILTER_TYPE == 'highpass':
            norm_freq = FREQ_LOW / self.nyquist
            if norm_freq < 1.0:
                self.b, self.a = signal.butter(4, norm_freq, btype='high')
                self.zi = signal.lfilter_zi(self.b, self.a)
    
    def process_audio(self, audio_data):
        """处理音频数据 - 简化版"""
        if FILTER_TYPE == 'none' or self.b is None:
            filtered = audio_data
        else:
            # 转换为浮点数
            audio_float = audio_data.astype(np.float32) / 32768.0
            
            # 应用滤波器
            filtered_float, self.zi = signal.lfilter(
                self.b, self.a, 
                audio_float, 
                zi=self.zi
            )
            
            # 转换回int16
            filtered = np.clip(filtered_float * 32768.0, -32768, 32767).astype(np.int16)
        
        # 应用增益
        if self.gain_linear != 1.0:
            processed = np.clip(
                filtered.astype(np.float32) * self.gain_linear,
                -32768, 32767
            ).astype(np.int16)
        else:
            processed = filtered
            
        return processed

def main():
    """主函数"""
    print("ESP32麦克风实时播放器 (简化版)")
    print(f"串口: {SERIAL_PORT}")
    print(f"波特率: {BAUD_RATE}")
    print(f"采样率: {SAMPLE_RATE}Hz")
    print(f"增益: {GAIN_DB:.1f}dB")
    print(f"滤波器: {FILTER_TYPE} ({FREQ_LOW}-{FREQ_HIGH}Hz)")
    print("-" * 50)
    
    # 初始化音频处理器
    processor = SimpleAudioProcessor()
    
    try:
        # 打开串口
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        print(f"✓ 已连接串口: {ser.name}")
        
        # 清空缓冲区
        ser.reset_input_buffer()
        time.sleep(0.5)
        
        # 创建音频输出流
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16',
            blocksize=BUFFER_SIZE
        )
        stream.start()
        
        print("开始播放... (按Ctrl+C停止)")
        print("-" * 50)
        
        bytes_received = 0
        start_time = time.time()
        last_status_time = time.time()
        
        # 调试计数器
        data_received_counter = 0
        no_data_counter = 0
        
        try:
            while True:
                # 读取数据
                expected_bytes = BUFFER_SIZE * 2
                data = ser.read(expected_bytes)
                
                if data:
                    bytes_received += len(data)
                    data_received_counter += 1
                    no_data_counter = 0
                    
                    # 检查数据长度
                    if len(data) < 4:
                        continue
                    
                    # 转换为int16数组
                    try:
                        audio = np.frombuffer(data, dtype=np.int16)
                    except:
                        print("数据转换错误，跳过")
                        continue
                    
                    # 处理音频
                    processed_audio = processor.process_audio(audio)
                    
                    # 播放音频
                    try:
                        stream.write(processed_audio)
                    except Exception as e:
                        print(f"播放错误: {e}")
                        continue
                    
                    # 显示状态
                    current_time = time.time()
                    elapsed_total = current_time - start_time
                    
                    if current_time - last_status_time >= 0.5:
                        if elapsed_total > 0:
                            kbps = bytes_received / elapsed_total / 1024
                            
                            # 计算音量
                            if len(audio) > 0:
                                rms = np.sqrt(np.mean(audio.astype(np.float32)**2))
                                volume = (rms / 32767) * 100
                                
                                # 简单的音量条
                                bar_length = 20
                                filled_length = int(bar_length * volume / 100)
                                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                                
                                # 状态信息
                                status = (f"\r数据包: {data_received_counter} | "
                                        f"速率: {kbps:.1f}KB/s | "
                                        f"音量: {volume:.1f}% [{bar}]")
                                sys.stdout.write(status)
                                sys.stdout.flush()
                        
                        last_status_time = current_time
                else:
                    no_data_counter += 1
                    if no_data_counter > 100:  # 连续100次无数据
                        print(f"\n警告: 连续{no_data_counter}次无数据，检查连接")
                        no_data_counter = 0
                    
                    time.sleep(0.001)
                    
        except KeyboardInterrupt:
            print("\n\n正在停止...")
        except Exception as e:
            print(f"\n处理错误: {e}")
            import traceback
            traceback.print_exc()
            
    except serial.SerialException as e:
        print(f"串口错误: {e}")
        print("请检查:")
        print(f"1. 串口设备 {SERIAL_PORT} 是否存在")
        print(f"2. ESP32是否正确连接")
        print(f"3. 是否被其他程序占用")
        
        # 列出可用串口
        import glob
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            ports = []
        
        print("可用的串口:")
        for port in ports:
            print(f"  {port}")
            
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if 'stream' in locals():
            try:
                stream.stop()
                stream.close()
            except:
                pass
        if 'ser' in locals() and hasattr(ser, 'is_open') and ser.is_open:
            try:
                ser.close()
            except:
                pass
        
        print("已停止")

# 调试函数，测试音频输出是否正常
def test_audio_output():
    """测试音频输出是否正常工作"""
    print("测试音频输出...")
    try:
        # 生成测试信号
        duration = 1.0
        samples = int(SAMPLE_RATE * duration)
        t = np.linspace(0, duration, samples, endpoint=False)
        test_signal = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440Hz正弦波
        test_signal = (test_signal * 32767).astype(np.int16)
        
        # 播放测试信号
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16'
        )
        stream.start()
        print("播放440Hz测试音...")
        stream.write(test_signal)
        time.sleep(1)
        stream.stop()
        stream.close()
        print("✓ 音频输出正常")
        return True
    except Exception as e:
        print(f"✗ 音频输出测试失败: {e}")
        return False

# 调试函数，测试串口连接
def test_serial_connection():
    """测试串口连接"""
    print(f"测试串口 {SERIAL_PORT}...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"✓ 串口连接成功")
        
        # 清空缓冲区
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # 尝试读取一些数据
        print("等待ESP32数据...")
        start_time = time.time()
        data_received = 0
        
        while time.time() - start_time < 3:  # 等待3秒
            data = ser.read(1024)
            if data:
                data_received += len(data)
                print(f"收到 {len(data)} 字节数据")
        
        if data_received > 0:
            print(f"✓ 串口数据传输正常，共收到 {data_received} 字节")
        else:
            print("⚠ 串口连接正常，但未收到数据")
            print("请检查ESP32是否正在发送数据")
        
        ser.close()
        return data_received > 0
    except Exception as e:
        print(f"✗ 串口连接失败: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("ESP32麦克风播放器 - 简化版")
    print("=" * 60)
    
    # 可选：运行测试
    run_tests = True  # 设置为True运行测试
    
    if run_tests:
        # 运行测试
        print("\n运行系统测试...")
        audio_ok = test_audio_output()
        serial_ok = test_serial_connection()
        
        # FIXME: 有时候会输出非常大的噪音，当音量持续在 0.5s 内有一半大于 20% 就直接重新运行了
        
        if audio_ok and serial_ok:
            print("\n✓ 所有测试通过，开始主程序...")
            print("-" * 60)
            time.sleep(1)
        else:
            print("\n⚠ 测试失败，请检查问题后再运行")
            sys.exit(1)
    
    # 运行主程序
    main()