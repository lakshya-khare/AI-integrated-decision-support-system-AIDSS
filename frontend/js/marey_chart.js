/**
 * High-Performance Interactive Time-Distance String Chart (Marey Diagram)
 * Re-engineered for Section Controllers: Crystal-clear trajectories, directional filtering,
 * focus isolation, and zero-collision labeling.
 */

class MareyChart {
    constructor(canvasId, containerId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.container = document.getElementById(containerId);
        this.tooltip = document.getElementById('chartTooltip');

        this.stations = [];
        this.trains = [];
        
        // Active Filters
        this.filterDirection = 'ALL';   // 'ALL', 'UP', 'DN'
        this.filterPriority = 'ALL';    // 'ALL', 'PREMIUM', 'EXPRESS', 'FREIGHT'
        this.focusedTrainNo = null;

        // Viewport bounds (in seconds from 00:00:00)
        this.startTimeSec = 0;
        this.endTimeSec = 86400; // 24 Hours default
        this.simTimeSec = 21600; // 06:00:00 initial default
        
        this.paddingLeft = 130;
        this.paddingRight = 30;
        this.paddingTop = 35;
        this.paddingBottom = 35;

        this.hoveredTrain = null;
        this.cursorX = null;
        this.cursorY = null;
        this.simulatedTrains = null;

        this.resizeCanvas();
        this.initEvents();
    }

    setData(stations, trains) {
        this.stations = stations;
        this.trains = trains;
        this.resizeCanvas();
        this.render();
    }

    setTimeWindow(startHour, endHour) {
        this.startTimeSec = startHour * 3600;
        this.endTimeSec = endHour * 3600;
        this.render();
    }

    setSimulationTime(sec) {
        this.simTimeSec = sec;
        this.render();
    }

    setDirectionFilter(dir) {
        this.filterDirection = dir; // 'ALL', 'UP', 'DN'
        this.render();
    }

    setPriorityFilter(prio) {
        this.filterPriority = prio; // 'ALL', 'PREMIUM', 'EXPRESS', 'FREIGHT'
        this.render();
    }

    focusTrain(trainNo) {
        this.focusedTrainNo = trainNo ? String(trainNo).trim() : null;
        this.render();
    }

    setSimulatedTrains(trains) {
        this.simulatedTrains = trains;
        this.render();
    }

    clearSimulatedTrains() {
        this.simulatedTrains = null;
        this.render();
    }

