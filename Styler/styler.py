import network
import time
from machine import Pin, SoftSPI
from umqtt.simple import MQTTClient
import dht
from mfrc522 import MFRC522
import ujson

# ----------------------------------------------------------------
# 설정 (와이파이 및 MQTT)
# ----------------------------------------------------------------
SSID = "YOUR_WIFI_SSID"
PASSWORD = "YOUR_WIFI_PASSWORD"
MQTT_SERVER = "YOUR_BROKER_IP"

# MQTT 토픽 설정 (사용자 정의)
TOPIC_STATUS = b"styler/status"   # 온습도 데이터 발신
TOPIC_NFC = b"styler/nfc"         # NFC 태그 ID 발신
TOPIC_CMD = b"styler/command"     # 제어 명령 수신

# ----------------------------------------------------------------
# 하드웨어 핀 설정
# ----------------------------------------------------------------
# 릴레이 (1: ON, 0: OFF)
relay_humid = Pin(22, Pin.OUT) # 가습기 제어
relay_fan = Pin(4, Pin.OUT)    # 건조 모터 제어

# 온습도 센서
sensor = dht.DHT22(Pin(15))

# NFC 리더 (SoftSPI 사용)
sck = Pin(18, Pin.OUT)
mosi = Pin(19, Pin.OUT)
miso = Pin(21, Pin.IN)
rst = Pin(17, Pin.OUT)
cs = Pin(5, Pin.OUT)
spi = SoftSPI(baudrate=100000, polarity=0, phase=0, sck=sck, mosi=mosi, miso=miso)
rdr = MFRC522(spi, cs, rst)

# ----------------------------------------------------------------
# 네트워크 함수
# ----------------------------------------------------------------
def connect_wifi():
    """와이파이 연결 함수"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        while not wlan.isconnected():
            pass
    print('✅ WiFi Connected')

def mqtt_callback(topic, msg):
    """MQTT 메시지 수신 시 처리 함수"""
    try:
        cmd_str = msg.decode()
        print(f"📩 수신 명령: {cmd_str}")
        
        # 명령에 따른 릴레이 제어
        if 'STEAM_MODE' in cmd_str:
            relay_humid.value(1) # 가습기 ON
            relay_fan.value(0)   # 팬 OFF
            
        elif 'DRY_MODE' in cmd_str:
            relay_humid.value(0) # 가습기 OFF
            relay_fan.value(1)   # 팬 ON
            
        elif 'ALL_OFF' in cmd_str:
            relay_humid.value(0) # 모두 OFF
            relay_fan.value(0)
            
    except Exception as e:
        print(f"❌ 명령 처리 오류: {e}")

def connect_mqtt():
    """MQTT 브로커 연결 함수"""
    client = MQTTClient("MyStyler_v1", MQTT_SERVER)
    client.set_callback(mqtt_callback)
    client.connect()
    client.subscribe(TOPIC_CMD)
    print(f"✅ MQTT Connected")
    return client

# ----------------------------------------------------------------
# 메인 루프
# ----------------------------------------------------------------
def main():
    relay_humid.value(0)
    relay_fan.value(0)
    
    connect_wifi()
    client = connect_mqtt()
    last_dht_time = 0
    
    print("🚀 시스템 시작...")
    
    while True:
        try:
            client.check_msg() # 명령 수신 대기
            
            # 1. NFC 태그 감지 및 전송
            (stat, tag_type) = rdr.request(rdr.REQIDL)
            if stat == rdr.OK:
                (stat, uid) = rdr.anticoll()
                if stat == rdr.OK:
                    uid_str = "0x" + "".join("{:02x}".format(x) for x in uid)
                    print(f"💳 Tag: {uid_str}")
                    
                    # 태그 ID 전송
                    payload = ujson.dumps({"nfc": uid_str})
                    client.publish(TOPIC_NFC, payload)
                    time.sleep(1) 

            # 2. 온습도 측정 및 전송 (2초 주기)
            if time.time() - last_dht_time > 2:
                try:
                    sensor.measure()
                    temp = sensor.temperature()
                    hum = sensor.humidity()
                    
                    payload = ujson.dumps({"temp": temp, "hum": hum})
                    client.publish(TOPIC_STATUS, payload)
                    last_dht_time = time.time()
                except Exception:
                    pass
                    
        except OSError:
            print("⚠️ 재연결 시도...")
            time.sleep(5)
            try:
                client = connect_mqtt()
            except:
                pass

if __name__ == "__main__":
    main()
