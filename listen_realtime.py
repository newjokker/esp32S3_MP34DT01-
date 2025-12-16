import sounddevice as sd
import numpy as np
import serial
import time
import sys

# 与ESP32代码匹配的配置
SERIAL_PORT = '/dev/cu.wchusbserial59090740691'
BAUD_RATE = 1500000
SAMPLE_RATE = 48000
CHANNELS = 1
BUFFER_SIZE = 1024  # 与ESP32的BUFFER_SIZE一致

def main():
    print(f"ESP32麦克风实时播放")
    print(f"采样率: {SAMPLE_RATE}Hz, 波特率: {BAUD_RATE}")
    
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
        
        try:
            while True:
                # 读取数据 - ESP32发送的是BUFFER_SIZE个int16样本
                expected_bytes = BUFFER_SIZE * 2  # 每个int16是2字节
                data = ser.read(expected_bytes)
                
                if data:
                    bytes_received += len(data)
                    
                    # 处理数据
                    if len(data) >= 4:  # 至少2个样本
                        # 转换为int16数组
                        audio = np.frombuffer(data, dtype=np.int16)
                        
                        # 音量调节（防止破音）
                        max_val = np.max(np.abs(audio))
                        if max_val > 0:
                            # 自动增益，目标峰值20000
                            gain = min(20000.0 / max_val, 1.0)  # 不超过原始音量
                            audio = (audio.astype(np.float32) * gain).astype(np.int16)
                        
                        # 播放
                        stream.write(audio)
                    
                    # 显示状态
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        kbps = bytes_received / elapsed / 1024
                        sys.stdout.write(f"\r接收: {bytes_received/1024:.1f}KB 速率: {kbps:.1f}KB/s")
                        sys.stdout.flush()
                else:
                    time.sleep(0.001)
                    
        except KeyboardInterrupt:
            print("\n\n正在停止...")
            
    except Exception as e:
        print(f"\n错误: {e}")
    finally:
        if 'stream' in locals():
            stream.stop()
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print("已停止")

if __name__ == "__main__":
    main()