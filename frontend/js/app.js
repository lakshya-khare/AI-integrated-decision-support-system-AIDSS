/**
 * AIDSS - Main Controller Application Logic
 * Real-Time Operational Playback, Time Scrubbing, Dynamic Signalling & OR Dispatch Integration.
 */

document.addEventListener('DOMContentLoaded', () => {
    // State Store
    const state = {
        status: null,
        stations: [],
        blockSections: [],
        trains: [],
        recommendations: [],
        selectedRec: null,
        kpis: null,
        auditLogs: [],
        currentTab: 'tab-marey',
        mareyChart: null,
        schematic: null,
        
        // Real-Time Playback Clock
        simTimeSec: 21600,       // 06:00:00 IST default
        isPlaying: false,
        playbackSpeed: 10,       // 10x real-time default
        playbackTimer: null,
    };

    // Initialize Components
    initPlaybackTimeline();
    initTabs();
    initModals();
    initMareyControls();
    initWhatIfForm();
    initActionButtons();

    // Fetch initial datasets
    loadAllData();

    // 1. Operational Playback Timeline & Clock Controls
    function initPlaybackTimeline() {
        const slider = document.getElementById('timelineSlider');
        const playBtn = document.getElementById('btnPlayPause');
        const playIcon = document.getElementById('playPauseIcon');
        const playText = document.getElementById('playPauseText');
        const speedButtons = document.querySelectorAll('.btn-speed');
        const jumpButtons = document.querySelectorAll('.btn-jump');

        // Play / Pause toggle
        playBtn.addEventListener('click', () => {
            state.isPlaying = !state.isPlaying;
            if (state.isPlaying) {
                playBtn.classList.add('playing');
                playIcon.textContent = '⏸';
                playText.textContent = 'PAUSE';
                startPlaybackTimer();
            } else {
                playBtn.classList.remove('playing');
                playIcon.textContent = '▶';
                playText.textContent = 'PLAY';
                stopPlaybackTimer();
            }
        });

        // Speed multipliers
        speedButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                speedButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                state.playbackSpeed = parseFloat(btn.getAttribute('data-speed'));
            });
        });

        // Range slider input
        slider.addEventListener('input', () => {
            state.simTimeSec = parseInt(slider.value);
            updateOperationalTime(state.simTimeSec);
        });

        // Shift jump buttons
        jumpButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetSec = parseInt(btn.getAttribute('data-time'));
                state.simTimeSec = targetSec;
                slider.value = targetSec;
                updateOperationalTime(targetSec);
            });
        });

        // Set initial clock
        updateOperationalTime(state.simTimeSec);
    }

    function startPlaybackTimer() {
        stopPlaybackTimer();
        state.playbackTimer = setInterval(() => {
            // Step forward based on speed (called every 200ms)
            const step = Math.round(state.playbackSpeed * 0.2);
            state.simTimeSec = (state.simTimeSec + step) % 86400;
            
            document.getElementById('timelineSlider').value = state.simTimeSec;
            updateOperationalTime(state.simTimeSec);
        }, 200);
    }

    function stopPlaybackTimer() {
        if (state.playbackTimer) {
            clearInterval(state.playbackTimer);
            state.playbackTimer = null;
        }
    }

    function updateOperationalTime(timeSec) {
        const hrs = Math.floor(timeSec / 3600) % 24;
        const mins = Math.floor((timeSec % 3600) / 60);
        const secs = Math.floor(timeSec % 60);
        const timeFormatted = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')} IST`;

        // Update Scrub display and Header Clock
        document.getElementById('scrubberTimeDisplay').textContent = timeFormatted;
        document.getElementById('clockDisplay').textContent = timeFormatted;

        // Update Shift indicator
        const shiftTag = document.getElementById('shiftTag');
        if (hrs >= 6 && hrs < 14) {
            shiftTag.textContent = 'SHIFT A • 06:00 - 14:00';
        } else if (hrs >= 14 && hrs < 22) {
            shiftTag.textContent = 'SHIFT B • 14:00 - 22:00';
        } else {
            shiftTag.textContent = 'SHIFT C • 22:00 - 06:00';
        }

        // Propagate to Marey Chart
        if (state.mareyChart) {
            state.mareyChart.setSimulationTime(timeSec);
        }

        // Propagate to Track Schematic if active
        if (state.currentTab === 'tab-schematic' && state.schematic) {
            state.schematic.setSimulationTime(timeSec);
        }

        // Propagate to Signalling Telemetry if active
        if (state.currentTab === 'tab-telemetry') {
            loadSignalAspects(timeSec);
        }

        // Update active KPIs
        loadKPIs(timeSec);

        // Update recommendations dynamically based on passing trains / operational window
        if (!state._lastRecUpdate || Math.abs(timeSec - state._lastRecUpdate) >= 60) {
            state._lastRecUpdate = timeSec;
            loadRecommendations(timeSec);
        }
    }

    // 2. Navigation Tabs
    function initTabs() {
        const tabs = document.querySelectorAll('.nav-tab');
        const panels = document.querySelectorAll('.tab-panel');

        tabs.forEach((tab) => {
            tab.addEventListener('click', () => {
                const target = tab.getAttribute('data-tab');
                tabs.forEach(t => t.classList.remove('active'));
                panels.forEach(p => p.classList.remove('active'));

                tab.classList.add('active');
                document.getElementById(target).classList.add('active');
                state.currentTab = target;

                if (target === 'tab-marey' && state.mareyChart) {
                    setTimeout(() => state.mareyChart.resizeCanvas(), 50);
                } else if (target === 'tab-schematic' && state.schematic) {
                    state.schematic.setSimulationTime(state.simTimeSec);
                } else if (target === 'tab-telemetry') {
                    loadCapacityAnalytics();
                    loadSignalAspects(state.simTimeSec);
                } else if (target === 'tab-audit') {
                    loadAuditTrail();
                }
            });
        });
    }

    // 3. API Data Loaders
    async function loadAllData() {
        try {
            await Promise.all([
                loadStatus(),
                loadInfrastructure(),
                loadTrains(),
                loadKPIs(state.simTimeSec),
                loadRecommendations(),
                loadAuditTrail()
            ]);

            // Initialize Visualizers once data arrives
            if (!state.mareyChart) {
                state.mareyChart = new MareyChart('mareyCanvas', 'mareyContainer');
            }
            state.mareyChart.setData(state.stations, state.trains);
            state.mareyChart.setSimulationTime(state.simTimeSec);

            if (!state.schematic) {
                state.schematic = new TrackSchematic('schematicViewport');
            }
            state.schematic.setData(state.stations, state.trains);
            state.schematic.setSimulationTime(state.simTimeSec);

            populateWhatIfSelectors();
        } catch (err) {
            console.error('Data load failure:', err);
        }
    }

    async function loadStatus() {
        const res = await fetch('/api/status');
        state.status = await res.json();
        
        const badge = document.getElementById('currentSourceBadge');
        if (state.status.mode === 'sample') {
            badge.textContent = 'SAMPLE DATA TWIN';
            badge.style.color = '#10b981';
        } else {
            badge.textContent = 'LIVE TMS GATEWAY';
            badge.style.color = '#38bdf8';
        }
    }

    async function loadInfrastructure() {
        const res = await fetch('/api/infrastructure');
        const data = await res.json();
        state.stations = data.stations;
        state.blockSections = data.block_sections;
    }

    async function loadTrains() {
        const res = await fetch('/api/trains/active?limit=80');
        state.trains = await res.json();
    }

    async function loadKPIs(timeSec) {
        try {
            const url = timeSec !== undefined ? `/api/kpis?time_sec=${timeSec}` : '/api/kpis';
            const res = await fetch(url);
            state.kpis = await res.json();

            document.getElementById('kpiThroughput').innerHTML = `${state.kpis.throughput_trains_24h} <span class="kpi-unit">TRAINS/24H</span>`;
            document.getElementById('kpiActiveTrains').textContent = `Active on Section: ${state.kpis.active_trains_on_section}`;
            document.getElementById('kpiPunctuality').textContent = `${state.kpis.punctuality_rate_percent}%`;
            document.getElementById('kpiAvgDelay').innerHTML = `${state.kpis.average_delay_minutes} <span class="kpi-unit">MINS</span>`;
            document.getElementById('kpiUtilization').textContent = `${state.kpis.track_utilization_percent}%`;

            // Calculate actual total delay saved from recommendations
            let totalSavedMins = 0;
            state.recommendations.forEach(r => {
                totalSavedMins += (r.delay_saved_minutes || r.projected_delay_savings_mins || 0);
            });
            document.getElementById('kpiMitigated').innerHTML = `${totalSavedMins.toFixed(1)} <span class="kpi-unit">MINS SAVED</span>`;
        } catch (err) {
            console.error('Failed to load KPIs:', err);
        }
    }

    async function loadRecommendations(timeSec) {
        try {
            const t = timeSec !== undefined ? timeSec : state.simTimeSec;
            const url = t !== undefined ? `/api/recommendations?time_sec=${t}&lookahead_mins=90` : '/api/recommendations';
            const res = await fetch(url);
            state.recommendations = await res.json();
            
            const badgeCount = document.getElementById('recBadgeCount');
            const pendingCount = document.getElementById('recPendingCount');
            const activePending = state.recommendations.filter(r => r.status === 'PENDING');
            badgeCount.textContent = activePending.length;
            pendingCount.textContent = `${activePending.length} Active Pending Interventions in Lookahead`;

            renderRecommendationsList();
        } catch (err) {
            console.error('Failed to load recommendations:', err);
        }
    }

    async function loadAuditTrail() {
        const res = await fetch('/api/audit?limit=40');
        state.auditLogs = await res.json();
        renderAuditTable();
    }

    // 4. Recommendations Rendering & Explainability
    function renderRecommendationsList() {
        const container = document.getElementById('recCardsContainer');
        container.innerHTML = '';

        if (!state.recommendations.length) {
            container.innerHTML = '<div style="padding:20px; text-align:center; color:#64748b;">No active conflicts for approaching trains in this window. Dispatch schedule fully optimal.</div>';
            return;
        }

        state.recommendations.forEach((rec) => {
            const isSelected = state.selectedRec && state.selectedRec.recommendation_id === rec.recommendation_id;
            const isApproved = rec.status === 'APPROVED';
            const card = document.createElement('div');
            card.className = `rec-card ${isSelected ? 'selected' : ''} ${isApproved ? 'approved-card' : ''}`;
            
            let urgencyHtml = '';
            if (rec.mins_until_arrival !== undefined) {
                if (rec.mins_until_arrival <= 15) {
                    urgencyHtml = `<span class="status-pill pill-danger" style="font-size:9px; padding:1px 5px;">⚡ PASSING IN ${Math.round(rec.mins_until_arrival)}m</span>`;
                } else {
                    urgencyHtml = `<span class="status-pill pill-info" style="font-size:9px; padding:1px 5px;">APPROACHING IN ${Math.round(rec.mins_until_arrival)}m</span>`;
                }
            } else if (isApproved) {
                urgencyHtml = `<span class="status-pill pill-ok" style="font-size:9px; padding:1px 5px;">✓ APPROVED (LOOP LOCKED)</span>`;
            }

            card.innerHTML = `
                <div class="rec-card-top">
                    <span class="rec-badge" style="${isApproved ? 'background:#065f46; color:#34d399; border-color:#059669;' : ''}">${isApproved ? '✓ APPROVED' : (rec.action || 'LOOP_HOLD')}</span>
                    ${urgencyHtml}
                    <span class="rec-time-saved">+${rec.delay_saved_minutes || rec.projected_delay_savings_mins || 14}m SAVED</span>
                </div>
                <div class="rec-train-name">${rec.train_number} &bull; ${rec.train_name}</div>
                <div class="rec-action-desc">${rec.primary_rationale}</div>
            `;

            card.addEventListener('click', () => {
                document.querySelectorAll('.rec-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                showRecommendationDetail(rec);
            });

            container.appendChild(card);
        });

        // Automatically select the first recommendation
        if (!state.selectedRec || !state.recommendations.some(r => r.recommendation_id === state.selectedRec.recommendation_id)) {
            if (state.recommendations.length > 0) {
                showRecommendationDetail(state.recommendations[0]);
                if (container.children[0]) container.children[0].classList.add('selected');
            }
        }
    }

    function showRecommendationDetail(rec) {
        state.selectedRec = rec;
        document.getElementById('recPlaceholder').classList.add('hidden');
        const detailCard = document.getElementById('recDetailCard');
        detailCard.classList.remove('hidden');

        const isApproved = rec.status === 'APPROVED';
        document.getElementById('detailActionBadge').textContent = isApproved ? 'APPROVED & ROUTED' : (rec.action || 'LOOP HOLD');
        document.getElementById('detailRecId').textContent = rec.recommendation_id;
        document.getElementById('detailSavings').textContent = `+${rec.delay_saved_minutes || rec.projected_delay_savings_mins} MINS SAVED`;
        document.getElementById('detailTrainTitle').textContent = `${rec.train_number} - ${rec.train_name}`;
        document.getElementById('detailStation').textContent = rec.station;
        document.getElementById('detailLine').textContent = rec.assigned_line;
        document.getElementById('detailHoldTime').textContent = `${rec.hold_minutes} Mins (Arrival: ${rec.target_time_formatted || '--:--'})`;
        document.getElementById('detailStatus').textContent = isApproved ? 'APPROVED (DISPATCH SLIP TRANSMITTED)' : 'PENDING APPROVAL';
        document.getElementById('detailStatus').style.color = isApproved ? '#34d399' : '#f59e0b';

        document.getElementById('detailRationaleText').textContent = rec.primary_rationale;

        // Button state
        const btnApprove = document.getElementById('btnApproveRec');
        const btnOverride = document.getElementById('btnOverrideRec');
        if (isApproved) {
            btnApprove.innerHTML = '<span class="icon">✓</span> ROUTE LOCKED ON LOOP (TRANSMITTED)';
            btnApprove.disabled = true;
            btnApprove.style.opacity = '0.6';
            btnOverride.disabled = true;
            btnOverride.style.opacity = '0.4';
        } else {
            btnApprove.innerHTML = '<span class="icon">✓</span> APPROVE & TRANSMIT DISPATCH SLIP';
            btnApprove.disabled = false;
            btnApprove.style.opacity = '1.0';
            btnOverride.disabled = false;
            btnOverride.style.opacity = '1.0';
        }

        // Justifications
        const justList = document.getElementById('detailJustifications');
        justList.innerHTML = '';
        (rec.technical_justifications || []).forEach(j => {
            const li = document.createElement('li');
            li.textContent = j;
            justList.appendChild(li);
        });

        // Counterfactual
        document.getElementById('detailCounterfactual').textContent = rec.counterfactual_risk;

        // Compliance
        const compList = document.getElementById('detailCompliance');
        compList.innerHTML = '';
        (rec.compliance_rules || []).forEach(r => {
            const li = document.createElement('li');
            li.textContent = r;
            compList.appendChild(li);
        });

        // Hide override box if open
        document.getElementById('overrideBox').classList.add('hidden');
    }

    // 5. Decision Action Handlers (Approve & Override)
    function initActionButtons() {
        // Approve Button
        document.getElementById('btnApproveRec').addEventListener('click', async () => {
            if (!state.selectedRec || state.selectedRec.status === 'APPROVED') return;
            const targetRec = state.selectedRec;
            try {
                const payload = {
                    recommendation_id: targetRec.recommendation_id,
                    action_taken: 'APPROVED',
                    controller_id: 'WAT-SCOR-01'
                };
                const res = await fetch('/api/decisions/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    // Update entire system immediately: trains, Marey chart, schematic, KPIs, recommendations, audit
                    await loadTrains();
                    await loadRecommendations(state.simTimeSec);
                    await loadKPIs(state.simTimeSec);
                    await loadAuditTrail();

                    if (state.mareyChart) state.mareyChart.setData(state.stations, state.trains);
                    if (state.schematic) state.schematic.setData(state.stations, state.trains);

                    alert(`✓ DISPATCH SLIP TRANSMITTED:\nRecommendation ${targetRec.recommendation_id} Approved.\nTrain ${targetRec.train_number} diverted to Loop Line at ${targetRec.station}.\nMain Line clear for high-priority overtake.\nLive timetable and visualizers updated!`);
                }
            } catch (err) {
                alert('Error submitting approval: ' + err);
            }
        });

        // Open Override Box
        document.getElementById('btnOverrideRec').addEventListener('click', () => {
            document.getElementById('overrideBox').classList.remove('hidden');
            document.getElementById('overrideReasonInput').focus();
        });

        // Cancel Override
        document.getElementById('btnCancelOverride').addEventListener('click', () => {
            document.getElementById('overrideBox').classList.add('hidden');
        });

        // Confirm Override
        document.getElementById('btnConfirmOverride').addEventListener('click', async () => {
            const reason = document.getElementById('overrideReasonInput').value.trim();
            if (!reason) {
                alert('Mandatory Requirement: Please enter an operational justification for manual override per General & Subsidiary Rules (G&SR).');
                return;
            }

            try {
                const payload = {
                    recommendation_id: state.selectedRec.recommendation_id,
                    action_taken: 'OVERRIDDEN',
                    controller_id: 'WAT-SCOR-01',
                    override_reason: reason
                };
                const res = await fetch('/api/decisions/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (res.ok) {
                    alert(`⚡ Controller Manual Override Logged into Audit Record.\nReason: "${reason}"`);
                    document.getElementById('overrideBox').classList.add('hidden');
                    document.getElementById('overrideReasonInput').value = '';
                    await loadRecommendations(state.simTimeSec);
                    await loadKPIs(state.simTimeSec);
                    await loadAuditTrail();
                }
            } catch (err) {
                alert('Error submitting override: ' + err);
            }
        });

        // Manual Run Re-optimize Button
        document.getElementById('btnManualOptimize').addEventListener('click', async () => {
            const btn = document.getElementById('btnManualOptimize');
            btn.innerHTML = '<span class="btn-icon">⏳</span> SOLVING...';
            btn.disabled = true;

            try {
                const res = await fetch('/api/optimize', { method: 'POST' });
                const data = await res.json();
                await loadTrains();
                await loadKPIs(state.simTimeSec);
                await loadRecommendations();

                if (state.mareyChart) state.mareyChart.setData(state.stations, state.trains);
                if (state.schematic) state.schematic.setData(state.stations, state.trains);

                alert(`AI Optimization Completed.\nRecalculated ${data.trains_recalculated} train paths. ${data.recommendations_count} recommendations active.`);
            } catch (err) {
                alert('Optimization error: ' + err);
            } finally {
                btn.innerHTML = '<span class="btn-icon">⚡</span> RUN RE-OPTIMIZE';
                btn.disabled = false;
            }
        });

        // Refresh Audit
        document.getElementById('btnRefreshAudit').addEventListener('click', loadAuditTrail);
    }

    // 6. Marey Chart Controls & Filtering
    function initMareyControls() {
        // Shift window pills
        const pills = document.querySelectorAll('.panel-toolbar .btn-pill:not(.filter-dir):not(.filter-prio)');
        pills.forEach((p) => {
            p.addEventListener('click', () => {
                pills.forEach(x => x.classList.remove('active'));
                p.classList.add('active');

                const win = p.getAttribute('data-window');
                const [start, end] = win.split('-').map(Number);
                if (state.mareyChart) {
                    state.mareyChart.setTimeWindow(start, end);
                }
            });
        });

        // Direction filter pills
        const dirPills = document.querySelectorAll('.filter-dir');
        dirPills.forEach((p) => {
            p.addEventListener('click', () => {
                dirPills.forEach(x => x.classList.remove('active'));
                p.classList.add('active');
                const dir = p.getAttribute('data-dir');
                if (state.mareyChart) {
                    state.mareyChart.setDirectionFilter(dir);
                }
            });
        });

        // Priority filter pills
        const prioPills = document.querySelectorAll('.filter-prio');
        prioPills.forEach((p) => {
            p.addEventListener('click', () => {
                prioPills.forEach(x => x.classList.remove('active'));
                p.classList.add('active');
                const prio = p.getAttribute('data-prio');
                if (state.mareyChart) {
                    state.mareyChart.setPriorityFilter(prio);
                }
            });
        });

        // Spotlight train select
        const searchInput = document.getElementById('searchTrainInput');
        if (searchInput) {
            searchInput.addEventListener('change', () => {
                const trainNo = searchInput.value;
                if (state.mareyChart) {
                    state.mareyChart.focusTrain(trainNo);
                }
            });
        }

        document.getElementById('btnZoomIn').addEventListener('click', () => {
            if (state.mareyChart) {
                state.mareyChart.startTimeSec += 3600;
                state.mareyChart.endTimeSec -= 3600;
                state.mareyChart.render();
            }
        });

        document.getElementById('btnZoomOut').addEventListener('click', () => {
            if (state.mareyChart) {
                state.mareyChart.startTimeSec = Math.max(0, state.mareyChart.startTimeSec - 3600);
                state.mareyChart.endTimeSec = Math.min(86400, state.mareyChart.endTimeSec + 3600);
                state.mareyChart.render();
            }
        });

        document.getElementById('btnResetChart').addEventListener('click', () => {
            if (state.mareyChart) {
                state.mareyChart.setTimeWindow(0, 24);
                state.mareyChart.setDirectionFilter('ALL');
                state.mareyChart.setPriorityFilter('ALL');
                state.mareyChart.focusTrain(null);
                
                pills.forEach(x => x.classList.remove('active'));
                pills[0].classList.add('active');
                dirPills.forEach(x => x.classList.remove('active'));
                dirPills[0].classList.add('active');
                prioPills.forEach(x => x.classList.remove('active'));
                prioPills[0].classList.add('active');
                if (searchInput) searchInput.value = '';
            }
        });
    }

    // 7. Multi-Condition Compound What-If Simulation Form
    function populateWhatIfSelectors() {
        const spotlightSelect = document.getElementById('searchTrainInput');
        if (spotlightSelect) {
            spotlightSelect.innerHTML = '<option value="">-- ALL TRAINS (SELECT TO ISOLATE) --</option>';
            state.trains.forEach((t) => {
                const opt = document.createElement('option');
                opt.value = t.train_number;
                opt.textContent = `${t.train_number} - ${t.name} (${t.direction})`;
                spotlightSelect.appendChild(opt);
            });
        }

        ['c1TrainNo', 'c2TrainNo'].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.innerHTML = '';
            state.trains.forEach((t) => {
                const opt = document.createElement('option');
                opt.value = t.train_number;
                opt.textContent = `${t.train_number} - ${t.name} (${t.priority})`;
                el.appendChild(opt);
            });
        });

        ['c1Station', 'c2Station'].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.innerHTML = '';
            state.stations.forEach((s) => {
                const opt = document.createElement('option');
                opt.value = s.code;
                opt.textContent = `${s.name} (${s.code})`;
                el.appendChild(opt);
            });
        });

        ['c1BlockId', 'c2BlockId'].forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.innerHTML = '';
            state.blockSections.forEach((b) => {
                const opt = document.createElement('option');
                opt.value = b.section_id;
                opt.textContent = `${b.section_id} (${b.length_km} km, Double Line)`;
                el.appendChild(opt);
            });
        });
    }

    function initWhatIfForm() {
        const c1Type = document.getElementById('c1Type');
        const c2Type = document.getElementById('c2Type');

        function updateC1() {
            const val = c1Type.value;
            document.getElementById('c1RowTrainDelay').classList.toggle('hidden', val !== 'TRAIN_DELAY');
            document.getElementById('c1RowStation').classList.toggle('hidden', val === 'TRACK_BLOCK');
            document.getElementById('c1RowBlock').classList.toggle('hidden', val !== 'TRACK_BLOCK');
            document.getElementById('c1RowSpeed').classList.toggle('hidden', val !== 'SPEED_RESTRICTION');
        }

        function updateC2() {
            const val = c2Type.value;
            document.getElementById('c2RowTrainDelay').classList.toggle('hidden', val !== 'TRAIN_DELAY');
            document.getElementById('c2RowStation').classList.toggle('hidden', val === 'TRACK_BLOCK');
            document.getElementById('c2RowBlock').classList.toggle('hidden', val !== 'TRACK_BLOCK');
            document.getElementById('c2RowSpeed').classList.toggle('hidden', val !== 'SPEED_RESTRICTION');
        }

        c1Type.addEventListener('change', updateC1);
        c2Type.addEventListener('change', updateC2);

        // Preset 1: VZM Loco Breakdown + CPP Block
        document.getElementById('preset1Btn').addEventListener('click', () => {
            document.getElementById('simName').value = 'Loco Snag at VZM & Track Block on CPP-BTVA';
            document.getElementById('c1Enabled').checked = true;
            c1Type.value = 'TRAIN_DELAY';
            document.getElementById('c1Station').value = 'VZM';
            document.getElementById('c1DelayMins').value = 35;
            
            document.getElementById('c2Enabled').checked = true;
            c2Type.value = 'TRACK_BLOCK';
            document.getElementById('c2BlockId').value = 'CPP-BTVA';
            updateC1();
            updateC2();
        });

        // Preset 2: Freight Stall + KPL TSR 30
        document.getElementById('preset2Btn').addEventListener('click', () => {
            document.getElementById('simName').value = 'Talcher Freight Stall at KPL & TSR 30 km/h at GVI';
            document.getElementById('c1Enabled').checked = true;
            c1Type.value = 'TRAIN_DELAY';
            document.getElementById('c1Station').value = 'KPL';
            document.getElementById('c1DelayMins').value = 40;
            
            document.getElementById('c2Enabled').checked = true;
            c2Type.value = 'SPEED_RESTRICTION';
            document.getElementById('c2Station').value = 'GVI';
            document.getElementById('c2SpeedKmh').value = 30;
            updateC1();
            updateC2();
        });

        // Preset 3: CHE Passenger Overhaul + NWP-RMZ Block
        document.getElementById('preset3Btn').addEventListener('click', () => {
            document.getElementById('simName').value = 'CHE Passenger Overhaul & Single Line NWP-RMZ';
            document.getElementById('c1Enabled').checked = true;
            c1Type.value = 'TRAIN_DELAY';
            document.getElementById('c1Station').value = 'CHE';
            document.getElementById('c1DelayMins').value = 25;
            
            document.getElementById('c2Enabled').checked = true;
            c2Type.value = 'TRACK_BLOCK';
            document.getElementById('c2BlockId').value = 'NWP-RMZ';
            updateC1();
            updateC2();
        });

        // Form Submit
        document.getElementById('whatIfForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btnRunSimulation');
            btn.innerHTML = '⚡ COMPUTING COUNTERFACTUAL...';
            btn.disabled = true;

            const c1Active = document.getElementById('c1Enabled').checked;
            const c2Active = document.getElementById('c2Enabled').checked;

            const conditions = [];
            if (c1Active) {
                conditions.push({
                    condition_id: 'C1',
                    enabled: true,
                    condition_type: c1Type.value,
                    target_train_no: document.getElementById('c1TrainNo').value,
                    target_station: document.getElementById('c1Station').value,
                    target_block_id: document.getElementById('c1BlockId').value,
                    delay_minutes: parseFloat(document.getElementById('c1DelayMins').value || '0'),
                    speed_restriction_kmh: parseInt(document.getElementById('c1SpeedKmh').value || '30')
                });
            }
            if (c2Active) {
                conditions.push({
                    condition_id: 'C2',
                    enabled: true,
                    condition_type: c2Type.value,
                    target_train_no: document.getElementById('c2TrainNo').value,
                    target_station: document.getElementById('c2Station').value,
                    target_block_id: document.getElementById('c2BlockId').value,
                    delay_minutes: parseFloat(document.getElementById('c2DelayMins').value || '0'),
                    speed_restriction_kmh: parseInt(document.getElementById('c2SpeedKmh').value || '30')
                });
            }

            const payload = {
                scenario_name: document.getElementById('simName').value,
                conditions: conditions
            };

            try {
                const res = await fetch('/api/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const result = await res.json();
                renderSimulationResults(result);
            } catch (err) {
                alert('Simulation error: ' + err);
            } finally {
                btn.innerHTML = '⚡ EXECUTE COMPOUND WHAT-IF SIMULATION';
                btn.disabled = false;
            }
        });
    }

    let isGhostOverlayActive = false;

    function renderSimulationResults(result) {
        document.getElementById('simEmptyNotice').classList.add('hidden');
        document.getElementById('simResultsContainer').classList.remove('hidden');

        document.getElementById('simSummaryText').textContent = result.impact_summary;

        document.getElementById('deltaDelay').textContent = `${result.kpi_delta.delay_change_mins > 0 ? '+' : ''}${result.kpi_delta.delay_change_mins}m`;
        document.getElementById('deltaDelay').style.color = result.kpi_delta.delay_change_mins > 5 ? '#f87171' : '#10b981';

        document.getElementById('deltaPunctuality').textContent = `${result.kpi_delta.punctuality_change_percent > 0 ? '+' : ''}${result.kpi_delta.punctuality_change_percent}%`;
        document.getElementById('deltaThroughput').textContent = `${result.kpi_delta.throughput_change >= 0 ? '+' : ''}${result.kpi_delta.throughput_change}`;
        document.getElementById('deltaRecCount').textContent = result.new_recommendations.length;

        document.getElementById('baseDelay').textContent = `${result.baseline_kpis.average_delay_minutes} mins`;
        document.getElementById('simDelay').textContent = `${result.scenario_kpis.average_delay_minutes} mins`;

        document.getElementById('basePunct').textContent = `${result.baseline_kpis.punctuality_rate_percent}%`;
        document.getElementById('simPunct').textContent = `${result.scenario_kpis.punctuality_rate_percent}%`;

        document.getElementById('baseThroughput').textContent = `${result.baseline_kpis.throughput_trains_24h} trains`;
        document.getElementById('simThroughput').textContent = `${result.scenario_kpis.throughput_trains_24h} trains`;

        document.getElementById('baseUtil').textContent = `${result.baseline_kpis.track_utilization_percent}%`;
        document.getElementById('simUtil').textContent = `${result.scenario_kpis.track_utilization_percent}%`;

        // Render Train-by-Train Comparative Delta Table
        const diffTbody = document.getElementById('simTrainDiffBody');
        diffTbody.innerHTML = '';
        const diffs = result.train_diffs || [];

        if (!diffs.length) {
            diffTbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:15px; color:#64748b;">No individual trains directly disrupted. Schedule absorbed within headway buffers.</td></tr>';
        } else {
            diffs.forEach(d => {
                const tr = document.createElement('tr');
                const isLate = d.delay_delta_mins > 0;
                tr.innerHTML = `
                    <td><strong>${d.train_number}</strong></td>
                    <td>${d.train_name}</td>
                    <td><span class="status-pill ${d.direction === 'UP' ? 'pill-info' : 'pill-ok'}">${d.direction}</span></td>
                    <td style="color:#94a3b8;">${d.baseline_arrival}</td>
                    <td style="color:${isLate ? '#f87171' : '#34d399'}; font-weight:700;">${d.simulated_arrival}</td>
                    <td style="color:${isLate ? '#f87171' : '#34d399'}; font-weight:700;">${isLate ? '+' : ''}${d.delay_delta_mins}m</td>
                    <td><span class="status-pill ${d.delay_delta_mins >= 15 ? 'pill-danger' : (d.delay_delta_mins >= 5 ? 'pill-warning' : 'pill-ok')}">${d.status}</span></td>
                `;
                diffTbody.appendChild(tr);
            });
        }

        // Toggle Marey Overlay Button
        const overlayBtn = document.getElementById('btnToggleMareyOverlay');
        overlayBtn.classList.remove('hidden');
        overlayBtn.onclick = () => {
            isGhostOverlayActive = !isGhostOverlayActive;
            if (isGhostOverlayActive) {
                overlayBtn.textContent = '✕ REMOVE GHOST OVERLAY';
                overlayBtn.style.background = '#dc2626';
                if (state.mareyChart) state.mareyChart.setSimulatedTrains(result.simulated_trains);
                
                // Switch to Marey Tab
                document.querySelector('.nav-tab[data-tab="tab-marey"]').click();
            } else {
                overlayBtn.textContent = '👁️ PREVIEW ON MAREY CHART';
                overlayBtn.style.background = '#0284c7';
                if (state.mareyChart) state.mareyChart.clearSimulatedTrains();
            }
        };
    }

    // 8. Audit Table Rendering
    function renderAuditTable() {
        const tbody = document.getElementById('auditTableBody');
        tbody.innerHTML = '';

        if (!state.auditLogs.length) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:#64748b; padding:20px;">No manual controller overrides logged yet. All dispatch decisions adhering to automated schedule.</td></tr>';
            return;
        }

        state.auditLogs.forEach((rec) => {
            const tr = document.createElement('tr');
            const isApproved = rec.event_type.includes('APPROVED');
            const isOverridden = rec.event_type.includes('OVERRIDDEN');

            tr.innerHTML = `
                <td><strong>${rec.audit_id}</strong></td>
                <td>${rec.timestamp}</td>
                <td><span style="color:#38bdf8;">${rec.controller_id}</span></td>
                <td>
                    <span class="status-pill ${isApproved ? 'pill-ok' : (isOverridden ? 'pill-warning' : 'pill-info')}">
                        ${rec.event_type}
                    </span>
                </td>
                <td><strong>${rec.train_number}</strong></td>
                <td>${rec.location}</td>
                <td>${rec.action_taken}</td>
                <td style="max-width:300px; color:${isOverridden ? '#fde047' : '#94a3b8'};">
                    ${rec.override_reason || 'Standard automated dispatch recommendation accepted.'}
                </td>
                <td style="color:${rec.projected_delay_delta_mins < 0 ? '#10b981' : '#f87171'};">
                    ${rec.projected_delay_delta_mins ? rec.projected_delay_delta_mins + 'm' : '--'}
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    // 9. Data Source Modal
    function initModals() {
        const modal = document.getElementById('sourceModal');
        document.getElementById('btnOpenSourceModal').addEventListener('click', () => {
            modal.classList.remove('hidden');
        });

        document.getElementById('btnCloseSourceModal').addEventListener('click', () => {
            modal.classList.add('hidden');
        });

        document.getElementById('btnSaveSourceConfig').addEventListener('click', async () => {
            const mode = document.querySelector('input[name="sourceMode"]:checked').value;
            const endpoint = document.getElementById('tmsUrlInput').value;
            const key = document.getElementById('tmsKeyInput').value;

            try {
                const res = await fetch('/api/datasource/switch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode, endpoint_url: endpoint, api_key: key })
                });
                const data = await res.json();
                alert(`Data source switched to: ${data.current_mode.toUpperCase()}`);
                modal.classList.add('hidden');
                await loadAllData();
            } catch (err) {
                alert('Failed to switch data source: ' + err);
            }
        });
    }

    // 10. Module 5: Line Capacity Analytics & Live 4-Aspect Signals
    async function loadCapacityAnalytics() {
        try {
            const res = await fetch('/api/analytics/capacity');
            const data = await res.json();
            
            document.getElementById('capTheoretical').textContent = data.theoretical_capacity_trains_24h;
            document.getElementById('capChartered').textContent = data.chartered_trains_count;
            document.getElementById('capSaturation').textContent = `${data.saturation_index_percent}%`;
            document.getElementById('capWhiteSpace').textContent = `${data.available_freight_white_spaces} SLOTS`;
        } catch (err) {
            console.error('Failed to load capacity analytics:', err);
        }
    }

    async function loadSignalAspects(timeSec) {
        try {
            const url = timeSec !== undefined ? `/api/signalling/aspects?time_sec=${timeSec}` : '/api/signalling/aspects';
            const res = await fetch(url);
            const signals = await res.json();
            const container = document.getElementById('signalsContainer');
            container.innerHTML = '';

            // Group signals by station
            const sttnSignals = {};
            signals.forEach(s => {
                if (!sttnSignals[s.station_code]) {
                    sttnSignals[s.station_code] = {};
                }
                sttnSignals[s.station_code][s.direction] = s;
            });

            state.stations.forEach(sttn => {
                const upSig = (sttnSignals[sttn.code] && sttnSignals[sttn.code]['UP']) || { aspect: 'GREEN', interlocking_locked: false };
                const dnSig = (sttnSignals[sttn.code] && sttnSignals[sttn.code]['DN']) || { aspect: 'GREEN', interlocking_locked: false };

                const row = document.createElement('div');
                row.className = 'station-signal-row';
                row.innerHTML = `
                    <div class="sig-sttn-info">
                        #${sttn.sequence} &bull; ${sttn.name} (${sttn.code}) ${sttn.is_junction ? '<span style="color:#38bdf8;">[JCT]</span>' : ''}
                    </div>
                    <div class="sig-aspect-pair">
                        <div class="aspect-badge">
                            <span style="color:#94a3b8; font-size:10px;">UP STARTER:</span>
                            <span class="aspect-lamp lamp-${upSig.aspect.toLowerCase().replace('_', '')}"></span>
                            <span style="color:${getAspectColor(upSig.aspect)}">${upSig.aspect}</span>
                            ${upSig.interlocking_locked ? '<span style="color:#ef4444; font-size:9px;">[LOCKED]</span>' : '<span style="color:#10b981; font-size:9px;">[ROUTE SET]</span>'}
                        </div>
                        <div class="aspect-badge">
                            <span style="color:#94a3b8; font-size:10px;">DN STARTER:</span>
                            <span class="aspect-lamp lamp-${dnSig.aspect.toLowerCase().replace('_', '')}"></span>
                            <span style="color:${getAspectColor(dnSig.aspect)}">${dnSig.aspect}</span>
                            ${dnSig.interlocking_locked ? '<span style="color:#ef4444; font-size:9px;">[LOCKED]</span>' : '<span style="color:#10b981; font-size:9px;">[ROUTE SET]</span>'}
                        </div>
                    </div>
                `;
                container.appendChild(row);
            });
        } catch (err) {
            console.error('Failed to load signals:', err);
        }
    }

    function getAspectColor(aspect) {
        if (aspect === 'RED') return '#ef4444';
        if (aspect === 'YELLOW') return '#f59e0b';
        if (aspect === 'DOUBLE_YELLOW') return '#fbbf24';
        return '#10b981';
    }
});
