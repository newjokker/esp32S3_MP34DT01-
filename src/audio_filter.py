# simple_audio_processor.py
import numpy as np
from scipy import signal

class SimpleAudioProcessor:
    """简化版音频处理器，确保实时性"""
    
    def __init__(self, sample_rate=48000, filter_type='bandpass', 
                 freq_low=100.0, freq_high=3000.0, gain_db=20.0):
        """
        初始化音频处理器
        
        参数:
        - sample_rate: 采样率 (Hz)
        - filter_type: 滤波器类型 ('none', 'bandpass', 'lowpass', 'highpass')
        - freq_low: 低切频率 (Hz)
        - freq_high: 高切频率 (Hz)
        - gain_db: 增益分贝值
        """
        self.sample_rate = sample_rate
        self.filter_type = filter_type
        self.freq_low = freq_low
        self.freq_high = freq_high
        self.gain_db = gain_db
        
        self.nyquist = sample_rate / 2.0
        
        # 初始化滤波器系数
        self.b = None
        self.a = None
        self.zi = None
        
        # 初始化增益
        self.gain_linear = 10 ** (gain_db / 20.0)
        
        # 设计滤波器
        self._init_filter()
        
        # 打印配置信息
        self._print_config()
    
    def _init_filter(self):
        """初始化滤波器"""
        if self.filter_type == 'none':
            return
            
        if self.filter_type == 'bandpass':
            # 确保频率在有效范围内
            low = max(1.0, self.freq_low) / self.nyquist
            high = min(self.freq_high, self.nyquist - 1) / self.nyquist
            
            if low < 1.0 and high < 1.0 and low < high:
                self.b, self.a = signal.butter(4, [low, high], btype='bandpass')
                self.zi = signal.lfilter_zi(self.b, self.a)
                
        elif self.filter_type == 'lowpass':
            norm_freq = min(self.freq_high, self.nyquist - 1) / self.nyquist
            if norm_freq < 1.0:
                self.b, self.a = signal.butter(4, norm_freq, btype='low')
                self.zi = signal.lfilter_zi(self.b, self.a)
                
        elif self.filter_type == 'highpass':
            norm_freq = max(1.0, self.freq_low) / self.nyquist
            if norm_freq < 1.0:
                self.b, self.a = signal.butter(4, norm_freq, btype='high')
                self.zi = signal.lfilter_zi(self.b, self.a)
    
    def _print_config(self):
        """打印配置信息"""
        print("=" * 50)
        print("SimpleAudioProcessor 配置:")
        print(f"  采样率: {self.sample_rate}Hz")
        print(f"  滤波器: {self.filter_type}")
        if self.filter_type != 'none':
            print(f"  频率范围: {self.freq_low:.0f}-{self.freq_high:.0f}Hz")
        print(f"  增益: {self.gain_db:.1f}dB ({self.gain_linear:.1f}x)")
        print("=" * 50)
    
    def process_audio(self, audio_data):
        """
        处理音频数据
        
        参数:
        - audio_data: int16格式的音频数据数组
        
        返回:
        - processed_audio: 处理后的int16音频数据
        """
        if self.filter_type == 'none' or self.b is None:
            filtered = audio_data
        else:
            # 转换为浮点数进行滤波
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
    
    def reset_filter_state(self):
        """重置滤波器状态（在音频中断时调用）"""
        if self.b is not None and self.a is not None:
            self.zi = signal.lfilter_zi(self.b, self.a)
    
    def update_gain(self, gain_db):
        """动态更新增益"""
        self.gain_db = gain_db
        self.gain_linear = 10 ** (gain_db / 20.0)
        print(f"增益更新: {gain_db:.1f}dB ({self.gain_linear:.1f}x)")
    
    def update_filter(self, filter_type=None, freq_low=None, freq_high=None):
        """动态更新滤波器参数"""
        changed = False
        
        if filter_type is not None and filter_type != self.filter_type:
            self.filter_type = filter_type
            changed = True
            
        if freq_low is not None and freq_low != self.freq_low:
            self.freq_low = freq_low
            changed = True
            
        if freq_high is not None and freq_high != self.freq_high:
            self.freq_high = freq_high
            changed = True
        
        if changed:
            # 重新设计滤波器
            self._init_filter()
            self._print_config()
    
    def get_audio_stats(self, audio_data):
        """
        获取音频统计信息
        
        返回:
        - dict: 包含RMS、峰值、dB值等统计信息
        """
        if len(audio_data) == 0:
            return {
                'rms': 0,
                'peak': 0,
                'rms_db': -float('inf'),
                'peak_db': -float('inf'),
                'volume_percent': 0
            }
        
        # 转换为浮点数
        audio_float = audio_data.astype(np.float32) / 32768.0
        
        # 计算RMS和峰值
        rms = np.sqrt(np.mean(audio_float**2))
        peak = np.max(np.abs(audio_float))
        
        # 计算dB值
        rms_db = 20 * np.log10(max(rms, 1e-6))  # 避免log(0)
        peak_db = 20 * np.log10(max(peak, 1e-6))
        
        # 计算音量百分比
        volume_percent = rms * 100
        
        return {
            'rms': rms,
            'peak': peak,
            'rms_db': rms_db,
            'peak_db': peak_db,
            'volume_percent': volume_percent
        }
    
    def process_with_stats(self, audio_data):
        """
        处理音频并返回统计信息
        
        返回:
        - tuple: (processed_audio, stats_dict)
        """
        # 处理音频
        processed = self.process_audio(audio_data)
        
        # 获取原始和处理后的统计信息
        raw_stats = self.get_audio_stats(audio_data)
        proc_stats = self.get_audio_stats(processed)
        
        return processed, {
            'raw': raw_stats,
            'processed': proc_stats
        }


