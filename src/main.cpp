#include <Arduino.h>
#include <driver/i2s.h>

// =================================================
// 硬件引脚定义
// =================================================

// -------- PDM 麦克风（I2S RX）--------
#define I2S_MIC_PORT     I2S_NUM_0
#define PDM_CLK_PIN      5
#define PDM_DATA_PIN     4

// -------- I2S DAC（PCM5102）--------
#define I2S_SPK_PORT     I2S_NUM_1
#define PIN_I2S_BCK      17
#define PIN_I2S_WS       18
#define PIN_I2S_DOUT     8

// =================================================
#define SAMPLE_RATE      44100
#define BUFFER_SAMPLES   8
#define MIC_GAIN         3.0f

// PCM5102 经验内部延迟（ms）
#define DAC_LATENCY_MS  0.8f

// 日志周期
#define LOG_INTERVAL_MS 1000

unsigned long last_log_time = 0;

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n🎤 ESP32-S3 实时音频延迟分析启动");

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
  // I2S TX - PCM5102
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

  Serial.println("✅ 初始化完成，开始监听\n");
}

void loop() {
  static int16_t mic_buffer[BUFFER_SAMPLES];
  static int16_t out_buffer[BUFFER_SAMPLES * 2];

  size_t bytes_read = 0;
  size_t bytes_written = 0;

  // ===== 时间戳 =====
  uint32_t t0, t1, t2, t3;

  // 1️⃣ 等 RX DMA buffer
  t0 = micros();
  i2s_read(I2S_MIC_PORT,
           mic_buffer,
           sizeof(mic_buffer),
           &bytes_read,
           portMAX_DELAY);
  t1 = micros();

  int samples = bytes_read / sizeof(int16_t);

  // 2️⃣ CPU 处理
  for (int i = 0; i < samples; i++) {
    float s = mic_buffer[i] * MIC_GAIN;
    if (s > 32767) s = 32767;
    if (s < -32768) s = -32768;
    int16_t v = (int16_t)s;
    out_buffer[i * 2]     = v;
    out_buffer[i * 2 + 1] = v;
  }
  t2 = micros();

  // 3️⃣ TX DMA buffer
  i2s_write(I2S_SPK_PORT,
            out_buffer,
            samples * 2 * sizeof(int16_t),
            &bytes_written,
            portMAX_DELAY);
  t3 = micros();

  // =================================================
  // 日志
  // =================================================
  unsigned long now = millis();
  if (now - last_log_time >= LOG_INTERVAL_MS) {
    last_log_time = now;

    float rx_wait_ms  = (t1 - t0) / 1000.0f;
    float cpu_ms      = (t2 - t1) / 1000.0f;
    float tx_wait_ms  = (t3 - t2) / 1000.0f;
    float frame_ms    = (float)BUFFER_SAMPLES / SAMPLE_RATE * 1000.0f;

    float estimated_total =
        frame_ms * 2 + DAC_LATENCY_MS + cpu_ms;

    Serial.printf(
      "⏱ RX wait=%.3f ms | CPU=%.3f ms | TX wait=%.3f ms | frame=%.3f ms | total≈%.2f ms\n",
      rx_wait_ms,
      cpu_ms,
      tx_wait_ms,
      frame_ms,
      estimated_total
    );
  }
}
