/**
 * Tobacco IoT Monitoring Dashboard JS
 * Manages real-time 5-second polling, Chart.js instances, color thresholds, and alarm notifications.
 */

document.addEventListener('DOMContentLoaded', () => {
    // API Endpoints
    const API = {
        gudangLatest: '/api/gudang/latest',
        gudangHistory: '/api/gudang/history',
        conveyorLatest: '/api/conveyor/latest',
        conveyorStats: '/api/conveyor/stats',
        conveyorHistory: '/api/conveyor/history',
        settings: '/api/settings'
    };

    // State Variables
    let envChart = null;
    let leafChart = null;
    let refreshTimer = null;
    let isFetching = false;
    let filterStartDate = '';
    let filterEndDate = '';

    // Thresholds
    const THRESHOLDS = {
        temp: { normalMin: 20.0, normalMax: 28.0, warnMax: 32.0 },
        humidity: { normalMin: 60.0, normalMax: 70.0, warnMin: 50.0, warnMax: 75.0 },
        gas: { normalMax: 150, warnMax: 300 }
    };

    // DOM Elements - Metrics
    const valSuhu = document.getElementById('valSuhu');
    const valKelembapan = document.getElementById('valKelembapan');
    const valGas = document.getElementById('valGas');
    const cardSuhu = document.getElementById('cardSuhu');
    const cardKelembapan = document.getElementById('cardKelembapan');
    const cardGas = document.getElementById('cardGas');
    const badgeStatusSuhu = document.getElementById('badgeStatusSuhu');
    const badgeStatusKelembapan = document.getElementById('badgeStatusKelembapan');
    const badgeStatusGas = document.getElementById('badgeStatusGas');
    const badgeModeFan = document.getElementById('badgeModeFan');
    const badgeStatusFan = document.getElementById('badgeStatusFan');
    const iconFanRotate = document.getElementById('iconFanRotate');
    const badgeStatusAlarm = document.getElementById('badgeStatusAlarm');
    const lblLastUpdate = document.getElementById('lblLastUpdate');
    const navConnectionStatus = document.getElementById('navConnectionStatus');

    // DOM Elements - Alarm Banner
    const alarmBanner = document.getElementById('alarmBanner');
    const alarmBannerDetails = document.getElementById('alarmBannerDetails');
    const btnDismissAlarm = document.getElementById('btnDismissAlarm');

    // DOM Elements - Conveyor Stats
    const badgeTotalDaun = document.getElementById('badgeTotalDaun');
    const statWrapperCount = document.getElementById('statWrapperCount');
    const statWrapperPct = document.getElementById('statWrapperPct');
    const statBinderCount = document.getElementById('statBinderCount');
    const statBinderPct = document.getElementById('statBinderPct');
    const statFillerCount = document.getElementById('statFillerCount');
    const statFillerPct = document.getElementById('statFillerPct');
    const statLatestLeaf = document.getElementById('statLatestLeaf');

    // DOM Elements - Tables
    const tableGudangBody = document.getElementById('tableGudangBody');
    const tableConveyorBody = document.getElementById('tableConveyorBody');

    // DOM Elements - Filter & Refresh
    const inputStartDate = document.getElementById('inputStartDate');
    const inputEndDate = document.getElementById('inputEndDate');
    const btnApplyFilter = document.getElementById('btnApplyFilter');
    const btnResetFilter = document.getElementById('btnResetFilter');
    const manualRefreshBtn = document.getElementById('manualRefreshBtn');
    const refreshIcon = document.getElementById('refreshIcon');

    // DOM Elements - Settings (only badge now)
    let currentSettings = null;

    // Helper: Format Date String
    function formatTimeDisplay(dateStr) {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    function formatDateTimeDisplay(dateStr) {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('id-ID', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    // Helper: Determine Status Evaluation
    function evaluateTemp(val) {
        if (val >= THRESHOLDS.temp.normalMin && val <= THRESHOLDS.temp.normalMax) {
            return { status: 'normal', label: 'Normal / Ideal', badgeClass: 'badge-status-normal', borderClass: 'status-border-normal' };
        } else if (val <= THRESHOLDS.temp.warnMax && val >= (THRESHOLDS.temp.normalMin - 4.0)) {
            return { status: 'warning', label: 'Waspada (Agak Hangat/Dingin)', badgeClass: 'badge-status-warning', borderClass: 'status-border-warning' };
        } else {
            return { status: 'danger', label: 'Bahaya (Kritis)', badgeClass: 'badge-status-danger', borderClass: 'status-border-danger' };
        }
    }

    function evaluateHumidity(val) {
        if (val >= THRESHOLDS.humidity.normalMin && val <= THRESHOLDS.humidity.normalMax) {
            return { status: 'normal', label: 'Optimal', badgeClass: 'badge-status-normal', borderClass: 'status-border-normal' };
        } else if (val >= THRESHOLDS.humidity.warnMin && val <= THRESHOLDS.humidity.warnMax) {
            return { status: 'warning', label: 'Waspada', badgeClass: 'badge-status-warning', borderClass: 'status-border-warning' };
        } else {
            return { status: 'danger', label: 'Bahaya (Resiko Jamur/Kering)', badgeClass: 'badge-status-danger', borderClass: 'status-border-danger' };
        }
    }

    function evaluateGas(val) {
        if (val <= THRESHOLDS.gas.normalMax) {
            return { status: 'normal', label: 'Aman', badgeClass: 'badge-status-normal', borderClass: 'status-border-normal' };
        } else if (val <= THRESHOLDS.gas.warnMax) {
            return { status: 'warning', label: 'Waspada', badgeClass: 'badge-status-warning', borderClass: 'status-border-warning' };
        } else {
            return { status: 'danger', label: 'Kritis / Bahaya Gas', badgeClass: 'badge-status-danger', borderClass: 'status-border-danger' };
        }
    }

    // Browser Web Notification Trigger
    function sendBrowserNotification(title, body) {
        if ("Notification" in window && Notification.permission === "granted") {
            try {
                new Notification(title, {
                    body: body,
                    icon: '/static/img/warning.png'
                });
            } catch (e) {
                console.warn('Browser notification error:', e);
            }
        }
    }

    // 1. Fetch Latest Gudang Data
    async function fetchLatestGudang() {
        try {
            const res = await fetch(API.gudangLatest);
            const json = await res.json();
            if (!json.success || !json.data) return;

            const data = json.data;

            // Render Suhu
            valSuhu.textContent = Number(data.suhu).toFixed(1);
            const evalSuhu = evaluateTemp(data.suhu);
            badgeStatusSuhu.textContent = evalSuhu.label;
            badgeStatusSuhu.className = `badge rounded-pill px-2 py-1 ${evalSuhu.badgeClass}`;
            cardSuhu.className = `metric-card h-100 ${evalSuhu.borderClass}`;

            // Render Kelembapan
            valKelembapan.textContent = Number(data.kelembapan).toFixed(1);
            const evalHum = evaluateHumidity(data.kelembapan);
            badgeStatusKelembapan.textContent = evalHum.label;
            badgeStatusKelembapan.className = `badge rounded-pill px-2 py-1 ${evalHum.badgeClass}`;
            cardKelembapan.className = `metric-card h-100 ${evalHum.borderClass}`;

            // Render Gas
            valGas.textContent = data.gas;
            const evalGas = evaluateGas(data.gas);
            badgeStatusGas.textContent = evalGas.label;
            badgeStatusGas.className = `badge rounded-pill px-2 py-1 ${evalGas.badgeClass}`;
            cardGas.className = `metric-card h-100 ${evalGas.borderClass}`;

            // Render Fan
            if (data.status_fan) {
                badgeStatusFan.textContent = 'AKTIF';
                badgeStatusFan.className = 'badge rounded-pill px-2 py-1 bg-success text-white';
                iconFanRotate.classList.add('fan-spinning', 'text-success');
            } else {
                badgeStatusFan.textContent = 'MATI';
                badgeStatusFan.className = 'badge rounded-pill px-2 py-1 bg-secondary text-white';
                iconFanRotate.classList.remove('fan-spinning', 'text-success');
            }

            // Render Alarm & Emergency Banner
            if (data.status_alarm) {
                badgeStatusAlarm.textContent = 'BAHAYA (ON)';
                badgeStatusAlarm.className = 'badge rounded-pill px-2 py-1 alarm-active-indicator';
                
                // Show banner
                alarmBanner.classList.remove('d-none');
                alarmBannerDetails.textContent = `Peringatan: Suhu ${data.suhu}°C, Kelembapan ${data.kelembapan}%, Gas ${data.gas} ppm. Status fan: ${data.status_fan ? 'ON' : 'OFF'}`;

                // Play Audio Chime
                if (window.alarmAudio) {
                    window.alarmAudio.startAlarm();
                }

                // Browser Notification
                sendBrowserNotification(
                    "PERINGATAN GUDANG TEMBAKAU",
                    `Sistem Alarm Aktif! Suhu: ${data.suhu}°C | Gas: ${data.gas} ppm`
                );
            } else {
                badgeStatusAlarm.textContent = 'AMAN';
                badgeStatusAlarm.className = 'badge rounded-pill px-2 py-1 bg-success-subtle text-success border border-success-subtle';
                alarmBanner.classList.add('d-none');
                if (window.alarmAudio) {
                    window.alarmAudio.stopAlarm();
                }
            }

            // Last update label
            lblLastUpdate.textContent = formatDateTimeDisplay(data.timestamp);

        } catch (e) {
            console.error('Error fetching latest gudang:', e);
        }
    }

    // 2. Fetch Conveyor Stats & Latest
    async function fetchConveyorInfo() {
        try {
            // Stats
            let statsUrl = API.conveyorStats;
            if (filterStartDate || filterEndDate) {
                statsUrl += `?start_date=${filterStartDate}&end_date=${filterEndDate}`;
            }

            const [resStats, resLatest] = await Promise.all([
                fetch(statsUrl),
                fetch(API.conveyorLatest)
            ]);

            const jsonStats = await resStats.json();
            const jsonLatest = await resLatest.json();

            if (jsonStats.success && jsonStats.data) {
                const s = jsonStats.data;
                badgeTotalDaun.textContent = `Total: ${s.total} Daun`;

                statWrapperCount.textContent = s.wrapper;
                statWrapperPct.textContent = `(${s.percentages.wrapper}%)`;

                statBinderCount.textContent = s.binder;
                statBinderPct.textContent = `(${s.percentages.binder}%)`;

                statFillerCount.textContent = s.filler;
                statFillerPct.textContent = `(${s.percentages.filler}%)`;

                updateLeafChart(s.wrapper, s.binder, s.filler);
            }

            if (jsonLatest.success && jsonLatest.data) {
                const l = jsonLatest.data;
                const catClass = l.hasil_klasifikasi === 'wrapper' ? 'badge-wrapper'
                               : l.hasil_klasifikasi === 'binder' ? 'badge-binder' : 'badge-filler';

                statLatestLeaf.innerHTML = `
                    <span class="badge ${catClass} me-1 text-uppercase">${l.hasil_klasifikasi}</span>
                    <span class="small text-secondary">Akurasi: <strong>${l.confidence_percent}%</strong></span>
                `;
            } else {
                statLatestLeaf.textContent = 'Belum ada data conveyor';
            }

        } catch (e) {
            console.error('Error fetching conveyor info:', e);
        }
    }

    // 3. Fetch Gudang History (for Line Chart & Table)
    async function fetchGudangHistory() {
        try {
            let url = `${API.gudangHistory}?limit=48&order=asc`;
            if (filterStartDate) url += `&start_date=${filterStartDate}`;
            if (filterEndDate) url += `&end_date=${filterEndDate}`;

            const res = await fetch(url);
            const json = await res.json();
            if (!json.success || !json.data) return;

            const records = json.data;

            // Update Line Chart
            updateEnvChart(records);

            // Update Log Table (10 latest entries, reverse asc to desc)
            const tableRecords = [...records].reverse().slice(0, 10);
            renderTableGudang(tableRecords);

        } catch (e) {
            console.error('Error fetching gudang history:', e);
        }
    }

    // 4. Fetch Conveyor History (for Table)
    async function fetchConveyorHistory() {
        try {
            let url = `${API.conveyorHistory}?limit=10`;
            if (filterStartDate) url += `&start_date=${filterStartDate}`;
            if (filterEndDate) url += `&end_date=${filterEndDate}`;

            const res = await fetch(url);
            const json = await res.json();
            if (!json.success || !json.data) return;

            renderTableConveyor(json.data);

        } catch (e) {
            console.error('Error fetching conveyor history:', e);
        }
    }

    // Render Table Gudang
    function renderTableGudang(records) {
        if (!records || records.length === 0) {
            tableGudangBody.innerHTML = `
                <tr><td colspan="8" class="text-center py-4 text-secondary">Tidak ada data rekam pada rentang waktu ini.</td></tr>
            `;
            return;
        }

        let html = '';
        records.forEach((r, idx) => {
            const evalSuhu = evaluateTemp(r.suhu);
            const evalGas = evaluateGas(r.gas);
            const evalHum = evaluateHumidity(r.kelembapan);

            const overallBadge = r.status_alarm ? '<span class="badge bg-danger">BAHAYA</span>'
                                : (evalSuhu.status === 'danger' || evalGas.status === 'danger' || evalHum.status === 'danger')
                                ? '<span class="badge bg-danger">KRITIS</span>'
                                : (evalSuhu.status === 'warning' || evalGas.status === 'warning' || evalHum.status === 'warning')
                                ? '<span class="badge bg-warning text-dark">WASPADA</span>'
                                : '<span class="badge bg-success">NORMAL</span>';

            html += `
                <tr>
                    <td class="text-secondary fw-semibold">${idx + 1}</td>
                    <td><i class="bi bi-clock me-1 text-secondary"></i> ${formatDateTimeDisplay(r.timestamp)}</td>
                    <td><span class="fw-bold text-danger">${r.suhu}°C</span></td>
                    <td><span class="fw-bold text-primary">${r.kelembapan}%</span></td>
                    <td><span class="fw-bold text-warning">${r.gas} ppm</span></td>
                    <td>
                        ${r.status_fan 
                            ? '<span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-fan me-1"></i> AKTIF</span>' 
                            : '<span class="badge bg-secondary-subtle text-secondary">MATI</span>'}
                    </td>
                    <td>
                        ${r.status_alarm 
                            ? '<span class="badge bg-danger alarm-active-indicator"><i class="bi bi-bell-fill me-1"></i> AKTIF</span>' 
                            : '<span class="badge bg-light text-secondary border">AMAN</span>'}
                    </td>
                    <td>${overallBadge}</td>
                </tr>
            `;
        });
        tableGudangBody.innerHTML = html;
    }

    // Render Table Conveyor
    function renderTableConveyor(records) {
        if (!records || records.length === 0) {
            tableConveyorBody.innerHTML = `
                <tr><td colspan="6" class="text-center py-4 text-secondary">Tidak ada data klasifikasi daun pada rentang waktu ini.</td></tr>
            `;
            return;
        }

        let html = '';
        records.forEach((r, idx) => {
            const cat = r.hasil_klasifikasi.toLowerCase();
            let catBadge = '';
            let catDesc = '';

            if (cat === 'wrapper') {
                catBadge = '<span class="badge badge-wrapper text-uppercase px-2 py-1">Wrapper</span>';
                catDesc = 'Pembungkus Luar (Kualitas Terbaik)';
            } else if (cat === 'binder') {
                catBadge = '<span class="badge badge-binder text-uppercase px-2 py-1">Binder</span>';
                catDesc = 'Pengikat Tengah (Kualitas Sedang)';
            } else {
                catBadge = '<span class="badge badge-filler text-uppercase px-2 py-1">Filler</span>';
                catDesc = 'Pengisi Inti (Kualitas Standar)';
            }

            html += `
                <tr>
                    <td class="text-secondary fw-semibold">${idx + 1}</td>
                    <td><i class="bi bi-clock me-1 text-secondary"></i> ${formatDateTimeDisplay(r.timestamp)}</td>
                    <td>${catBadge}</td>
                    <td><code>${r.confidence_score}</code></td>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <div class="progress flex-fill" style="height: 6px; width: 60px;">
                                <div class="progress-bar bg-emerald" style="width: ${r.confidence_percent}%;"></div>
                            </div>
                            <span class="fw-semibold small">${r.confidence_percent}%</span>
                        </div>
                    </td>
                    <td class="small text-secondary">${catDesc}</td>
                </tr>
            `;
        });
        tableConveyorBody.innerHTML = html;
    }

    // 5. Setup & Update Chart.js
    function initCharts() {
        const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';
        const textColor = isDark ? '#94a3b8' : '#64748b';

        // A. Line Chart Suhu & Kelembapan
        const ctxEnv = document.getElementById('envLineChart').getContext('2d');
        envChart = new Chart(ctxEnv, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Suhu (°C)',
                        data: [],
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.08)',
                        borderWidth: 2.5,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                        tension: 0.35,
                        fill: true,
                        yAxisID: 'yTemp'
                    },
                    {
                        label: 'Kelembapan (%)',
                        data: [],
                        borderColor: '#0284c7',
                        backgroundColor: 'rgba(2, 132, 199, 0.08)',
                        borderWidth: 2.5,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                        tension: 0.35,
                        fill: true,
                        yAxisID: 'yHum'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            color: textColor,
                            font: { family: 'Plus Jakarta Sans', weight: '600', size: 12 },
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#1e293b' : '#ffffff',
                        titleColor: isDark ? '#f8fafc' : '#0f172a',
                        bodyColor: isDark ? '#cbd5e1' : '#334155',
                        borderColor: isDark ? '#334155' : '#e2e8f0',
                        borderWidth: 1,
                        padding: 10,
                        usePointStyle: true
                    }
                },
                scales: {
                    x: {
                        grid: { color: gridColor },
                        ticks: { color: textColor, font: { family: 'Plus Jakarta Sans', size: 11 } }
                    },
                    yTemp: {
                        type: 'linear',
                        position: 'left',
                        title: {
                            display: true,
                            text: 'Suhu (°C)',
                            color: '#ef4444',
                            font: { family: 'Plus Jakarta Sans', weight: '700' }
                        },
                        min: 15,
                        max: 40,
                        grid: { color: gridColor },
                        ticks: { color: textColor }
                    },
                    yHum: {
                        type: 'linear',
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Kelembapan (%)',
                            color: '#0284c7',
                            font: { family: 'Plus Jakarta Sans', weight: '700' }
                        },
                        min: 30,
                        max: 95,
                        grid: { drawOnChartArea: false },
                        ticks: { color: textColor }
                    }
                }
            }
        });

        // B. Doughnut Chart Klasifikasi Daun
        const ctxLeaf = document.getElementById('leafPieChart').getContext('2d');
        leafChart = new Chart(ctxLeaf, {
            type: 'doughnut',
            data: {
                labels: ['Wrapper', 'Binder', 'Filler'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: [
                        '#f59e0b', // Wrapper: Golden Amber
                        '#b45309', // Binder: Rich Cigar Brown
                        '#78350f'  // Filler: Deep Clay Leaf
                    ],
                    borderWidth: 2,
                    borderColor: isDark ? '#1e293b' : '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '68%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: textColor,
                            font: { family: 'Plus Jakarta Sans', weight: '600' },
                            usePointStyle: true,
                            padding: 15
                        }
                    },
                    tooltip: {
                        backgroundColor: isDark ? '#1e293b' : '#ffffff',
                        titleColor: isDark ? '#f8fafc' : '#0f172a',
                        bodyColor: isDark ? '#cbd5e1' : '#334155',
                        borderColor: isDark ? '#334155' : '#e2e8f0',
                        borderWidth: 1,
                        padding: 10
                    }
                }
            }
        });
    }

    function updateEnvChart(records) {
        if (!envChart) return;
        const labels = records.map(r => formatTimeDisplay(r.timestamp));
        const temps = records.map(r => r.suhu);
        const hums = records.map(r => r.kelembapan);

        envChart.data.labels = labels;
        envChart.data.datasets[0].data = temps;
        envChart.data.datasets[1].data = hums;
        envChart.update('none'); // Update smoothly without jarring re-render
    }

    function updateLeafChart(wrapper, binder, filler) {
        if (!leafChart) return;
        leafChart.data.datasets[0].data = [wrapper, binder, filler];
        leafChart.update('none');
    }

    // Refresh All Data function
    async function refreshAll() {
        if (isFetching) return;
        isFetching = true;
        refreshIcon.classList.add('fan-spinning');

        try {
            await Promise.all([
                fetchLatestGudang(),
                fetchConveyorInfo(),
                fetchGudangHistory(),
                fetchConveyorHistory(),
                fetchSettings()
            ]);
            navConnectionStatus.textContent = 'Live (5s)';
            navConnectionStatus.className = 'fw-semibold text-success';
        } catch (e) {
            console.error('Refresh all error:', e);
            navConnectionStatus.textContent = 'Koneksi Terputus';
            navConnectionStatus.className = 'fw-semibold text-danger';
        } finally {
            isFetching = false;
            refreshIcon.classList.remove('fan-spinning');
        }
    }

    // Listen for Theme Change Event to refresh chart colors
    window.addEventListener('themeChanged', (e) => {
        const isDark = e.detail.theme === 'dark';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)';
        const textColor = isDark ? '#94a3b8' : '#64748b';

        if (envChart) {
            envChart.options.scales.x.grid.color = gridColor;
            envChart.options.scales.x.ticks.color = textColor;
            envChart.options.scales.yTemp.grid.color = gridColor;
            envChart.options.scales.yTemp.ticks.color = textColor;
            envChart.options.scales.yHum.ticks.color = textColor;
            envChart.options.plugins.legend.labels.color = textColor;
            envChart.update();
        }

        if (leafChart) {
            leafChart.options.plugins.legend.labels.color = textColor;
            leafChart.data.datasets[0].borderColor = isDark ? '#1e293b' : '#ffffff';
            leafChart.update();
        }
    });

    // Dismiss Alarm Temporarily Button
    btnDismissAlarm?.addEventListener('click', () => {
        if (window.alarmAudio) {
            window.alarmAudio.stopAlarm();
        }
        alarmBanner.classList.add('d-none');
    });

    // Manual Refresh Button
    manualRefreshBtn?.addEventListener('click', () => {
        refreshAll();
    });

    // Filter Buttons Handlers
    btnApplyFilter?.addEventListener('click', () => {
        filterStartDate = inputStartDate.value;
        filterEndDate = inputEndDate.value;
        document.getElementById('lblChartRange').textContent = 
            `Rentang: ${filterStartDate || 'Awal'} s/d ${filterEndDate || 'Kini'}`;
        refreshAll();
    });

    btnResetFilter?.addEventListener('click', () => {
        inputStartDate.value = '';
        inputEndDate.value = '';
        filterStartDate = '';
        filterEndDate = '';
        document.getElementById('lblChartRange').textContent = 'Histori sensor gudang tembakau';
        refreshAll();
    });

    // 6. Settings Handlers (Update Fan Mode Badge Only)
    async function fetchSettings() {
        if(!badgeModeFan) return;
        try {
            const res = await fetch(API.settings);
            const json = await res.json();
            if (json.success && json.data) {
                currentSettings = json.data;
                // Update indicator Mode Fan di card Aktuator
                if (currentSettings.mode_fan === 'manual') {
                    badgeModeFan.textContent = 'MANUAL';
                    badgeModeFan.className = 'badge bg-warning text-dark rounded-pill px-2 py-1';
                } else {
                    badgeModeFan.textContent = 'AUTO';
                    badgeModeFan.className = 'badge bg-secondary rounded-pill px-2 py-1';
                }
            }
        } catch (e) {
            console.error('Error fetching settings:', e);
        }
    }

    // Initialization
    initCharts();
    refreshAll();

    // Start 5-Second Interval Polling
    refreshTimer = setInterval(refreshAll, 5000);
});
