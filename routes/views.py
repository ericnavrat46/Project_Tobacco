from flask import Blueprint, render_template

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
def dashboard():
    return render_template('dashboard.html')

@views_bp.route('/klasifikasi')
def klasifikasi_page():
    return render_template('klasifikasi.html')

@views_bp.route('/export')
def export_page():
    return render_template('export.html')

@views_bp.route('/settings')
def settings_page():
    return render_template('settings.html')
