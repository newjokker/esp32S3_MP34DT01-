

import serial
import wave
import time
import sys
import struct
import numpy as np
from datetime import datetime

# 配置参数
SERIAL_PORT = '/dev/cu.wchusbserial59090740691'
BAUD_RATE = 1500000
BUFFER_SIZE = 1024
SAMPLE_RATE = 48000
CHANNELS = 1
SAMPLE_WIDTH = 2
WAV_FILE = f'recording_{datetime.now().strftime("%Y%m%d_%H%M%S")}.wav'
RECORD_SECONDS = 10
TIMEOUT = 0.1
VOLUME_GAIN = 8.0  # 音量增益倍数，2.0表示两倍音量

def apply_volume_gain(audio_data, gain):
    """应用音量增益，防止削波"""
    amplified = audio_data.astype(np.float32) * gain
    
    # 限制在int16范围内防止削波
    amplified = np.clip(amplified, -32768, 32767)
    
    return amplified.astype(np.int16)

def find_sync_point(ser, sample_rate, sample_width, search_time=1.0):
    """寻找数据同步点"""
    print("正在寻找数据同步点...")
    
    # 收集足够的数据进行同步分析
    bytes_to_collect = int(sample_rate * sample_width * search_time)
    sync_buffer = bytearray()
    
    start_time = time.time()
    while len(sync_buffer) < bytes_to_collect and (time.time() - start_time) < search_time * 2:
        sync_buffer.extend(ser.read(ser.in_waiting or 1))
    
    if len(sync_buffer) < 100:  # 至少需要一些数据
        print("警告: 无法获取足够的数据进行同步")
        return 0
    
    best_offset = 0
    best_score = -float('inf')
    
    # 尝试不同的字节偏移（0或1）
    for offset in [0, 1]:
        score = 0
        valid_samples = 0
        
        try:
            # 从偏移位置开始解析数据
            test_data = np.frombuffer(sync_buffer[offset:], dtype=np.int16)
            
            if len(test_data) < 50:
                continue
                
            # 计算同步分数
            # 1. 正常音频信号应该有合理的幅值分布
            abs_max = np.max(np.abs(test_data))
            if abs_max > 32000:  # 接近最大值，可能是错位
                score -= 1000
            else:
                score += 100
            
            # 2. 检查过零点（音频信号的特征）
            zero_crossings = np.sum(np.diff(np.signbit(test_data.astype(np.float32))))
            expected_crossings = len(test_data) * 0.1  # 预期至少有10%的过零点
            if zero_crossings > expected_crossings:
                score += zero_crossings * 2
            
            # 3. 检查数据变化（不应该全是相同的值）
            unique_ratio = len(np.unique(test_data)) / len(test_data)
            score += unique_ratio * 500
            
            print(f"偏移 {offset}: 分数={score}, 最大值={abs_max}, 过零点={zero_crossings}")
            
            if score > best_score:
                best_score = score
                best_offset = offset
                
        except Exception as e:
            print(f"同步分析错误 (偏移{offset}): {e}")
            continue
    
    print(f"选择同步偏移: {best_offset} (分数: {best_score})")
    return best_offset

def main():
    print(f"准备录制 {RECORD_SECONDS} 秒音频...")
    print(f"采样率: {SAMPLE_RATE}Hz, 位深度: {SAMPLE_WIDTH*8}bit, 声道数: {CHANNELS}")
    print(f"音量增益: {VOLUME_GAIN}x")
    
    try:
        # 打开串口
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=TIMEOUT)
        print(f"已连接到串口: {ser.name}")
        
        # 清空缓冲区
        ser.reset_input_buffer()
        time.sleep(0.5)
        
        # 寻找同步点
        sync_offset = find_sync_point(ser, SAMPLE_RATE, SAMPLE_WIDTH)
        
        # 丢弃同步点之前的不对齐数据
        if sync_offset > 0:
            discard_bytes = ser.read(sync_offset)
            print(f"丢弃 {len(discard_bytes)} 字节不对齐数据")
        
        # 创建WAV文件
        wf = wave.open(WAV_FILE, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        
        print(f"\n开始录制 (将保存到: {WAV_FILE})")
        start_time = time.time()
        total_bytes = 0
        expected_bytes = SAMPLE_RATE * SAMPLE_WIDTH * RECORD_SECONDS
        
        # 同步监控变量
        sync_errors = 0
        max_sync_errors = 5
        
        while time.time() - start_time < RECORD_SECONDS and sync_errors < max_sync_errors:
            remaining = RECORD_SECONDS - (time.time() - start_time)
            bytes_to_read = min(BUFFER_SIZE * SAMPLE_WIDTH, 
                               int(remaining * SAMPLE_RATE * SAMPLE_WIDTH))
            
            # 从串口读取数据
            data = ser.read(bytes_to_read)
            bytes_read = len(data)
            
            if bytes_read > 0:
                try:
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    
                    # 应用音量增益
                    amplified_data = apply_volume_gain(audio_data, VOLUME_GAIN)
                    
                    # 检查数据合理性
                    max_amplitude = np.max(np.abs(amplified_data))
                    zero_crossings = np.sum(np.diff(np.signbit(amplified_data.astype(np.float32))))
                    
                    # 如果数据饱和且没有过零点，可能是同步丢失
                    if max_amplitude > 32000 and zero_crossings < len(amplified_data) * 0.05:
                        sync_errors += 1
                        print(f"\n警告: 检测到可能的同步错误 ({sync_errors}/{max_sync_errors})")
                        
                        if sync_errors >= max_sync_errors:
                            print("同步错误过多，停止录制")
                            break
                        
                        # 尝试重新同步
                        ser.reset_input_buffer()
                        time.sleep(0.1)
                        new_offset = find_sync_point(ser, SAMPLE_RATE, SAMPLE_WIDTH)
                        if new_offset > 0:
                            ser.read(new_offset)
                            sync_errors = 0
                        continue
                    
                    # 写入放大后的数据
                    wf.writeframes(amplified_data.tobytes())
                    total_bytes += bytes_read
                    sync_errors = 0
                    
                except Exception as e:
                    print(f"\n数据处理错误: {e}")
                    sync_errors += 1
                    continue
            
            # 显示进度
            progress = min(100, (total_bytes / expected_bytes) * 100)
            sys.stdout.write(
                f"\r进度: {progress:.1f}% | "
                f"已接收: {total_bytes/1024:.1f}KB/{expected_bytes/1024:.1f}KB | "
                f"时间: {time.time()-start_time:.1f}s/{RECORD_SECONDS}s"
            )
            sys.stdout.flush()
        
        # 关闭文件
        wf.close()
        ser.close()
        
        # 验证录制结果
        actual_seconds = total_bytes / (SAMPLE_RATE * SAMPLE_WIDTH)
        print(f"\n\n录制完成! 实际录制时长: {actual_seconds:.2f}秒")
        print(f"音频已保存到: {WAV_FILE}")
        
        if sync_errors >= max_sync_errors:
            print("警告: 录制过程中出现同步问题，音频质量可能受影响")
        elif actual_seconds < RECORD_SECONDS * 0.9:
            print("警告: 录制时长不足，可能是数据传输问题")
        
    except serial.SerialException as e:
        print(f"\n串口错误: {e}")
    except Exception as e:
        print(f"\n发生错误: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        if 'wf' in locals():
            wf.close()

if __name__ == '__main__':
    main()