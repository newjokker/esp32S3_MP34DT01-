#include <Arduino.h>
#include <driver/i2s.h>

// =================================================
// 硬件引脚定义
// =================================================

// -------- PDM 麦克风（I2S RX）--------
#define I2S_MIC_PORT     I2S_NUM_0
#define PDM_CLK_PIN      5
#define PDM_DATA_PIN     4

// -------- I2S 耳机 / DAC（I2S TX）--------
#define I2S_SPK_PORT     I2S_NUM_1
#define PIN_I2S_BCK      17
#define PIN_I2S_WS       18
#define PIN_I2S_DOUT     8

// =================================================
#define SAMPLE_RATE      44100
#define BUFFER_SAMPLES   32
#define MIC_GAIN         3.0f
// =================================================

// DAC / 耳机的经验固定延迟（ms）
#define DAC_LATENCY_MS  1.5f

// 日志输出周期
#define LOG_INTERVAL_MS 1000

unsigned long last_log_time = 0;

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n🎤 ESP32-S3 麦克风实时监听启动");

  // =================================================
  // I2S RX - PDM 麦克风
  // =================================================
  i2s_config_t mic_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = BUFFER_SAMPLES,
    .use_apll = true,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t mic_pins = {
    .mck_io_num = I2S_PIN_NO_CHANGE,
    .bck_io_num = I2S_PIN_NO_CHANGE,
    .ws_io_num  = PDM_CLK_PIN,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num  = PDM_DATA_PIN
  };

  i2s_driver_install(I2S_MIC_PORT, &mic_config, 0, NULL);
  i2s_set_pin(I2S_MIC_PORT, &mic_pins);
  i2s_set_clk(I2S_MIC_PORT, SAMPLE_RATE,
              I2S_BITS_PER_SAMPLE_16BIT,
              I2S_CHANNEL_MONO);

  // =================================================
  // I2S TX - 耳机 / DAC
  // =================================================
  i2s_config_t spk_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = BUFFER_SAMPLES,
    .use_apll = false,
    .tx_desc_auto_clear = true,
    .fixed_mclk = 0
  };

  i2s_pin_config_t spk_pins = {
    .mck_io_num = I2S_PIN_NO_CHANGE,
    .bck_io_num = PIN_I2S_BCK,
    .ws_io_num  = PIN_I2S_WS,
    .data_out_num = PIN_I2S_DOUT,
    .data_in_num  = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_SPK_PORT, &spk_config, 0, NULL);
  i2s_set_pin(I2S_SPK_PORT, &spk_pins);

  Serial.println("✅ 初始化完成，开始监听");
}

void loop() {
  static int16_t mic_buffer[BUFFER_SAMPLES];
  static int16_t out_buffer[BUFFER_SAMPLES * 2];

  size_t bytes_read = 0;
  size_t bytes_written = 0;

  uint32_t t_start = micros();

  // 1️⃣ 读取麦克风
  i2s_read(I2S_MIC_PORT,
           mic_buffer,
           sizeof(mic_buffer),
           &bytes_read,
           portMAX_DELAY);

  int samples = bytes_read / sizeof(int16_t);

  // 2️⃣ 放大 + 单声道复制
  for (int i = 0; i < samples; i++) {
    float s = mic_buffer[i] * MIC_GAIN;
    if (s > 32767) s = 32767;
    if (s < -32768) s = -32768;
    int16_t v = (int16_t)s;
    out_buffer[i * 2]     = v;
    out_buffer[i * 2 + 1] = v;
  }

  // 3️⃣ 播放
  i2s_write(I2S_SPK_PORT,
            out_buffer,
            samples * 2 * sizeof(int16_t),
            &bytes_written,
            portMAX_DELAY);

  uint32_t t_end = micros();

  // =================================================
  // 延迟估算 & 日志
  // =================================================
  unsigned long now = millis();
  if (now - last_log_time >= LOG_INTERVAL_MS) {
    last_log_time = now;

    float frame_ms = (float)BUFFER_SAMPLES / SAMPLE_RATE * 1000.0f;
    float processing_ms = (t_end - t_start) / 1000.0f;

    float estimated_latency =
        frame_ms * 2 + DAC_LATENCY_MS + processing_ms;

    Serial.printf(
      "📊 延迟估算 | frame=%.2f ms | proc=%.3f ms | total≈%.2f ms\n",
      frame_ms,
      processing_ms,
      estimated_latency
    );
  }
}
