#include <Arduino.h>
#include <driver/i2s.h>

#define I2S_PORT I2S_NUM_0
#define SAMPLE_RATE 16000
#define BUFFER_SIZE 1024

void setup() {
  Serial.begin(460800);

  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    // .communication_format = 0,  // ✅ PDM 模式不要设通信格式
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = BUFFER_SIZE,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .mck_io_num = I2S_PIN_NO_CHANGE,
    .bck_io_num = I2S_PIN_NO_CHANGE,
    .ws_io_num = 14,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = 13
  };

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
  i2s_set_clk(I2S_PORT, SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);

  Serial.println("I2S PDM 麦克风初始化完成");
}

void loop() {
  int16_t buffer[BUFFER_SIZE];
  size_t bytes_read;
  i2s_read(I2S_PORT, buffer, sizeof(buffer), &bytes_read, portMAX_DELAY);
  Serial.write((uint8_t *)buffer, bytes_read);
}
