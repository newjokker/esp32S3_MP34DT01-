
import sounddevice as sd
import numpy as np
import serial
import time
import sys
from src.test_voice import test_audio_output, test_serial_connection, safe_serial_connection
from src.audio_filter import SimpleAudioProcessor 
import warnings
warnings.filterwarnings("ignore")

# 与ESP32代码匹配的配置
SERIAL_PORT = 'COM26'
BAUD_RATE = 1500000
SAMPLE_RATE = 48000
CHANNELS = 1
BUFFER_SIZE = 256  # 与ESP32的BUFFER_SIZE一致

# ========== 用户参数 ==========
GAIN_DB = 20.0                     # 增益分贝值
FILTER_TYPE = 'bandpass'          # 只使用简单的滤波器类型
FREQ_LOW = 100.0                  # 低切频率
FREQ_HIGH = 3000.0                # 高切频率
# 爆音检测参数
VOLUME_THRESHOLD = 15.0           # 音量阈值百分比
CHECK_DURATION = 0.5              # 检测时长(秒)
THRESHOLD_RATIO = 0.5             # 超过阈值的比例阈值
MAX_RETRIES = 3                   # 最大重试次数
# ===================================


def main():
    """主函数"""
    print("ESP32麦克风实时播放器 (带爆音保护)")
    print(f"串口: {SERIAL_PORT}")
    print(f"波特率: {BAUD_RATE}")
    print(f"采样率: {SAMPLE_RATE}Hz")
    print(f"增益: {GAIN_DB:.1f}dB")
    print(f"滤波器: {FILTER_TYPE} ({FREQ_LOW}-{FREQ_HIGH}Hz)")
    print(f"爆音保护: 音量>{VOLUME_THRESHOLD}%持续{THRESHOLD_RATIO*100:.0f}%时间时重启")
    print("-" * 60)
    
    # 初始化音频处理器
    processor = SimpleAudioProcessor(
        sample_rate=SAMPLE_RATE,
        filter_type=FILTER_TYPE,
        freq_low=FREQ_LOW,
        freq_high=FREQ_HIGH,
        gain_db=GAIN_DB
    )
    
    ser = None
    stream = None
    
    try:
        # 安全连接串口
        ser = safe_serial_connection(
                            SERIAL_PORT, 
                            BAUD_RATE, 
                            MAX_RETRIES=MAX_RETRIES, 
                            buffer_size=BUFFER_SIZE, 
                            CHECK_DURATION=CHECK_DURATION, 
                            VOLUME_THRESHOLD=VOLUME_THRESHOLD, 
                            THRESHOLD_RATIO=THRESHOLD_RATIO
                        )
        
        # 创建音频输出流
        stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16',
            blocksize=BUFFER_SIZE
        )
        stream.start()
        
        print("开始播放... (按Ctrl+C停止)")
        print("-" * 60)
        
        # 运行时统计
        bytes_received = 0
        start_time = time.time()
        last_status_time = time.time()
        data_received_counter = 0
        audio_quality_checks = 0
        last_quality_check = time.time()
        
        # 音量统计
        volume_history = []
        max_history_size = 100
        
        # 爆音保护状态
        over_threshold_count = 0
        total_samples_count = 0
        auto_reconnect_count = 0
        
        try:
            while True:
                # 读取数据
                expected_bytes = BUFFER_SIZE * 2
                data = ser.read(expected_bytes)
                
                if data:
                    bytes_received += len(data)
                    data_received_counter += 1
                    
                    # 检查数据长度
                    if len(data) < 4:
                        continue
                    
                    # 转换为int16数组
                    try:
                        audio = np.frombuffer(data, dtype=np.int16)
                    except:
                        print("数据转换错误，跳过")
                        continue
                    
                    # 计算音量
                    if len(audio) > 0:
                        rms = np.sqrt(np.mean(audio.astype(np.float32)**2))
                        volume = (rms / 32767) * 100
                        
                        # 更新音量历史
                        volume_history.append(volume)
                        if len(volume_history) > max_history_size:
                            volume_history.pop(0)
                        
                        # 爆音检测
                        total_samples_count += 1
                        if volume > VOLUME_THRESHOLD:
                            over_threshold_count += 1
                        
                        # 定期重置计数（滑动窗口）
                        if total_samples_count >= 50:  # 每50个样本检查一次
                            high_ratio = over_threshold_count / total_samples_count
                            
                            if high_ratio > THRESHOLD_RATIO:
                                print(f"\n⚠ 爆音检测: 最近{total_samples_count}个样本中，"
                                      f"{over_threshold_count}个超过阈值 ({high_ratio*100:.1f}%)")
                                print("自动重新连接中...")
                                
                                auto_reconnect_count += 1
                                
                                # 保存当前状态
                                last_volume = volume
                                last_bytes = bytes_received
                                
                                # 关闭当前连接
                                stream.stop()
                                ser.close()
                                time.sleep(1)
                                
                                # 重新连接
                                try:
                                    ser = safe_serial_connection(SERIAL_PORT, BAUD_RATE)
                                    stream = sd.OutputStream(
                                        samplerate=SAMPLE_RATE,
                                        channels=CHANNELS,
                                        dtype='int16',
                                        blocksize=BUFFER_SIZE
                                    )
                                    stream.start()
                                    
                                    print(f"✓ 自动重新连接成功 ({auto_reconnect_count}次)")
                                    print("恢复播放...")
                                    
                                    # 重置统计
                                    bytes_received = last_bytes
                                    over_threshold_count = 0
                                    total_samples_count = 0
                                    volume_history = []
                                    
                                    continue  # 跳过本次循环的后续处理
                                    
                                except Exception as e:
                                    print(f"✗ 自动重新连接失败: {e}")
                                    raise
                            
                            # 重置计数
                            over_threshold_count = 0
                            total_samples_count = 0
                    
                    # 显示状态
                    current_time = time.time()
                    elapsed_total = current_time - start_time
                    
                    if current_time - last_status_time >= 0.5:
                        if elapsed_total > 0:
                            kbps = bytes_received / elapsed_total / 1024
                            
                            # 简单的音量条
                            bar_length = 20
                            filled_length = int(bar_length * volume / 100)
                            bar = '█' * filled_length + '░' * (bar_length - filled_length)
                            
                            # 计算平均音量
                            avg_volume = np.mean(volume_history) if volume_history else 0
                            
                            # 状态信息
                            status = (f"\r数据包: {data_received_counter:6d} | "
                                    f"速率: {kbps:5.1f}KB/s | "
                                    f"音量: {volume:5.1f}% [{bar}] | "
                                    f"平均: {avg_volume:5.1f}% | "
                                    f"重连: {auto_reconnect_count:2d}")
                            
                            # 添加警告提示
                            if avg_volume > VOLUME_THRESHOLD * 0.7:
                                status += " ⚠"
                            elif avg_volume > VOLUME_THRESHOLD:
                                status += " ✗"
                            
                            sys.stdout.write(status)
                            sys.stdout.flush()
                        
                        last_status_time = current_time
                    
                    # 处理音频
                    processed_audio = processor.process_audio(audio)
                    
                    # 播放音频
                    try:
                        stream.write(processed_audio)
                    except Exception as e:
                        print(f"播放错误: {e}")
                        # 重置处理器状态
                        processor.reset_filter_state()
                        continue
                    
                else:
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
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except:
                pass
        if ser is not None and hasattr(ser, 'is_open') and ser.is_open:
            try:
                ser.close()
            except:
                pass
        

if __name__ == "__main__":
    print("=" * 60)
    print("ESP32麦克风播放器 - 带爆音保护版")
    print("=" * 60)
    
    # 可选：运行测试
    run_tests = False   
    
    if run_tests:
        # 运行测试
        print("\n运行系统测试...")
        audio_ok = test_audio_output(SAMPLE_RATE)
        serial_ok = test_serial_connection(SERIAL_PORT, BAUD_RATE)
        
        if audio_ok and serial_ok:
            print("\n✓ 所有测试通过，开始主程序...")
            print("-" * 60)
            time.sleep(1)
        else:
            print("\n⚠ 测试失败，请检查问题后再运行")
            sys.exit(1)
    
    # 运行主程序
    main()