    initEvents() {
        window.addEventListener('resize', () => this.resizeCanvas());

        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            this.cursorX = e.clientX - rect.left;
            this.cursorY = e.clientY - rect.top;
            this.handleMouseMove(this.cursorX, this.cursorY, e.clientX, e.clientY);
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.tooltip.style.display = 'none';
            this.hoveredTrain = null;
            this.cursorX = null;
            this.cursorY = null;
            this.render();
        });

        this.canvas.addEventListener('click', () => {
            if (this.hoveredTrain) {
                if (this.focusedTrainNo === this.hoveredTrain.train_number) {
                    this.focusedTrainNo = null; // Toggle off
                } else {
                    this.focusedTrainNo = this.hoveredTrain.train_number;
                }
                const trainSelect = document.getElementById('searchTrainInput');
                if (trainSelect) trainSelect.value = this.focusedTrainNo || '';
                this.render();
            } else {
                this.focusedTrainNo = null;
                const trainSelect = document.getElementById('searchTrainInput');
                if (trainSelect) trainSelect.value = '';
                this.render();
            }
        });
    }

    resizeCanvas() {
        if (!this.container) return;
        const rect = this.container.getBoundingClientRect();
        const width = rect.width || this.container.clientWidth || 1200;
        const height = rect.height || this.container.clientHeight || 650;
        const dpr = window.devicePixelRatio || 1;
        
        this.canvas.width = Math.floor(width * dpr);
        this.canvas.height = Math.floor(height * dpr);
        this.canvas.style.width = `${width}px`;
        this.canvas.style.height = `${height}px`;
        
        this.ctx.resetTransform();
        this.ctx.scale(dpr, dpr);
        this.render();
    }

    render() {
        if (!this.container) return;
        const rect = this.container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        const targetWidth = Math.floor((rect.width || 1200) * dpr);
        const targetHeight = Math.floor((rect.height || 650) * dpr);

        if (this.canvas.width !== targetWidth || this.canvas.height !== targetHeight) {
            this.canvas.width = targetWidth;
            this.canvas.height = targetHeight;
            this.canvas.style.width = `${rect.width || 1200}px`;
            this.canvas.style.height = `${rect.height || 650}px`;
            this.ctx.resetTransform();
            this.ctx.scale(dpr, dpr);
        }

        const width = this.canvas.width / dpr;
        const height = this.canvas.height / dpr;

        if (width <= 0 || height <= 0 || this.stations.length === 0) {
            return;
        }

        this.ctx.clearRect(0, 0, width, height);

        // Base canvas background
        this.ctx.fillStyle = '#080c14';
        this.ctx.fillRect(0, 0, width, height);

        const plotWidth = width - this.paddingLeft - this.paddingRight;
        const plotHeight = height - this.paddingTop - this.paddingBottom;

        // 1. Alternating Station Row Bands & Station Grid
        this.drawStationGrid(plotWidth, plotHeight, width);

        // 2. Alternating Hour Columns & Time Grid
        this.drawTimeGrid(plotWidth, plotHeight, width, height);

        // 3. Train Trajectories (Background unfocused + Foreground focused)
        this.drawTrainTrajectories(plotWidth, plotHeight);

        // 4. Crosshair and Cursor Readout
        this.drawCrosshair(plotWidth, plotHeight, width, height);

        // 5. Current Simulated Shift Marker
        this.drawCurrentTimeMarker(plotWidth, plotHeight);
    }

    drawStationGrid(plotWidth, plotHeight, width) {
        if (!this.stations.length) return;
        const maxDist = this.stations[this.stations.length - 1].chainage_km;

        this.stations.forEach((sttn, i) => {
            const y = this.paddingTop + (sttn.chainage_km / maxDist) * plotHeight;
            const nextY = i < this.stations.length - 1 
                ? this.paddingTop + (this.stations[i+1].chainage_km / maxDist) * plotHeight 
                : y + 20;

            // Zebra banding between stations
            if (i % 2 === 1) {
                this.ctx.fillStyle = 'rgba(255, 255, 255, 0.015)';
                this.ctx.fillRect(this.paddingLeft, y, plotWidth, nextY - y);
            }

            // Major Junction Station Band Highlight
            if (sttn.is_junction) {
                this.ctx.fillStyle = 'rgba(2, 132, 199, 0.04)';
                this.ctx.fillRect(this.paddingLeft, y - 6, plotWidth, 12);
            }

            // Horizontal Station Line
            this.ctx.beginPath();
            this.ctx.strokeStyle = sttn.is_junction ? '#334155' : '#172033';
            this.ctx.lineWidth = sttn.is_junction ? 1.5 : 1;
            this.ctx.moveTo(this.paddingLeft, y);
            this.ctx.lineTo(width - this.paddingRight, y);
            this.ctx.stroke();

            // Station Label (Left Y-Axis)
            this.ctx.textAlign = 'right';
            this.ctx.font = sttn.is_junction ? 'bold 11px JetBrains Mono' : '10px JetBrains Mono';
            this.ctx.fillStyle = sttn.is_junction ? '#38bdf8' : '#94a3b8';
            this.ctx.fillText(`${sttn.code}`, this.paddingLeft - 42, y + 3);

            // Chainage KM in muted text
            this.ctx.font = '9px JetBrains Mono';
            this.ctx.fillStyle = '#64748b';
            this.ctx.fillText(`${sttn.chainage_km.toFixed(1)}k`, this.paddingLeft - 8, y + 3);
        });
    }

    drawTimeGrid(plotWidth, plotHeight, width, height) {
        const totalDuration = this.endTimeSec - this.startTimeSec;
        const stepSec = totalDuration <= 28800 ? 1800 : 3600; // 30 mins or 1 hour

        for (let t = this.startTimeSec; t <= this.endTimeSec; t += stepSec) {
            const x = this.paddingLeft + ((t - this.startTimeSec) / totalDuration) * plotWidth;

            // Hourly Column alternate shading
            const hourIdx = Math.floor(t / 3600);
            if (hourIdx % 2 === 0) {
                const nextX = this.paddingLeft + (((t + stepSec) - this.startTimeSec) / totalDuration) * plotWidth;
                this.ctx.fillStyle = 'rgba(255, 255, 255, 0.008)';
                this.ctx.fillRect(x, this.paddingTop, Math.min(nextX - x, width - this.paddingRight - x), plotHeight);
            }

            // Vertical Grid Line
            this.ctx.beginPath();
            this.ctx.strokeStyle = '#1e293b';
            this.ctx.lineWidth = 1;
            this.ctx.moveTo(x, this.paddingTop);
            this.ctx.lineTo(x, height - this.paddingBottom);
            this.ctx.stroke();

            // Time Label (Top and Bottom)
            const hours = Math.floor(t / 3600) % 24;
            const mins = Math.floor((t % 3600) / 60);
            const timeStr = `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`;

            this.ctx.font = '10px JetBrains Mono, monospace';
            this.ctx.textAlign = 'center';
            this.ctx.fillStyle = '#94a3b8';
            this.ctx.fillText(timeStr, x, this.paddingTop - 10);
            this.ctx.fillText(timeStr, x, height - this.paddingBottom + 16);
        }
    }

    drawTrainTrajectories(plotWidth, plotHeight) {
        if (!this.stations.length || !this.trains.length) return;
        const maxDist = this.stations[this.stations.length - 1].chainage_km;
        const totalDuration = this.endTimeSec - this.startTimeSec;
        const sttnDistMap = {};
        this.stations.forEach(s => sttnDistMap[s.code] = s.chainage_km);

        // Filter trains based on controls
        const filteredTrains = this.trains.filter((t) => {
            if (this.filterDirection !== 'ALL' && t.direction !== this.filterDirection) return false;
            if (this.filterPriority === 'PREMIUM' && t.priority !== 'P1_PREMIUM' && t.priority !== 'P2_SUPERFAST') return false;
            if (this.filterPriority === 'EXPRESS' && t.priority !== 'P3_EXPRESS') return false;
            if (this.filterPriority === 'FREIGHT' && t.priority !== 'P4_FREIGHT' && t.priority !== 'P5_EMPTY') return false;
            return true;
        });

        // Split into background (unfocused) and foreground (focused/hovered)
        const hasFocus = !!this.focusedTrainNo;

        filteredTrains.forEach((train) => {
            if (!train.stops || train.stops.length < 2) return;

            const isFocused = this.focusedTrainNo === train.train_number;
            const isHovered = this.hoveredTrain && this.hoveredTrain.train_number === train.train_number;

            // Visibility / Opacity
            let alpha = 0.85;
            let lineWidth = 1.6;
            let strokeColor = train.color;

            if (hasFocus) {
                if (isFocused) {
                    alpha = 1.0;
                    lineWidth = 3.5;
                    strokeColor = '#fbbf24'; // Glowing Gold
                } else {
                    alpha = 0.15; // Dim others
                    lineWidth = 1.0;
                }
            } else if (isHovered) {
                alpha = 1.0;
                lineWidth = 3.0;
                strokeColor = '#ffffff';
            }

            // Draw Trajectory Segments
            this.ctx.save();
            this.ctx.globalAlpha = alpha;
            this.ctx.strokeStyle = strokeColor;
            this.ctx.lineWidth = lineWidth;
            if (isFocused || isHovered) {
                this.ctx.shadowColor = strokeColor;
                this.ctx.shadowBlur = 8;
            }

            this.ctx.beginPath();
            let started = false;

            train.stops.forEach((stop) => {
                const dist = sttnDistMap[stop.station_code];
                if (dist === undefined) return;

                const y = this.paddingTop + (dist / maxDist) * plotHeight;
                const arrSec = stop.actual_arrival !== null ? stop.actual_arrival : stop.scheduled_arrival;
                const depSec = stop.actual_departure !== null ? stop.actual_departure : stop.scheduled_departure;

                const xArr = this.paddingLeft + ((arrSec - this.startTimeSec) / totalDuration) * plotWidth;
                const xDep = this.paddingLeft + ((depSec - this.startTimeSec) / totalDuration) * plotWidth;

                if (!started) {
                    this.ctx.moveTo(xArr, y);
                    started = true;
                } else {
                    this.ctx.lineTo(xArr, y);
                }

                // If loop hold/dwell occurred
                if (xDep !== xArr) {
                    this.ctx.lineTo(xDep, y);
                }
            });
            this.ctx.stroke();
            this.ctx.restore();

            // Draw Clean Label at Midpoint (ONLY when focused, hovered, or standalone)
            if (isFocused || isHovered) {
                const midIdx = Math.floor(train.stops.length / 2);
                const midStop = train.stops[midIdx];
                const dist = sttnDistMap[midStop.station_code];
                if (dist !== undefined) {
                    const y = this.paddingTop + (dist / maxDist) * plotHeight;
                    const arrSec = midStop.actual_arrival || midStop.scheduled_arrival;
                    const x = this.paddingLeft + ((arrSec - this.startTimeSec) / totalDuration) * plotWidth;

                    this.ctx.save();
                    this.ctx.font = 'bold 11px JetBrains Mono';
                    const labelText = `${train.train_number} ${train.name} (${train.direction})`;
                    const textWidth = this.ctx.measureText(labelText).width;

                    // Tag background box
                    this.ctx.fillStyle = '#0f172a';
                    this.ctx.fillRect(x - textWidth/2 - 6, y - 18, textWidth + 12, 18);
                    this.ctx.strokeStyle = strokeColor;
                    this.ctx.lineWidth = 1;
                    this.ctx.strokeRect(x - textWidth/2 - 6, y - 18, textWidth + 12, 18);

                    // Text
                    this.ctx.fillStyle = '#ffffff';
                    this.ctx.textAlign = 'center';
                    this.ctx.fillText(labelText, x, y - 5);
                    this.ctx.restore();
                }
            }
        });

        // 3b. If Simulated Trains Overlay is active, render counterfactual ghost paths (dashed lines)
        if (this.simulatedTrains && this.simulatedTrains.length) {
            this.ctx.save();
            this.ctx.setLineDash([5, 4]);

            this.simulatedTrains.forEach((simTrain) => {
                if (!simTrain.stops || simTrain.stops.length < 2) return;
                if (this.filterDirection !== 'ALL' && simTrain.direction !== this.filterDirection) return;

                this.ctx.strokeStyle = '#f59e0b'; // Amber ghost
                this.ctx.lineWidth = 2.0;
                this.ctx.globalAlpha = 0.85;

                this.ctx.beginPath();
                let started = false;

                simTrain.stops.forEach((stop) => {
                    const dist = sttnDistMap[stop.station_code];
                    if (dist === undefined) return;

                    const y = this.paddingTop + (dist / maxDist) * plotHeight;
                    const arrSec = stop.actual_arrival !== null ? stop.actual_arrival : stop.scheduled_arrival;
                    const depSec = stop.actual_departure !== null ? stop.actual_departure : stop.scheduled_departure;

                    const xArr = this.paddingLeft + ((arrSec - this.startTimeSec) / totalDuration) * plotWidth;
                    const xDep = this.paddingLeft + ((depSec - this.startTimeSec) / totalDuration) * plotWidth;

                    if (!started) {
                        this.ctx.moveTo(xArr, y);
                        started = true;
                    } else {
                        this.ctx.lineTo(xArr, y);
                    }
                    if (xDep !== xArr) {
                        this.ctx.lineTo(xDep, y);
                    }
                });
                this.ctx.stroke();
            });

            this.ctx.restore();

            // Overlay HUD Banner (Top-Right with crisp badge)
            this.ctx.save();
            const width = plotWidth + this.paddingLeft + this.paddingRight;
            const bannerText = '⚡ WHAT-IF GHOST OVERLAY (DASHED AMBER) VS BASELINE (SOLID)';
            this.ctx.font = 'bold 10px JetBrains Mono';
            const bWidth = this.ctx.measureText(bannerText).width;
            const bX = width - this.paddingRight - bWidth - 12;
            const bY = this.paddingTop + 14;
            this.ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
            this.ctx.fillRect(bX - 8, bY - 12, bWidth + 16, 18);
            this.ctx.strokeStyle = '#f59e0b';
            this.ctx.lineWidth = 1;
            this.ctx.strokeRect(bX - 8, bY - 12, bWidth + 16, 18);
            this.ctx.fillStyle = '#f59e0b';
            this.ctx.fillText(bannerText, bX, bY);
            this.ctx.restore();
        }
    }

    drawCrosshair(plotWidth, plotHeight, width, height) {
        if (!this.cursorX || !this.cursorY) return;
        if (this.cursorX < this.paddingLeft || this.cursorX > width - this.paddingRight) return;
        if (this.cursorY < this.paddingTop || this.cursorY > height - this.paddingBottom) return;

        this.ctx.save();
        this.ctx.strokeStyle = 'rgba(56, 189, 248, 0.3)';
        this.ctx.setLineDash([3, 3]);
        this.ctx.lineWidth = 1;

        // Vertical line
        this.ctx.beginPath();
        this.ctx.moveTo(this.cursorX, this.paddingTop);
        this.ctx.lineTo(this.cursorX, height - this.paddingBottom);
        this.ctx.stroke();

        // Horizontal line
        this.ctx.beginPath();
        this.ctx.moveTo(this.paddingLeft, this.cursorY);
        this.ctx.lineTo(width - this.paddingRight, this.cursorY);
        this.ctx.stroke();

        // Cursor Time Badge
        const totalDuration = this.endTimeSec - this.startTimeSec;
        const curSec = this.startTimeSec + ((this.cursorX - this.paddingLeft) / plotWidth) * totalDuration;
        const hrs = Math.floor(curSec / 3600) % 24;
        const mins = Math.floor((curSec % 3600) / 60);
        const timeBadge = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')} IST`;

        this.ctx.fillStyle = '#0284c7';
        this.ctx.fillRect(this.cursorX - 35, height - this.paddingBottom + 4, 70, 16);
        this.ctx.fillStyle = '#fff';
        this.ctx.font = 'bold 9px JetBrains Mono';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(timeBadge, this.cursorX, height - this.paddingBottom + 16);

        this.ctx.restore();
    }

    drawCurrentTimeMarker(plotWidth, plotHeight) {
        const simTimeSec = this.simTimeSec || 21600;
        const totalDuration = this.endTimeSec - this.startTimeSec;
        const maxDist = this.stations.length ? this.stations[this.stations.length - 1].chainage_km : 176.83;
        const sttnDistMap = {};
        this.stations.forEach(s => sttnDistMap[s.code] = s.chainage_km);

        if (simTimeSec >= this.startTimeSec && simTimeSec <= this.endTimeSec) {
            const x = this.paddingLeft + ((simTimeSec - this.startTimeSec) / totalDuration) * plotWidth;

            this.ctx.save();
            this.ctx.strokeStyle = '#ef4444';
            this.ctx.lineWidth = 2;
            this.ctx.beginPath();
            this.ctx.moveTo(x, this.paddingTop);
            this.ctx.lineTo(x, this.canvas.height - this.paddingBottom);
            this.ctx.stroke();

            // Time Label Badge
            const hrs = Math.floor(simTimeSec / 3600) % 24;
            const mins = Math.floor((simTimeSec % 3600) / 60);
            const timeStr = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')} IST`;

            this.ctx.fillStyle = '#ef4444';
            this.ctx.fillRect(x - 36, this.paddingTop - 18, 72, 16);
            this.ctx.fillStyle = '#fff';
            this.ctx.font = 'bold 9px JetBrains Mono';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(timeStr, x, this.paddingTop - 6);

            // Interpolate and Draw Real-Time Train Markers on the Line
            this.trains.forEach((train) => {
                if (!train.stops || train.stops.length < 2) return;
                const isFocused = this.focusedTrainNo === train.train_number;

                for (let i = 0; i < train.stops.length - 1; i++) {
                    const s1 = train.stops[i];
                    const s2 = train.stops[i+1];
                    const d1 = sttnDistMap[s1.station_code];
                    const d2 = sttnDistMap[s2.station_code];
                    if (d1 === undefined || d2 === undefined) continue;

                    const tDep = s1.actual_departure || s1.scheduled_departure;
                    const tArr = s2.actual_arrival || s2.scheduled_arrival;

                    if (tDep <= simTimeSec && simTimeSec <= tArr) {
                        const runDur = maxDist > 0 ? Math.max(1, tArr - tDep) : 1;
                        const progress = (simTimeSec - tDep) / runDur;
                        const currDist = d1 + progress * (d2 - d1);
                        const y = this.paddingTop + (currDist / maxDist) * plotHeight;

                        // Pulsing Active Train Dot
                        this.ctx.beginPath();
                        this.ctx.arc(x, y, isFocused ? 7 : 5, 0, Math.PI * 2);
                        this.ctx.fillStyle = isFocused ? '#fbbf24' : train.color;
                        this.ctx.fill();
                        this.ctx.strokeStyle = '#ffffff';
                        this.ctx.lineWidth = 1.5;
                        this.ctx.stroke();

                        // Train number tag beside the moving dot
                        this.ctx.fillStyle = '#ffffff';
                        this.ctx.font = 'bold 9px JetBrains Mono';
                        this.ctx.textAlign = train.direction === 'UP' ? 'left' : 'right';
                        this.ctx.fillText(train.train_number, x + (train.direction === 'UP' ? 8 : -8), y + 3);
                        break;
                    }
                }
            });

            this.ctx.restore();
        }
    }

    handleMouseMove(mouseX, mouseY, clientX, clientY) {
        if (!this.stations.length || !this.trains.length) return;

        const width = this.canvas.width / (window.devicePixelRatio || 1);
        const height = this.canvas.height / (window.devicePixelRatio || 1);
        const plotWidth = width - this.paddingLeft - this.paddingRight;
        const plotHeight = height - this.paddingTop - this.paddingBottom;
        const maxDist = this.stations[this.stations.length - 1].chainage_km;
        const totalDuration = this.endTimeSec - this.startTimeSec;
        const sttnDistMap = {};
        this.stations.forEach(s => sttnDistMap[s.code] = s.chainage_km);

        let closestTrain = null;
        let closestDist = 15; // Pixel threshold
        let matchInfo = null;

        for (const train of this.trains) {
            if (this.filterDirection !== 'ALL' && train.direction !== this.filterDirection) continue;

            for (let i = 0; i < train.stops.length; i++) {
                const stop = train.stops[i];
                const dist = sttnDistMap[stop.station_code];
                if (dist === undefined) continue;

                const y = this.paddingTop + (dist / maxDist) * plotHeight;
                const arrSec = stop.actual_arrival !== null ? stop.actual_arrival : stop.scheduled_arrival;
                const x = this.paddingLeft + ((arrSec - this.startTimeSec) / totalDuration) * plotWidth;

                const d = Math.hypot(mouseX - x, mouseY - y);
                if (d < closestDist) {
                    closestDist = d;
                    closestTrain = train;
                    matchInfo = { train, stop, x, y };
                }
            }
        }

        if (matchInfo) {
            this.hoveredTrain = matchInfo.train;
            const t = matchInfo.train;
            const s = matchInfo.stop;
            const arrH = String(Math.floor((s.actual_arrival % 86400) / 3600)).padStart(2, '0');
            const arrM = String(Math.floor((s.actual_arrival % 3600) / 60)).padStart(2, '0');
            const schedH = String(Math.floor((s.scheduled_arrival % 86400) / 3600)).padStart(2, '0');
            const schedM = String(Math.floor((s.scheduled_arrival % 3600) / 60)).padStart(2, '0');

            this.tooltip.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:4px; margin-bottom:6px;">
                    <strong style="color:${t.color}; font-size:12px;">${t.train_number} ${t.name}</strong>
                    <span style="background:${t.direction === 'UP' ? '#0284c7' : '#7c3aed'}; color:#fff; font-size:9px; padding:1px 5px; border-radius:3px;">${t.direction}</span>
                </div>
                <div style="font-size:11px; line-height:1.5;">
                    <div><strong>Station:</strong> ${s.station_code}</div>
                    <div><strong>Optimized Time:</strong> ${arrH}:${arrM}</div>
                    <div><strong>Scheduled (WTT):</strong> ${schedH}:${schedM}</div>
                    <div><strong>Delay Variance:</strong> <span style="color:${s.delay_arrival_mins > 5 ? '#f87171' : '#10b981'}; font-weight:700;">${s.delay_arrival_mins > 0 ? '+' : ''}${s.delay_arrival_mins} mins</span></div>
                    <div><strong>Assigned Track:</strong> Line ${s.assigned_line || '2 (Main)'}</div>
                </div>
                <div style="margin-top:6px; font-size:9px; color:#94a3b8; text-align:center;">Click to isolate & highlight train path</div>
            `;
            this.tooltip.style.left = `${clientX + 14}px`;
            this.tooltip.style.top = `${clientY - 20}px`;
            this.tooltip.style.display = 'block';
        } else {
            this.hoveredTrain = null;
            this.tooltip.style.display = 'none';
        }

        this.render();
    }
}

window.MareyChart = MareyChart;
