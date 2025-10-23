# 说明

### 环境

```bash

platformio lib install "Adafruit GFX Library"

platformio lib install "Adafruit SSD1306"

platformio lib install "DHT sensor library"

platformio lib install "PubSubClient"

pio lib install "Adafruit NeoPixel"

pio pkg install --library 1076

pio pkg install --library "knolleary/PubSubClient"

pio lib install "Stepper"

pio lib install "AccelStepper"

pio lib install "ESP32Servo"

```

### 调试代码

* 串口调试
```bash

tio -b 115200 --timestamp  /dev/cu.wchusbserial5A7B1617701 

```

* python 代码调试

```bash

python3 ./tools/read_csv.py /dev/cu.wchusbserial5A7B1617701 

```


### 需求

* 可以快速去采集数据，但是采集的数据都保存在本地的文件系统中或者哪个存储中（断电可恢复），数据一小时或者指定周期上传一次

* 可以换一个板子 esp32C6 看看省电的效果, 


### 注意点

* 插到电脑上当做鼠标的时候，一定要接到 usb 接口，而不是 uart 接口，不然没用， 我发现 uart 口也是有用的🤦‍♂️ 

* 虽然写的是 5v 但是要接在 3.3v 上才能正常运行

* 波特率和采样率和对应着增加，不然会出现溢出的情况，非常大的声音

* 采用数字增益 8 倍就行了，现在的摸头是没有数字增益功能的

* 查看波形的时候有一定的概率开始查看的时候是错误的数据，重新运行就行

* 运行时间太长的话也会出问题，只需要重新拔插一下 usb 线就行了






