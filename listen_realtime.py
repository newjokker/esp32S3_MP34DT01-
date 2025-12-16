import sounddevice as sd
import numpy as np
import serial
import time
import sys
import argparse

# 与ESP32代码匹配的配置
SERIAL_PORT = '/dev/cu.wchusbserial59090740691'
BAUD_RATE = 1500000
SAMPLE_RATE = 48000
CHANNELS = 1
BUFFER_SIZE = 1024  # 与ESP32的BUFFER_SIZE一致

def main(gain_db=0.0):
    """
    参数:
    - gain_db: 增益分贝值，可以为正（放大）或负（衰减）
    """
    print(f"ESP32麦克风实时播放")
    print(f"采样率: {SAMPLE_RATE}Hz, 波特率: {BAUD_RATE}")
    print(f"增益: {gain_db:.1f}dB")
    
    # 将分贝转换为线性增益倍数
    # 公式: gain_linear = 10^(gain_db/20)
    gain_linear = 10 ** (gain_db / 20.0)
    print(f"线性增益倍数: {gain_linear:.2f}x")
    
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
                        
                        # 应用用户指定的固定增益
                        if gain_db != 0:
                            audio = np.clip(audio.astype(np.float32) * gain_linear, 
                                          -32768, 32767).astype(np.int16)
                        
                        # 计算峰值和音量
                        if len(audio) > 0:
                            current_peak = np.max(np.abs(audio))
                            volume_percent = (current_peak / 32767) * 100
                        
                        # 播放
                        stream.write(audio)
                    
                    # 每0.5秒显示一次状态
                    current_time = time.time()
                    elapsed_total = current_time - start_time
                    
                    if current_time - last_status_time >= 0.2:
                        if elapsed_total > 0 and 'current_peak' in locals():
                            kbps = bytes_received / elapsed_total / 1024
                            sys.stdout.write(f"\r接收: {bytes_received/1024:.1f}KB "
                                           f"速率: {kbps:.1f}KB/s "
                                           f"音量: {volume_percent:.1f}% "
                                           f"峰值: {current_peak}          ")
                            sys.stdout.flush()
                        last_status_time = current_time
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
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='ESP32麦克风实时播放器')
    parser.add_argument('--gain', type=float, default=16.0, 
                       help='增益分贝值，例如：6.0表示+6dB放大')
    
    args = parser.parse_args()
    
    # 运行主程序
    main(gain_db=args.gain)