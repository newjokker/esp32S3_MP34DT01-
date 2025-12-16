#include <Arduino.h>
#include <driver/i2s.h>

#define I2S_PORT I2S_NUM_0
#define SAMPLE_RATE 48000  // 提高到48kHz (CD音质)
// #define SAMPLE_RATE 4000  // 提高到48kHz (CD音质)
#define BUFFER_SIZE 1024   // 保持缓冲区大小不变

// ESP32-S3的I2S PDM麦克风推荐引脚
#define PDM_DATA_PIN  4  // DATA引脚
#define PDM_CLK_PIN   5  // CLK引脚

void setup() {
  // 串口波特率提高到921600以适应更高的采样率
  Serial.begin(1500000);

  // I2S配置
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = BUFFER_SIZE,
    .use_apll = true,  // 启用APLL以获得更精确的时钟
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  // ESP32-S3的I2S引脚配置
  i2s_pin_config_t pin_config = {
    .mck_io_num = I2S_PIN_NO_CHANGE,
    .bck_io_num = I2S_PIN_NO_CHANGE,
    .ws_io_num = PDM_CLK_PIN,      // CLK引脚
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = PDM_DATA_PIN    // DATA引脚
  };

  // 安装I2S驱动
  esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("I2S驱动安装失败: %d\n", err);
    while(1);
  }

  // 设置引脚
  err = i2s_set_pin(I2S_PORT, &pin_config);
  if (err != ESP_OK) {
    Serial.printf("I2S引脚设置失败: %d\n", err);
    while(1);
  }

  // 设置时钟
  i2s_set_clk(I2S_PORT, SAMPLE_RATE, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);

  Serial.println("I2S PDM麦克风初始化完成");
  Serial.printf("当前采样率: %d Hz, 波特率: 921600\n", SAMPLE_RATE);
}

void loop() {
  int16_t buffer[BUFFER_SIZE];
  size_t bytes_read;
  
  // 读取I2S数据
  esp_err_t err = i2s_read(I2S_PORT, buffer, sizeof(buffer), &bytes_read, portMAX_DELAY);
  if (err != ESP_OK) {
    Serial.printf("I2S读取错误: %d\n", err);
    return;
  }
  
  // 将数据通过串口发送
  Serial.write((uint8_t *)buffer, bytes_read);
}