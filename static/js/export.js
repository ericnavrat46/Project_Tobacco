/**
 * Tobacco IoT Monitoring - Export Page JS
 * Manages date presets, preview table rendering, and Excel/CSV report downloads.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Helper: Format Date as YYYY-MM-DD
    function formatDate(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    // Apply Presets
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const target = e.currentTarget.dataset.target;
            const preset = e.currentTarget.dataset.preset;
            
            const startInput = document.getElementById(`${target}StartDate`);
            const endInput = document.getElementById(`${target}EndDate`);
            
            const now = new Date();
            
            if (preset === 'today') {
                const todayStr = formatDate(now);
                startInput.value = todayStr;
                endInput.value = todayStr;
            } else if (preset === '7days') {
                const past = new Date();
                past.setDate(now.getDate() - 7);
                startInput.value = formatDate(past);
                endInput.value = formatDate(now);
            } else if (preset === '30days') {
                const past = new Date();
                past.setDate(now.getDate() - 30);
                startInput.value = formatDate(past);
                endInput.value = formatDate(now);
            } else if (preset === 'all') {
                startInput.value = '';
                endInput.value = '';
            }

            // Visual active indicator on clicked preset
            btn.parentElement.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active', 'btn-secondary'));
            btn.classList.add('active');
        });
    });

    // Preview Elements
    const previewCard = document.getElementById('previewCard');
    const previewTitle = document.getElementById('previewTitle');
    const previewCountBadge = document.getElementById('previewCountBadge');
    const previewTableHead = document.getElementById('previewTableHead');
    const previewTableBody = document.getElementById('previewTableBody');
    const btnClosePreview = document.getElementById('btnClosePreview');

    btnClosePreview?.addEventListener('click', () => {
        previewCard.classList.add('d-none');
    });

    // Preview Gudang Data
    document.getElementById('btnPreviewGudang')?.addEventListener('click', async () => {
        const startDate = document.getElementById('gudangStartDate').value;
        const endDate = document.getElementById('gudangEndDate').value;

        previewCard.classList.remove('d-none');
        previewTitle.textContent = 'Pratinjau Data Telemetri Gudang (Maks. 50 Data Terakhir)';
        previewTableHead.innerHTML = `
            <tr>
                <th>Waktu</th>
                <th>Suhu</th>
                <th>Kelembapan</th>
                <th>Gas</th>
                <th>Status Fan</th>
                <th>Status Alarm</th>
                <th>Kondisi</th>
            </tr>
        `;
        previewTableBody.innerHTML = `
            <tr><td colspan="7" class="text-center py-3 text-secondary">
                <div class="spinner-border spinner-border-sm text-emerald me-2" role="status"></div> Memuat pratinjau...
            </td></tr>
        `;

        try {
            let url = `/api/gudang/history?limit=50&order=desc`;
            if (startDate) url += `&start_date=${startDate}`;
            if (endDate) url += `&end_date=${endDate}`;

            const res = await fetch(url);
            const json = await res.json();

            if (!json.success || !json.data || json.data.length === 0) {
                previewCountBadge.textContent = '0 Data';
                previewTableBody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-secondary">Tidak ada data ditemukan pada rentang tanggal ini.</td></tr>`;
                return;
            }

            previewCountBadge.textContent = `${json.data.length} Data Ditampilkan`;
            let rowsHtml = '';
            json.data.forEach(r => {
                const condBadge = r.status_alarm ? '<span class="badge bg-danger">BAHAYA</span>'
                                : r.status_eval.overall === 'danger' ? '<span class="badge bg-danger">KRITIS</span>'
                                : r.status_eval.overall === 'warning' ? '<span class="badge bg-warning text-dark">WASPADA</span>'
                                : '<span class="badge bg-success">NORMAL</span>';

                rowsHtml += `
                    <tr>
                        <td>${r.timestamp_display || r.timestamp}</td>
                        <td><strong class="text-danger">${r.suhu} °C</strong></td>
                        <td><strong class="text-primary">${r.kelembapan} %</strong></td>
                        <td><strong class="text-warning">${r.gas} ppm</strong></td>
                        <td>${r.status_fan ? '<span class="badge bg-success">AKTIF</span>' : '<span class="badge bg-secondary">MATI</span>'}</td>
                        <td>${r.status_alarm ? '<span class="badge bg-danger">AKTIF</span>' : '<span class="badge bg-light text-secondary border">AMAN</span>'}</td>
                        <td>${condBadge}</td>
                    </tr>
                `;
            });
            previewTableBody.innerHTML = rowsHtml;
            previewCard.scrollIntoView({ behavior: 'smooth' });

        } catch (e) {
            previewTableBody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-danger">Gagal memuat pratinjau: ${e.message}</td></tr>`;
        }
    });

    // Preview Conveyor Data
    document.getElementById('btnPreviewConveyor')?.addEventListener('click', async () => {
        const startDate = document.getElementById('conveyorStartDate').value;
        const endDate = document.getElementById('conveyorEndDate').value;

        previewCard.classList.remove('d-none');
        previewTitle.textContent = 'Pratinjau Data Klasifikasi Daun Conveyor (Maks. 50 Data Terakhir)';
        previewTableHead.innerHTML = `
            <tr>
                <th>Waktu</th>
                <th>Hasil Klasifikasi</th>
                <th>Confidence Score</th>
                <th>Akurasi (%)</th>
                <th>Kategori Daun</th>
            </tr>
        `;
        previewTableBody.innerHTML = `
            <tr><td colspan="5" class="text-center py-3 text-secondary">
                <div class="spinner-border spinner-border-sm text-emerald me-2" role="status"></div> Memuat pratinjau...
            </td></tr>
        `;

        try {
            let url = `/api/conveyor/history?limit=50`;
            if (startDate) url += `&start_date=${startDate}`;
            if (endDate) url += `&end_date=${endDate}`;

            const res = await fetch(url);
            const json = await res.json();

            if (!json.success || !json.data || json.data.length === 0) {
                previewCountBadge.textContent = '0 Data';
                previewTableBody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-secondary">Tidak ada data ditemukan pada rentang tanggal ini.</td></tr>`;
                return;
            }

            previewCountBadge.textContent = `${json.data.length} Data Ditampilkan`;
            let rowsHtml = '';
            json.data.forEach(r => {
                const cat = r.hasil_klasifikasi.toLowerCase();
                const catBadge = cat === 'wrapper' ? '<span class="badge badge-wrapper text-uppercase px-2 py-1">Wrapper</span>'
                               : cat === 'binder' ? '<span class="badge badge-binder text-uppercase px-2 py-1">Binder</span>'
                               : '<span class="badge badge-filler text-uppercase px-2 py-1">Filler</span>';

                rowsHtml += `
                    <tr>
                        <td>${r.timestamp_display || r.timestamp}</td>
                        <td>${catBadge}</td>
                        <td><code>${r.confidence_score}</code></td>
                        <td><strong>${r.confidence_percent}%</strong></td>
                        <td class="small text-secondary">${cat === 'wrapper' ? 'Pembungkus Luar' : cat === 'binder' ? 'Pengikat Tengah' : 'Pengisi Inti'}</td>
                    </tr>
                `;
            });
            previewTableBody.innerHTML = rowsHtml;
            previewCard.scrollIntoView({ behavior: 'smooth' });

        } catch (e) {
            previewTableBody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-danger">Gagal memuat pratinjau: ${e.message}</td></tr>`;
        }
    });

    // Download Gudang Handler
    document.getElementById('btnDownloadGudang')?.addEventListener('click', () => {
        const startDate = document.getElementById('gudangStartDate').value;
        const endDate = document.getElementById('gudangEndDate').value;
        const format = document.querySelector('input[name="formatGudang"]:checked')?.value || 'excel';

        let url = `/api/export/gudang?format=${format}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;

        window.location.href = url;
    });

    // Download Conveyor Handler
    document.getElementById('btnDownloadConveyor')?.addEventListener('click', () => {
        const startDate = document.getElementById('conveyorStartDate').value;
        const endDate = document.getElementById('conveyorEndDate').value;
        const format = document.querySelector('input[name="formatConveyor"]:checked')?.value || 'excel';

        let url = `/api/export/conveyor?format=${format}`;
        if (startDate) url += `&start_date=${startDate}`;
        if (endDate) url += `&end_date=${endDate}`;

        window.location.href = url;
    });
});
