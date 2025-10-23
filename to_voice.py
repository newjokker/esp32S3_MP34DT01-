import serial
import wave
import time
import sys
import struct
from datetime import datetime

# 配置参数
SERIAL_PORT = '/dev/cu.wchusbserial59090740691'  # 替换为你的串口号
BAUD_RATE = 1500000
BUFFER_SIZE = 1024  # 与Arduino代码中的BUFFER_SIZE一致
SAMPLE_RATE = 48000  # 采样率
CHANNELS = 1         # 单声道
SAMPLE_WIDTH = 2     # 16位 = 2字节
WAV_FILE = f'recording_{datetime.now().strftime("%Y%m%d_%H%M%S")}.wav'
RECORD_SECONDS = 10  # 录制时长(秒)
TIMEOUT = 0.1        # 串口超时时间(秒)

def main():
    print(f"准备录制 {RECORD_SECONDS} 秒音频...")
    print(f"采样率: {SAMPLE_RATE}Hz, 位深度: {SAMPLE_WIDTH*8}bit, 声道数: {CHANNELS}")
    
    try:
        # 打开串口
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
        print(f"已连接到串口: {ser.name}")
        print(f"串口设置: {ser.get_settings()}")
        
        # 创建WAV文件
        wf = wave.open(WAV_FILE, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        
        print(f"\n开始录制 (将保存到: {WAV_FILE})")
        start_time = time.time()
        total_bytes = 0
        expected_bytes = SAMPLE_RATE * SAMPLE_WIDTH * RECORD_SECONDS
        
        # 先清空串口缓冲区
        ser.reset_input_buffer()
        
        while time.time() - start_time < RECORD_SECONDS:
            # 计算剩余时间
            remaining = RECORD_SECONDS - (time.time() - start_time)
            
            # 计算本次需要读取的字节数
            bytes_to_read = min(BUFFER_SIZE * SAMPLE_WIDTH, 
                               int(remaining * SAMPLE_RATE * SAMPLE_WIDTH))
            
            # 从串口读取数据
            data = ser.read(bytes_to_read)
            bytes_read = len(data)
            total_bytes += bytes_read
            
            if bytes_read > 0:
                wf.writeframes(data)
            
            # 显示进度
            progress = min(100, (total_bytes / expected_bytes) * 100)
            sys.stdout.write(
                f"\r进度: {progress:.1f}% | "
                f"已接收: {total_bytes/(1024):.1f}KB/{expected_bytes/(1024):.1f}KB | "
                f"时间: {time.time()-start_time:.1f}s/{RECORD_SECONDS}s"
            )
            sys.stdout.flush()
            
            # 如果读取超时但没有数据，可能是连接问题
            if bytes_read == 0 and time.time() - start_time > 1:
                print("\n警告: 串口读取超时，可能数据流中断")
                break
        
        # 关闭文件
        wf.close()
        ser.close()
        
        # 验证实际录制时长
        actual_seconds = total_bytes / (SAMPLE_RATE * SAMPLE_WIDTH)
        print(f"\n\n录制完成! 实际录制时长: {actual_seconds:.2f}秒")
        print(f"音频已保存到: {WAV_FILE}")
        
        if actual_seconds < RECORD_SECONDS * 0.9:
            print(f"警告: 实际录制时长不足预期时长的90%，可能是数据传输问题")
            print("可能原因:")
            print("1. 波特率设置过高导致数据丢失")
            print("2. Arduino端数据处理不及时")
            print("3. 串口连接不稳定")
            print("建议:")
            print("- 尝试降低波特率")
            print("- 检查Arduino端的代码和硬件性能")
            print("- 使用更短的USB线或更好的串口转换器")
        
    except serial.SerialException as e:
        print(f"\n串口错误: {e}")
    except wave.Error as e:
        print(f"\nWAV文件错误: {e}")
    except Exception as e:
        print(f"\n发生错误: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        if 'wf' in locals():
            wf.close()

if __name__ == '__main__':
    main()