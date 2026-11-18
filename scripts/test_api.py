import json
import random
import urllib.request
import urllib.error

BASE_URL = "http://localhost:5000/api"

def make_request(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    
    body = json.dumps(data).encode('utf-8') if data else None
    try:
        with urllib.request.urlopen(req, data=body, timeout=5) as response:
            status_code = response.getcode()
            response_body = response.read().decode('utf-8')
            return status_code, json.loads(response_body)
    except urllib.error.HTTPError as e:
        status_code = e.code
        response_body = e.read().decode('utf-8')
        try:
            parsed = json.loads(response_body)
        except Exception:
            parsed = response_body
        return status_code, parsed
    except Exception as e:
        return 0, str(e)

def test_esp32_post(suhu=26.5, kelembapan=64.2, gas=80, status_fan=True, status_alarm=False):
    url = f"{BASE_URL}/gudang"
    payload = {
        "suhu": suhu,
        "kelembapan": kelembapan,
        "gas": gas,
        "status_fan": status_fan,
        "status_alarm": status_alarm
    }
    status, res = make_request(url, method="POST", data=payload)
    print(f"[ESP32 -> POST /api/gudang] HTTP {status}: {json.dumps(res, indent=2)}")
    return status == 201

def test_wemos_post(kategori="wrapper", conf=0.954):
    url = f"{BASE_URL}/conveyor"
    payload = {
        "hasil_klasifikasi": kategori,
        "confidence_score": conf
    }
    status, res = make_request(url, method="POST", data=payload)
    print(f"[WEMOS -> POST /api/conveyor] HTTP {status}: {json.dumps(res, indent=2)}")
    return status == 201

def test_get_endpoints():
    endpoints = [
        f"{BASE_URL}/gudang/latest",
        f"{BASE_URL}/gudang/history?limit=5",
        f"{BASE_URL}/conveyor/latest",
        f"{BASE_URL}/conveyor/stats"
    ]
    for ep in endpoints:
        status, res = make_request(ep, method="GET")
        print(f"\n[GET {ep}] HTTP {status}:")
        if isinstance(res, dict):
            print(f"Success: {res.get('success')}, Message: {res.get('message')}")
            if 'data' in res:
                print(f"Data sample: {str(res['data'])[:120]}...")
        else:
            print(f"Response: {res}")

if __name__ == "__main__":
    print("=== PENGUJIAN API IOT GUDANG TEMBAKAU ===")
    print("\n1. Testing ESP32 POST /api/gudang...")
    test_esp32_post(suhu=25.8, kelembapan=65.5, gas=78, status_fan=True, status_alarm=False)

    print("\n2. Testing Wemos POST /api/conveyor...")
    test_wemos_post(kategori="wrapper", conf=0.962)
    test_wemos_post(kategori="binder", conf=0.912)

    print("\n3. Testing GET Endpoints...")
    test_get_endpoints()

    print("\n4. Testing Error Handling (Invalid Payload)...")
    status, res = make_request(f"{BASE_URL}/conveyor", method="POST", data={"hasil_klasifikasi": "invalid_leaf", "confidence_score": 0.5})
    print(f"[Error Validation Test] HTTP {status}: {res}")
