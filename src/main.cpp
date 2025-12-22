#include <Arduino.h>
#include <driver/i2s.h>

#define I2S_PORT I2S_NUM_0

// ===== 音频参数 =====
#define SAMPLE_RATE     48000      // 48 kHz
#define READ_SAMPLES    256         // 每次读取 256 sample（≈5.33 ms）
#define BITS_PER_SAMPLE I2S_BITS_PER_SAMPLE_16BIT

// ===== PDM 引脚（ESP32-S3 推荐）=====
#define PDM_DATA_PIN  4
#define PDM_CLK_PIN   5

static int16_t audio_buffer[READ_SAMPLES];

void setup() {
  Serial.begin(1500000);
  delay(1000);

  // ===== I2S 配置 =====
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(
        I2S_MODE_MASTER |
        I2S_MODE_RX |
        I2S_MODE_PDM
    ),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = READ_SAMPLES,   // 🔴 与读取长度保持一致
    .use_apll = true,              // 更稳的时钟
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  // ===== I2S 引脚 =====
  i2s_pin_config_t pin_config = {
    .mck_io_num   = I2S_PIN_NO_CHANGE,
    .bck_io_num   = I2S_PIN_NO_CHANGE,
    .ws_io_num    = PDM_CLK_PIN,    // PDM CLK
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num  = PDM_DATA_PIN    // PDM DATA
  };

  // ===== 安装 I2S 驱动 =====
  esp_err_t err;
  err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("I2S driver install failed: %d\n", err);
    while (1);
  }

  err = i2s_set_pin(I2S_PORT, &pin_config);
  if (err != ESP_OK) {
    Serial.printf("I2S pin config failed: %d\n", err);
    while (1);
  }

  i2s_set_clk(
    I2S_PORT,
    SAMPLE_RATE,
    BITS_PER_SAMPLE,
    I2S_CHANNEL_MONO
  );

  Serial.println("I2S PDM microphone initialized");
  Serial.printf("Sample rate: %d Hz\n", SAMPLE_RATE);
  Serial.printf("Read samples per frame: %d\n", READ_SAMPLES);
}

void loop() {
  size_t bytes_read = 0;

  esp_err_t err = i2s_read(
    I2S_PORT,
    audio_buffer,
    READ_SAMPLES * sizeof(int16_t),
    &bytes_read,
    portMAX_DELAY
  );

  if (err != ESP_OK || bytes_read == 0) {
    Serial.println("I2S read error");
    return;
  }

  // ===== 示例 1：直接原始数据输出（不推荐长期用）=====
  Serial.write((uint8_t *)audio_buffer, bytes_read);

  // ===== 示例 2：更推荐（计算特征再发）=====
  /*
  int64_t sum = 0;
  for (int i = 0; i < READ_SAMPLES; i++) {
    sum += abs(audio_buffer[i]);
  }
  int32_t avg = sum / READ_SAMPLES;
  Serial.println(avg);
  */
}
