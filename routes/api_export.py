from flask import Blueprint, request, jsonify, send_file
from datetime import datetime, time
import io
import pandas as pd
from models.gudang import MonitoringGudang
from models.klasifikasi import KlasifikasiDaun

api_export_bp = Blueprint('api_export', __name__, url_prefix='/api/export')

@api_export_bp.route('/gudang', methods=['GET'])
def export_gudang():
    """
    GET /api/export/gudang?format=excel|csv&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    Export data monitoring gudang ke Excel atau CSV
    """
    try:
        export_format = request.args.get('format', 'excel').lower()
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query = MonitoringGudang.query

        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                query = query.filter(MonitoringGudang.timestamp >= start_dt)
            except ValueError:
                pass

        if end_date_str:
            try:
                end_dt = datetime.combine(datetime.strptime(end_date_str, '%Y-%m-%d'), time.max)
                query = query.filter(MonitoringGudang.timestamp <= end_dt)
            except ValueError:
                pass

        records = query.order_by(MonitoringGudang.timestamp.desc(), MonitoringGudang.id.desc()).all()

        rows = []
        for r in records:
            d = r.to_dict()
            rows.append({
                'ID': d['id'],
                'Waktu': d['timestamp_display'],
                'Suhu (°C)': d['suhu'],
                'Kelembapan (%)': d['kelembapan'],
                'Gas (ppm)': d['gas'],
                'Status Fan': 'Aktif' if d['status_fan'] else 'Mati',
                'Status Alarm': 'Bahaya/Aktif' if d['status_alarm'] else 'Aman/Mati',
                'Status Suhu': d['status_eval']['suhu'].capitalize(),
                'Status Kelembapan': d['status_eval']['kelembapan'].capitalize(),
                'Status Gas': d['status_eval']['gas'].capitalize(),
                'Kondisi Gudang': d['status_eval']['overall'].upper()
            })

        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=[
                'ID', 'Waktu', 'Suhu (°C)', 'Kelembapan (%)', 'Gas (ppm)',
                'Status Fan', 'Status Alarm', 'Status Suhu', 'Status Kelembapan',
                'Status Gas', 'Kondisi Gudang'
            ])

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

        if export_format == 'csv':
            buffer = io.BytesIO()
            df.to_csv(buffer, index=False, encoding='utf-8-sig')
            buffer.seek(0)
            return send_file(
                buffer,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'monitoring_gudang_{timestamp_str}.csv'
            )
        else:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Monitoring Gudang')
            buffer.seek(0)
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'monitoring_gudang_{timestamp_str}.xlsx'
            )

    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal mengekspor data gudang: {str(e)}"
        }), 500


@api_export_bp.route('/conveyor', methods=['GET'])
def export_conveyor():
    """
    GET /api/export/conveyor?format=excel|csv&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    Export data klasifikasi daun ke Excel atau CSV
    """
    try:
        export_format = request.args.get('format', 'excel').lower()
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        query = KlasifikasiDaun.query

        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                query = query.filter(KlasifikasiDaun.timestamp >= start_dt)
            except ValueError:
                pass

        if end_date_str:
            try:
                end_dt = datetime.combine(datetime.strptime(end_date_str, '%Y-%m-%d'), time.max)
                query = query.filter(KlasifikasiDaun.timestamp <= end_dt)
            except ValueError:
                pass

        records = query.order_by(KlasifikasiDaun.timestamp.desc(), KlasifikasiDaun.id.desc()).all()

        rows = []
        for r in records:
            d = r.to_dict()
            rows.append({
                'ID': d['id'],
                'Waktu': d['timestamp_display'],
                'Hasil Klasifikasi': d['hasil_klasifikasi'].capitalize(),
                'Confidence Score': d['confidence_score'],
                'Confidence (%)': f"{d['confidence_percent']}%"
            })

        df = pd.DataFrame(rows)
        if df.empty:
            df = pd.DataFrame(columns=[
                'ID', 'Waktu', 'Hasil Klasifikasi', 'Confidence Score', 'Confidence (%)'
            ])

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')

        if export_format == 'csv':
            buffer = io.BytesIO()
            df.to_csv(buffer, index=False, encoding='utf-8-sig')
            buffer.seek(0)
            return send_file(
                buffer,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'klasifikasi_daun_{timestamp_str}.csv'
            )
        else:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Klasifikasi Daun')
            buffer.seek(0)
            return send_file(
                buffer,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'klasifikasi_daun_{timestamp_str}.xlsx'
            )

    except Exception as e:
        return jsonify({
            "success": False,
            "data": None,
            "message": f"Gagal mengekspor data klasifikasi: {str(e)}"
        }), 500
