
import sounddevice as sd
import numpy as np
import serial
import time
import sys
import math

# 调试函数，测试音频输出是否正常
def test_audio_output(SAMPLE_RATE):
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
def test_serial_connection(SERIAL_PORT, BAUD_RATE):
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
        
        while time.time() - start_time < 1:  # 等待3秒
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

# 检查爆音的函数
def check_initial_audio(ser, buffer_size=1024, CHECK_DURATION=0.5, VOLUME_THRESHOLD=15, THRESHOLD_RATIO=0.5):
    """
    检查初始音频质量，防止爆音
    
    参数:
    - ser: 串口对象
    - buffer_size: 缓冲区大小
    
    返回:
    - bool: True表示音频正常，False表示需要重新连接
    """
    print("开始音频质量检查...")
    print(f"阈值: 在{CHECK_DURATION}秒内，音量超过{VOLUME_THRESHOLD}%的比例不能超过{THRESHOLD_RATIO*100:.0f}%")
    
    start_time = time.time()
    volume_samples = []  # 存储音量样本
    high_volume_count = 0  # 高音量计数
    
    check_start = time.time()
    
    while time.time() - check_start < CHECK_DURATION:
        # 读取数据
        expected_bytes = buffer_size * 2
        data = ser.read(expected_bytes)
        
        if data and len(data) >= 4:
            try:
                # 转换为音频数据
                audio = np.frombuffer(data, dtype=np.int16)
                
                # 计算音量
                if len(audio) > 0:
                    rms = np.sqrt(np.mean(audio.astype(np.float32)**2))
                    volume = (rms / 32767) * 100
                    
                    volume_samples.append(volume)
                    
                    # 统计高音量样本
                    if volume > VOLUME_THRESHOLD:
                        high_volume_count += 1
                    
                    # 显示实时检查进度
                    elapsed = time.time() - check_start
                    progress = min(elapsed / CHECK_DURATION, 1.0)
                    bar_length = 20
                    filled_length = int(bar_length * progress)
                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                    
                    high_ratio = high_volume_count / max(len(volume_samples), 1)
                    
                    sys.stdout.write(f"\r音频检查: [{bar}] {progress*100:.0f}% | "
                                   f"当前音量: {volume:.1f}% | "
                                   f"高音量比例: {high_ratio*100:.1f}%")
                    sys.stdout.flush()
            except:
                # 数据转换错误，视为异常音频
                return False
        
        time.sleep(0.001)  # 短暂休眠，避免过度占用CPU
    
    print()  # 换行
    
    # 分析结果
    if len(volume_samples) == 0:
        print("⚠ 未收到任何音频数据")
        return False
    
    high_ratio = high_volume_count / len(volume_samples)
    avg_volume = np.mean(volume_samples) if volume_samples else 0
    
    print(f"检查结果:")
    print(f"  采样数: {len(volume_samples)}")
    print(f"  平均音量: {avg_volume:.1f}%")
    print(f"  最大音量: {np.max(volume_samples) if volume_samples else 0:.1f}%")
    print(f"  高音量样本数: {high_volume_count}")
    print(f"  高音量比例: {high_ratio*100:.1f}%")
    
    # 判断标准
    if high_ratio > THRESHOLD_RATIO:
        print(f"✗ 高音量比例过高 ({high_ratio*100:.1f}% > {THRESHOLD_RATIO*100:.0f}%)")
        print(f"  可能原因:")
        print(f"  1. 麦克风增益设置过高")
        print(f"  2. ESP32音频数据异常")
        print(f"  3. 串口数据传输错误")
        return False
    elif avg_volume > VOLUME_THRESHOLD * 0.8:  # 平均音量接近阈值
        print(f"⚠ 平均音量较高 ({avg_volume:.1f}%)，建议检查麦克风增益")
        return True
    else:
        print(f"✓ 音频质量正常")
        return True

# 安全连接函数，防止爆音
def safe_serial_connection(port, baud_rate, timeout=0.1, MAX_RETRIES=3, buffer_size=1024, CHECK_DURATION=0.1, VOLUME_THRESHOLD=15, THRESHOLD_RATIO=0.5):
    """
    安全的串口连接，带重试机制
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"连接尝试 {attempt}/{MAX_RETRIES}...")
            
            # 打开串口
            ser = serial.Serial(port, baud_rate, timeout=timeout)
            print(f"✓ 串口连接成功: {ser.name}")
            
            # 清空缓冲区
            ser.reset_input_buffer()
            time.sleep(0.5)
            
            # 检查音频质量
            if check_initial_audio(ser, buffer_size=1024, CHECK_DURATION=CHECK_DURATION, VOLUME_THRESHOLD=VOLUME_THRESHOLD, THRESHOLD_RATIO=THRESHOLD_RATIO):
                return ser
            else:
                print(f"音频质量检查失败，关闭连接重试...")
                ser.close()
                time.sleep(1)  # 等待1秒后重试
                
        except serial.SerialException as e:
            print(f"✗ 串口连接失败: {e}")
            if attempt < MAX_RETRIES:
                print(f"等待1秒后重试...")
                time.sleep(1)
            else:
                raise
    
    raise ConnectionError(f"无法建立稳定的串口连接，已重试{MAX_RETRIES}次")
