import json
import uuid
import paho.mqtt.client as mqtt
from models import db
from models.gudang import MonitoringGudang
from models.klasifikasi import KlasifikasiDaun
from models.settings import Settings

_mqtt_client = None
_flask_app = None


def _build_fan_state_payload(settings):
    if not settings:
        return json.dumps({
            "fan": "OFF",
            "mode": "AUTO",
            "suhu_min": 25.0,
            "suhu_max": 30.0,
            "kelembapan_min": 40.0,
            "kelembapan_max": 50.0,
            "gas_min": 1050,
            "gas_threshold": 1500
        })

    mode = settings.mode_fan.strip().upper() if settings.mode_fan else "AUTO"
    fan = "ON" if settings.status_fan_manual else "OFF"
    return json.dumps({
        "fan": fan,
        "mode": mode,
        "suhu_min": round(float(settings.suhu_min), 2),
        "suhu_max": round(float(settings.suhu_max), 2),
        "kelembapan_min": round(float(settings.kelembapan_min), 2),
        "kelembapan_max": round(float(settings.kelembapan_max), 2),
        "gas_min": int(settings.gas_min),
        "gas_threshold": int(settings.gas_threshold)
    })


def publish_fan_state(settings=None):
    """Publish status fan, mode, dan threshold ke ESP32 via MQTT (retained)."""
    global _mqtt_client, _flask_app
    if _mqtt_client is None or _flask_app is None:
        return False

    try:
        topic = _flask_app.config.get('MQTT_TOPIC_GUDANG_CONTROL', 'tobaccoguard/gudang/fan_state')
        payload = _build_fan_state_payload(settings)
        info = _mqtt_client.publish(topic, payload, qos=1, retain=True)
        return info.rc == mqtt.MQTT_ERR_SUCCESS
    except Exception as e:
        print(f"[MQTT] Gagal publish fan_state: {e}")
        return False


def _handle_gudang_message(payload_str):
    data = json.loads(payload_str)
    required = ['suhu', 'kelembapan', 'gas']
    if not all(k in data for k in required):
        return

    record = MonitoringGudang(
        suhu=float(data['suhu']),
        kelembapan=float(data['kelembapan']),
        gas=int(data['gas']),
        status_fan=bool(data.get('status_fan', False)),
        status_alarm=bool(data.get('status_alarm', False))
    )
    db.session.add(record)
    db.session.commit()


def _handle_conveyor_message(payload_str):
    data = json.loads(payload_str)
    if 'hasil_klasifikasi' not in data or 'confidence_score' not in data:
        return

    hasil = str(data['hasil_klasifikasi']).strip().lower()
    if hasil not in KlasifikasiDaun.VALID_CATEGORIES:
        return

    confidence = float(data['confidence_score'])
    if 1.0 < confidence <= 100.0:
        confidence /= 100.0
    if not (0.0 <= confidence <= 1.0):
        return

    record = KlasifikasiDaun(
        hasil_klasifikasi=hasil,
        confidence_score=confidence
    )
    db.session.add(record)
    db.session.commit()


def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        topic_gudang = _flask_app.config.get('MQTT_TOPIC_GUDANG_SENSOR', 'tobaccoguard/gudang/sensor')
        topic_conveyor = _flask_app.config.get('MQTT_TOPIC_CONVEYOR_DATA', 'tobaccoguard/conveyor/data')
        client.subscribe([(topic_gudang, 1), (topic_conveyor, 1)])
        print(f"[MQTT] Terhubung ke broker! Subscribed: {topic_gudang}, {topic_conveyor}")

        # Sinkronkan settings terbaru saat pertama kali connect
        with _flask_app.app_context():
            try:
                settings = Settings.query.get(1)
                publish_fan_state(settings)
            except Exception as e:
                print(f"[MQTT] Gagal sync settings awal: {e}")
    else:
        print(f"[MQTT] Gagal konek ke broker (rc={reason_code})")


def _on_message(client, userdata, msg):
    if _flask_app is None:
        return

    topic_gudang = _flask_app.config.get('MQTT_TOPIC_GUDANG_SENSOR', 'tobaccoguard/gudang/sensor')
    topic_conveyor = _flask_app.config.get('MQTT_TOPIC_CONVEYOR_DATA', 'tobaccoguard/conveyor/data')
    payload_str = msg.payload.decode('utf-8', errors='ignore')

    with _flask_app.app_context():
        try:
            if msg.topic == topic_gudang:
                _handle_gudang_message(payload_str)
            elif msg.topic == topic_conveyor:
                _handle_conveyor_message(payload_str)
        except Exception as e:
            db.session.rollback()
            print(f"[MQTT] Error proses pesan ({msg.topic}): {e}")


def init_mqtt(app):
    """Inisialisasi koneksi MQTT background loop untuk Flask."""
    global _mqtt_client, _flask_app
    if not app.config.get('MQTT_ENABLED', True):
        return None

    _flask_app = app
    broker = app.config.get('MQTT_BROKER', 'broker.hivemq.com')
    port = int(app.config.get('MQTT_PORT', 1883))
    client_id = f"tobaccoguard-flask-{uuid.uuid4().hex[:8]}"

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=15)

    try:
        client.connect_async(broker, port, keepalive=60)
        client.loop_start()
        _mqtt_client = client
        print(f"[MQTT] Worker dimulai -> {broker}:{port}")
    except Exception as e:
        print(f"[MQTT] Peringatan gagal inisialisasi ({broker}:{port}): {e}")

    return _mqtt_client