# 预设配置功能
class AudioProcessorPresets:
    """音频处理器预设配置"""
    
    @staticmethod
    def get_preset(preset_name):
        """获取预设配置"""
        presets = {
            'voice_chat': {
                'name': '语音聊天',
                'filter_type': 'bandpass',
                'freq_low': 100.0,
                'freq_high': 3000.0,
                'gain_db': 20.0
            },
            'meeting': {
                'name': '会议模式',
                'filter_type': 'bandpass',
                'freq_low': 150.0,
                'freq_high': 2800.0,
                'gain_db': 22.0
            },
            'noisy_environment': {
                'name': '嘈杂环境',
                'filter_type': 'bandpass',
                'freq_low': 200.0,
                'freq_high': 2500.0,
                'gain_db': 25.0
            },
            'low_noise': {
                'name': '去除低频噪音',
                'filter_type': 'highpass',
                'freq_low': 200.0,
                'freq_high': 3000.0,
                'gain_db': 18.0
            },
            'high_noise': {
                'name': '去除高频噪音',
                'filter_type': 'lowpass',
                'freq_low': 100.0,
                'freq_high': 2000.0,
                'gain_db': 18.0
            },
            'raw': {
                'name': '原始音频',
                'filter_type': 'none',
                'freq_low': 20.0,
                'freq_high': 20000.0,
                'gain_db': 16.0
            }
        }
        
        return presets.get(preset_name, presets['voice_chat'])
    
    @staticmethod
    def list_presets():
        """列出所有可用预设"""
        presets = AudioProcessorPresets.get_preset('voice_chat')  # 获取一个示例以了解结构
        preset_names = ['voice_chat', 'meeting', 'noisy_environment', 
                       'low_noise', 'high_noise', 'raw']
        
        print("可用预设:")
        for name in preset_names:
            preset = AudioProcessorPresets.get_preset(name)
            print(f"  {name:20} - {preset['name']}")
            print(f"     滤波器: {preset['filter_type']}, "
                  f"频率: {preset['freq_low']:.0f}-{preset['freq_high']:.0f}Hz, "
                  f"增益: {preset['gain_db']:.1f}dB")
        
        return preset_names


# 快速创建处理器的工厂函数
def create_processor_from_preset(preset_name='voice_chat', sample_rate=48000):
    """从预设创建音频处理器"""
    preset = AudioProcessorPresets.get_preset(preset_name)
    
    processor = SimpleAudioProcessor(
        sample_rate=sample_rate,
        filter_type=preset['filter_type'],
        freq_low=preset['freq_low'],
        freq_high=preset['freq_high'],
        gain_db=preset['gain_db']
    )
    
    print(f"✓ 已从预设 '{preset_name}' 创建处理器: {preset['name']}")
    return processor


# 测试函数
def test_processor():
    """测试音频处理器"""
    print("测试 SimpleAudioProcessor...")
    
    # 创建测试信号
    sample_rate = 48000
    duration = 0.1
    samples = int(sample_rate * duration)
    t = np.linspace(0, duration, samples, endpoint=False)
    
    # 生成包含低频、人声和高频的测试信号
    test_signal = (
        0.3 * np.sin(2 * np.pi * 50 * t) +      # 50Hz 低频
        0.5 * np.sin(2 * np.pi * 1000 * t) +    # 1kHz 人声
        0.2 * np.sin(2 * np.pi * 5000 * t)      # 5kHz 高频
    )
    
    # 转换为int16
    audio_data = (test_signal * 32767).astype(np.int16)
    
    # 测试不同滤波器
    test_cases = [
        ('bandpass', 100, 3000, 20, "人声带通"),
        ('highpass', 200, 3000, 18, "去除低频"),
        ('lowpass', 100, 2000, 18, "去除高频"),
        ('none', 20, 20000, 16, "原始音频")
    ]
    
    for filter_type, low, high, gain, desc in test_cases:
        print(f"\n测试: {desc}")
        print(f"滤波器: {filter_type}, {low}-{high}Hz, 增益: {gain}dB")
        
        processor = SimpleAudioProcessor(
            sample_rate=sample_rate,
            filter_type=filter_type,
            freq_low=low,
            freq_high=high,
            gain_db=gain
        )
        
        # 处理音频
        processed = processor.process_audio(audio_data)
        
        # 获取统计信息
        stats = processor.get_audio_stats(processed)
        
        print(f"  处理后 - RMS: {stats['rms']:.3f}, "
              f"峰值: {stats['peak']:.3f}, "
              f"音量: {stats['volume_percent']:.1f}%")
    
    # 测试预设
    print("\n测试预设功能:")
    AudioProcessorPresets.list_presets()
    
    # 测试从预设创建
    processor = create_processor_from_preset('voice_chat', sample_rate)
    print("✓ 所有测试通过")


if __name__ == "__main__":
    # 如果直接运行此文件，执行测试
    test_processor()