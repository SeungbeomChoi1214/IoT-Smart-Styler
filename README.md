# IoT 기반 NFC 스마트 스타일러 (Smart Styler PoC)

> Raspberry Pi · DHT22 · Relay · NFC · Node-RED · MQTT

라즈베리 파이와 온습도 센서, 릴레이 모듈을 활용해 의류 관리기의 핵심 기능(건조 · 스팀)을 구현한 IoT PoC 프로젝트입니다.  
단순 센서 제어에서 나아가 NFC 태깅 기반 모드 자동 인식과 MQTT 양방향 통신을 통한 실시간 관제 대시보드까지 구축했습니다.

| 항목 | 내용 |
|---|---|
| 기간 | 2025년 (2개월, 단기 PoC) |
| 팀 구성 | 총 4인 (통합 스마트홈 프로젝트 일환) |
| 담당 파트 | NFC 스마트 스타일러 — H/W 설계 및 S/W 로직 전담 |
| 시연 영상 | [YouTube 🎬](https://youtu.be/5jtdL9JyHZ8) |

---

## Architecture

```
NFC Tag (UID)
     │
     ▼
Raspberry Pi  ──── DHT22 (온습도)
     │                  │
     │           MQTT Publish
     │         (styler/status)
     ▼
Node-RED Dashboard  ◄──── MQTT Subscribe (styler/command)
     │
     ▼
Relay Module
  ├─ DC Fan
  ├─ 소형 가습기
  └─ 히터
```

- **NFC → 모드 분기**: UID를 읽어 `STEAM_MODE` / `DRY_MODE` 자동 전환
- **MQTT 토픽 구조**: `styler/status` (센서 데이터 수신) · `styler/command` (원격 제어 발행)
- **전원 분리**: 제어 전원(3.3 V)과 액추에이터 구동 전원(5 V / 12 V)을 물리적으로 분리해 안정성 확보

---

## 핵심 구현

### 1. H/W 제어 시스템

- DHT22, DC 팬, 소형 가습기, 히터를 릴레이 모듈로 통합 제어
- NFC 리더로 의류 태그 UID를 인식해 모드를 자동 분기

```python
# NFC UID → 동작 모드 매핑 예시
NFC_MODE_MAP = {
    "0xd7746c06": "STEAM_MODE",
    "0xa1b2c3d4": "DRY_MODE",
}

def handle_nfc_tag(uid: str):
    mode = NFC_MODE_MAP.get(uid)
    if mode:
        trigger_mode(mode)
```

### 2. Node-RED & MQTT 관제 대시보드
<img width="1584" height="1152" alt="image" src="https://github.com/user-attachments/assets/d6bab4c6-372e-4b46-8bda-fc97b6e4b6a5" />

- `mqtt in` 노드로 센서 데이터를 구독해 실시간 게이지 UI로 시각화
- `mqtt out` 노드로 원격 제어 명령을 발행해 M2M 양방향 제어 달성
<img width="2814" height="700" alt="image" src="https://github.com/user-attachments/assets/50112264-5a29-43c1-8db3-a9e5def351fd" />

---

## Troubleshooting

실제 H/W와 S/W를 연결하면서 맞닥뜨린 세 가지 핵심 이슈와 해결 과정입니다.

### Issue 1 · 전압 강하로 인한 시스템 재부팅 (Brown-out)

**증상**  
액추에이터 구동 순간 과전류가 발생해 라즈베리 파이가 강제 재부팅됨.

**원인**  
제어 전원과 구동 전원이 동일 라인 공유 → 돌입 전류(Inrush Current) 발생 시 전압 강하.

**해결**  
- 제어 전원(3.3 V)과 액추에이터 구동 전원을 물리적으로 분리  
- 릴레이의 **포토커플러(Opto-isolator)** 로 회로 절연  
- 전원 입력부에 **평활 콘덴서** 추가

> 이 경험은 이후 K-DT AIoT 프로젝트에서 모터 제어 안정화 로직을 설계하는 직접적인 기반이 됐습니다.

---

### Issue 2 · DHT22 센서 노이즈 (Outlier & None 반환)

**증상**  
주기적으로 `None` 값이 반환되거나, 습도 99.9% 같은 Outlier 데이터가 튀는 현상.

| 레이어 | 조치 |
|---|---|
| H/W | 데이터 핀-VCC 간 **4.7 kΩ 풀업 저항** 추가 → One-wire 신호 무결성 확보 |
| S/W | 이전 값과의 편차 기반 필터링 + `read_retry()` 방어 로직 구현 |

```python
def read_sensor_safe(pin, prev_humidity):
    humidity, temperature = Adafruit_DHT.read_retry(DHT22, pin)
    if humidity is None or abs(humidity - prev_humidity) > 20:
        return prev_humidity, None   # 이전 값 유지
    return humidity, temperature
```

---

### Issue 3 · 릴레이 채터링 및 Active-Low 논리 반전

**증상**  
목표 습도(70%) 도달 시, 69.9 ↔ 70.1% 사이를 오가며 릴레이가 초당 수 차례 ON/OFF를 반복.

**해결**  
- **히스테리시스(Hysteresis) 불감대 설정**: 65% 미만 → 작동 / 75% 이상 → 정지 (10% Deadband)  
- Active-Low 릴레이 특성에 맞게 S/W 출력 논리를 역전(`HIGH → OFF`)

```python
HUMIDITY_ON  = 65
HUMIDITY_OFF = 75

def control_humidifier(humidity: float, is_running: bool) -> bool:
    if humidity < HUMIDITY_ON:
        return True
    if humidity > HUMIDITY_OFF:
        return False
    return is_running   # 불감대 내에서는 현재 상태 유지
```

---

## What I Learned

- 전원 분리와 절연 설계가 임베디드 시스템 안정성의 출발점임을 체감
- 센서 노이즈는 H/W(풀업 저항)와 S/W(필터링 로직)를 함께 잡아야 한다는 것을 배움
- 히스테리시스 개념을 처음 제어 로직에 적용해 하드웨어 수명과 제어 안정성을 동시에 확보
- Node-RED + MQTT로 IoT 데이터의 실시간 시각화와 M2M 양방향 제어 파이프라인 구축

이 프로젝트의 전력 안정화·노이즈 처리·MQTT 통신 경험은 이후 **K-DT AIoT 로봇 / Mobius 4.0 기반 스마트 분류 시스템** 설계의 기술적 뼈대가 됐습니다.

---

## Tech Stack
`Raspberry Pi 5` `Python 3` `Node-RED` `MQTT (Mosquitto)` `DHT22` `Relay Module` `NFC (RC522)` `DC 팬 / 가습기 / 히터`
