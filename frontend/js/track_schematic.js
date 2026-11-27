/**
 * Dynamic Track Schematic & Block Signalling Visualizer
 * Renders real-time train movements across station lines and inter-station block sections.
 */

class TrackSchematic {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.stations = [];
        this.trains = [];
        this.simTimeSec = 21600; // 06:00:00 initial default
    }

    setData(stations, trains) {
        this.stations = stations;
        this.trains = trains;
        this.render();
    }

    setSimulationTime(sec) {
        this.simTimeSec = sec;
        this.render();
    }

    render() {
        if (!this.container || !this.stations.length) return;

        const simTimeSec = this.simTimeSec || 21600;

        // Determine which trains are currently at stations or in block sections
        const stationOccupancies = {}; // sttnCode -> [ { train, stop, isHalted, dwellRemaining } ]
        const blockOccupancies = {};   // "fromSttn-toSttn" -> [ { train, progress, speed } ]

        this.trains.forEach((train) => {
            if (!train.stops || train.stops.length < 2) return;

            for (let i = 0; i < train.stops.length; i++) {
                const s = train.stops[i];
                const arr = s.actual_arrival !== null ? s.actual_arrival : s.scheduled_arrival;
                const dep = s.actual_departure !== null ? s.actual_departure : s.scheduled_departure;

                // Currently at this station
                if (arr <= simTimeSec && simTimeSec <= dep) {
                    stationOccupancies[s.station_code] = {
                        train,
                        stop: s,
                        line: s.assigned_line || (train.direction === 'UP' ? '2' : '3'),
                        dwellRemainingSec: Math.max(0, dep - simTimeSec)
                    };
                    break;
                }

                // Currently in block section towards next stop
                if (i < train.stops.length - 1) {
                    const nextS = train.stops[i+1];
                    const nextArr = nextS.actual_arrival !== null ? nextS.actual_arrival : nextS.scheduled_arrival;

                    if (dep < simTimeSec && simTimeSec < nextArr) {
                        const runDur = Math.max(1, nextArr - dep);
                        const progress = (simTimeSec - dep) / runDur;
                        const blockKey = `${s.station_code}-${nextS.station_code}`;
                        blockOccupancies[blockKey] = {
                            train,
                            from: s.station_code,
                            to: nextS.station_code,
                            progressPercent: Math.round(progress * 100),
                            speed: train.max_speed_kmh,
                            etaSec: Math.max(0, nextArr - simTimeSec)
                        };
                        break;
                    }
                }
            }
        });

        let html = '';

        this.stations.forEach((sttn, idx) => {
            const occ = stationOccupancies[sttn.code];

            html += `
                <div class="station-track-block">
                    <div class="station-block-title">
                        <span>#${sttn.sequence} &bull; ${sttn.name} (${sttn.code}) ${sttn.is_junction ? '<span style="color:#38bdf8;">[JUNCTION]</span>' : ''}</span>
                        <span>Chainage: ${sttn.chainage_km.toFixed(2)} KM &bull; ${occ ? `<span style="color:#f59e0b; font-weight:700;">OCCUPIED BY ${occ.train.train_number}</span>` : '<span style="color:#10b981;">ALL TRACKS CLEAR</span>'}</span>
                    </div>
                    <div class="station-lines-layout">
            `;

            sttn.lines.forEach((line) => {
                const isOccupied = occ && String(occ.line) === String(line.line_number);
                const trainInfo = isOccupied ? occ.train : null;

                html += `
                    <div class="track-line-row">
                        <div class="line-badge">${line.line_type} ${line.line_number}</div>
                        <div class="line-track-visual ${isOccupied ? 'occupied' : ''}">
                            ${isOccupied ? `
                                <div class="train-tag" style="background:${trainInfo.color}; left:35%;">
                                    🚆 ${trainInfo.train_number} ${trainInfo.name} (${trainInfo.direction}) &bull; Dwell: ${Math.ceil(occ.dwellRemainingSec/60)}m left
                                </div>
                            ` : ''}
                        </div>
                        <div class="line-csr" style="width:160px; font-size:10px; color:#64748b;">
                            CSR: ${line.csr_length_m}m &bull; ${line.speed_limit_kmh} km/h ${line.has_platform ? '&bull; Platform' : ''}
                        </div>
                    </div>
                `;
            });

            html += `</div>`;

            // Draw Block Section between this station and the next
            if (idx < this.stations.length - 1) {
                const nextSttn = this.stations[idx + 1];
                const blockUpKey = `${sttn.code}-${nextSttn.code}`;
                const blockDnKey = `${nextSttn.code}-${sttn.code}`;
                const upTrain = blockOccupancies[blockUpKey];
                const dnTrain = blockOccupancies[blockDnKey];

                const dist = Math.abs(nextSttn.chainage_km - sttn.chainage_km).toFixed(2);

                html += `
                    <div class="inter-block-section" style="background:#090e17; border:1px dashed #1e293b; padding:8px 14px; margin:6px 0; border-radius:4px;">
                        <div style="display:flex; justify-content:space-between; font-size:10px; color:#64748b; margin-bottom:4px; font-family:var(--font-mono);">
                            <span>INTER-STATION DOUBLE BLOCK: <strong>${sttn.code} ⇄ ${nextSttn.code}</strong> (${dist} km)</span>
                            <span>${(upTrain || dnTrain) ? '<span style="color:#ef4444; font-weight:700;">● BLOCK OCCUPIED IN TRANSIT</span>' : '<span style="color:#10b981;">● BLOCK CLEAR (GREEN)</span>'}</span>
                        </div>

                        <!-- UP Track in Block Section -->
                        <div style="display:flex; align-items:center; gap:8px; margin:4px 0;">
                            <span style="font-size:9px; color:#38bdf8; width:50px;">UP LINE</span>
                            <div style="flex:1; height:6px; background:#1e293b; border-radius:3px; position:relative;">
                                ${upTrain ? `
                                    <div style="position:absolute; left:${upTrain.progressPercent}%; top:-18px; transform:translateX(-50%); background:#0284c7; color:#fff; padding:1px 6px; border-radius:3px; font-size:9px; font-weight:700; white-space:nowrap; box-shadow:0 0 6px #0284c7;">
                                        🚆 ${upTrain.train.train_number} ➡ ${upTrain.speed} km/h (${upTrain.progressPercent}%)
                                    </div>
                                    <div style="width:${upTrain.progressPercent}%; height:100%; background:#38bdf8; border-radius:3px;"></div>
                                ` : ''}
                            </div>
                        </div>

                        <!-- DN Track in Block Section -->
                        <div style="display:flex; align-items:center; gap:8px; margin:4px 0;">
                            <span style="font-size:9px; color:#a855f7; width:50px;">DN LINE</span>
                            <div style="flex:1; height:6px; background:#1e293b; border-radius:3px; position:relative;">
                                ${dnTrain ? `
                                    <div style="position:absolute; right:${dnTrain.progressPercent}%; top:-18px; transform:translateX(50%); background:#7c3aed; color:#fff; padding:1px 6px; border-radius:3px; font-size:9px; font-weight:700; white-space:nowrap; box-shadow:0 0 6px #7c3aed;">
                                        ⬅ 🚆 ${dnTrain.train.train_number} ${dnTrain.speed} km/h (${dnTrain.progressPercent}%)
                                    </div>
                                    <div style="position:absolute; right:0; width:${dnTrain.progressPercent}%; height:100%; background:#a855f7; border-radius:3px;"></div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }

            html += `</div>`;
        });

        this.container.innerHTML = html;
    }
}

window.TrackSchematic = TrackSchematic;
