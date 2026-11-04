import json
import urllib.request
import urllib.error
from flask import Blueprint, request, jsonify, current_app
from config import Config
from models.gudang import MonitoringGudang
from models.klasifikasi import KlasifikasiDaun
from models.settings import Settings

api_chatbot_bp = Blueprint('api_chatbot', __name__, url_prefix='/api/chatbot')

def get_system_context():
    """Mengumpulkan panduan domain TobaccoGuard & data terkini sistem."""
    knowledge_base = [
        "PERAN & IDENTITAS:",
        "- Anda adalah TobaccoBot, asisten AI resmi untuk aplikasi 'TobaccoGuard' (Sistem Cerdas Pemantauan Gudang & Klasifikasi Mutu Daun Tembakau Cerutu).",
        "- Jawablah dengan bahasa Indonesia yang jelas, ringkas, santun, akurat, dan berbasis data ilmiah tembakau berikut.",
        "",
        "PENGETAHUAN SISTEM TOBACCOGUARD:",
        "1. KLASIFIKASI MUTU DAUN TEMBAKAU (3 Kategori Utama Cerutu):",
        "   - Wrapper (Grade A / Mutu Terbaik): Daun pembungkus terluar cerutu. Karakteristik: elastis, halus tanpa cacat, warna seragam/merata, urat daun halus, nilai ekonomis paling tinggi.",
        "   - Binder (Grade B / Mutu Sedang): Daun pengikat bagian tengah yang membungkus inti cerutu. Karakteristik: memiliki kekuatan fisik baik, daya tahan sobek tinggi, tekstur lebih tebal dari wrapper.",
        "   - Filler (Grade C / Mutu Standar): Daun pengisi bagian dalam/inti racikan cerutu. Karakteristik: menyumbang aroma dan rasa utama saat dibakar, aspek estetika fisik tidak sepenting wrapper.",
        "",
        "2. STANDAR LINGKUNGAN GUDANG PENYIMPANAN TEMBAKAU:",
        f"   - Suhu Ideal: {Config.TEMP_NORMAL_MIN}°C - {Config.TEMP_NORMAL_MAX}°C (Peringatan jika > {Config.TEMP_WARNING_MAX}°C karena memicu kekeringan atau fermentasi berlebih).",
        f"   - Kelembapan (RH) Ideal: {Config.HUMIDITY_NORMAL_MIN}% - {Config.HUMIDITY_NORMAL_MAX}% (Jika terlalu kering < 50% daun rapuh/pecah; jika terlalu lembap > 75% memicu jamur/fungi).",
        f"   - Gas (Ammonia / Fermentasi): Normal <= {Config.GAS_NORMAL_MAX} ppm. Nilai gas tinggi menandakan fermentasi gas berlebih atau ventilasi buruk.",
        "",
        "3. PERANGKAT KERAS & TEKNOLOGI:",
        "   - ESP32: Memantau sensor suhu, kelembaban (DHT22), kadar gas (MQ-135), mengendalikan Exhaust Fan dan Kipas pendingin.",
        "   - Wemos & Kamera: Memindai citra daun pada conveyor menggunakan AI Deep Learning (MobileNetV2 / AlexNet) untuk sortir otomatis.",
    ]

    # Ambil data real-time database jika tersedia
    try:
        settings = Settings.query.get(1)
        if settings:
            knowledge_base.append(f"\n[SETTING AMBANG BATAS AKTIF] Suhu Max: {settings.suhu_max}°C, Kelembaban Max: {settings.kelembapan_max}%, Batas Gas: {settings.gas_threshold} ppm.")

        latest_gudang = MonitoringGudang.query.order_by(MonitoringGudang.id.desc()).first()
        if latest_gudang:
            eval_res = latest_gudang.evaluate_status(settings)
            fan_str = "Menyala (ON)" if latest_gudang.status_fan else "Mati (OFF)"
            knowledge_base.append(
                f"[DATA SENSOR GUDANG SAAT INI]\n"
                f"- Suhu: {latest_gudang.suhu:.1f}°C (Status: {eval_res['suhu']})\n"
                f"- Kelembaban: {latest_gudang.kelembapan:.1f}% (Status: {eval_res['kelembapan']})\n"
                f"- Gas: {latest_gudang.gas} ppm (Status: {eval_res['gas']})\n"
                f"- Status Sistem Keseluruhan: {eval_res['overall'].upper()}\n"
                f"- Exhaust Fan: {fan_str}"
            )
        else:
            knowledge_base.append("[DATA SENSOR GUDANG]: Belum ada data rekaman sensor di database.")

        latest_leaf = KlasifikasiDaun.query.order_by(KlasifikasiDaun.id.desc()).first()
        if latest_leaf:
            knowledge_base.append(
                f"[DETEKSI TEMBAKAU TERAKHIR DI CONVEYOR]\n"
                f"- Kategori: {latest_leaf.hasil_klasifikasi.upper()}\n"
                f"- Tingkat Keyakinan (Confidence): {latest_leaf.confidence_score * 100:.1f}%\n"
                f"- Waktu: {latest_leaf.timestamp}"
            )
    except Exception:
        pass

    knowledge_base.append("\nATURAN MENJAWAB:\n- Jika ditanya tentang data kondisi gudang atau deteksi saat ini, selalu rujuk data aktual di atas.\n- Jawab langsung ke inti pertanyaan secara terstruktur dan informatif.")

    return "\n".join(knowledge_base)

@api_chatbot_bp.route('/ask', methods=['POST'])
def ask_chatbot():
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    history = data.get('history', [])

    if not user_message:
        return jsonify({'success': False, 'error': 'Pesan tidak boleh kosong'}), 400

    api_key = current_app.config.get('GEMINI_API_KEY') or ''
    if not api_key or api_key == 'YOUR_GEMINI_API_KEY_HERE':
        return jsonify({
            'success': False,
            'error': 'API Key Gemini belum dikonfigurasi. Silakan isi GEMINI_API_KEY di file .env terlebih dahulu.'
        }), 400

    system_instruction = get_system_context()

    contents = []
    
    # Riwayat percakapan sebelumnya
    for chat in history[-6:]:
        role = "user" if chat.get('role') == 'user' else 'model'
        text = chat.get('text', '').strip()
        if text:
            contents.append({
                "role": role,
                "parts": [{"text": text}]
            })
    
    # Pesan user saat ini
    contents.append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,  # Lebih rendah agar respon faktual, konsisten, dan tidak halusinasi
            "maxOutputTokens": 800
        }
    }

    candidate_models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest"]
    last_error = ""

    for model_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
                candidates = resp_data.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts:
                        reply_text = parts[0].get('text', '')
                        return jsonify({'success': True, 'reply': reply_text})
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            try:
                err_json = json.loads(error_body)
                last_error = err_json.get('error', {}).get('message', str(e))
            except Exception:
                last_error = error_body or str(e)
            if e.code == 404:
                continue
            return jsonify({'success': False, 'error': f'Gemini API Error ({e.code}): {last_error}'}), 500
        except Exception as e:
            last_error = str(e)
            continue

    return jsonify({'success': False, 'error': f'Gagal mendapatkan respon dari AI: {last_error}'}), 500
