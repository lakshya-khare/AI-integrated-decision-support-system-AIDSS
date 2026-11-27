# AI-Integrated Decision Support System (AIDSS)
### Section Throughput Optimization & Real-Time Rail Traffic Control

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Production%20REST-009688.svg)](https://fastapi.tiangolo.com)
[![OR-Tools CP-SAT](https://img.shields.io/badge/Google%20OR--Tools-CP--SAT-FF6F00.svg)](https://developers.google.com/optimization)
[![Tests Passing](https://img.shields.io/badge/Tests-9%2F9%20Passing%20(100%25)-brightgreen.svg)](tests/test_core.py)
[![Railway Zone](https://img.shields.io/badge/Indian%20Railways-ECoR%20%2F%20Waltair-003366.svg)](#operational-context)

> **Industry Context**: Ministry of Railways (Government of India) | Problem Statement ID: 25022  
> **Operational Territory**: Kottavalasa (KTV) — Palasa (PSA) Mainline Corridor, Waltair (WAT) Division, East Coast Railway (ECoR)  
> **Scale**: 176.83 km | 22 Stations | 103 Track Lines | Double-Line Automatic Block Signalling (ABS) | 229 Trains/Day

---

![AIDSS Rail Traffic Control Console](docs/screenshots/dashboard.png)

---

## 1. Project Overview & Interview Elevator Pitch

**AIDSS** is an enterprise-grade, mission-critical Decision Support System designed for Railway Section Controllers (SCOR) and Chief Traffic Controllers (CPCR). It automates real-time conflict detection, disjunctive schedule optimization, and dynamic loop line precedence dispatching across high-density mixed-traffic corridors.

### The Engineering Challenge
In heavy mixed corridors, high-speed passenger services (130 km/h Vande Bharat, Rajdhani, Superfast Express) share physical tracks with heavy bulk freight (50–75 km/h loaded BOXN coal and BCN grain rakes). When unplanned delays occur (e.g., locomotive snags, caution orders, maintenance blocks), manual controller decisions often cause cascading headway delays across multiple block sections.

### The Solution
AIDSS solves the **Disjunctive Section Traffic Dispatching Problem (STDP)** using a hybrid optimization approach: **Google OR-Tools CP-SAT** for exact mathematical constraint programming combined with a **sub-25ms fast priority-dispatch heuristic** for live reactive control. It provides Explainable AI (XAI) dispatch advisories, automates schedule mutations upon controller approval, and simulates multi-condition What-If disruptions before field orders are transmitted.

---

## 2. Where & How It Is Used

* **Deployment Target**: Divisional Rail Traffic Control Offices (Control Office Application / TMS Consoles).
* **Target Users**: Section Controllers (SCOR), Chief Train Controllers (CPCR), and Traffic Planning Officers.
* **Operational Flow**:
  1. **Ingestion & Digital Twin**: The system ingests infrastructure geometry (CSR lengths, gradients, speed limits) and train timetables via an abstracted data adapter.
  2. **Automated Conflict Detection**: The network engine scans running paths to identify headway infractions, platform overlaps, and precedence bottlenecks.
  3. **AI Dispatch Advisory**: When a faster train approaches a slower train, AIDSS calculates the optimal loop line diversion, verifying physical Clear Standing Room ($L_{\text{train}} \le \text{CSR}_{\text{loop}}$) and delay savings.
  4. **Controller Action & Schedule Mutation**: When approved by the controller, AIDSS mutates the active timetable in memory, adjusts downstream arrival/departure timings, clears the mainline aspect for the following train, and logs the action to an immutable audit record.
  5. **Compound Counterfactual Simulation**: Controllers can run multi-condition What-If scenarios (e.g. Loco failure + Block section maintenance) to preview comparative schedule deltas before executing field orders.

---

## 3. Technology Stack & Architectural Decisions

| Layer | Technologies | Justification & Architecture Rationale |
| :--- | :--- | :--- |
| **Backend & API** | **Python 3.10+**, **FastAPI**, **Uvicorn** | Asynchronous, non-blocking REST API with strict Pydantic v2 data validation schemas; sub-millisecond response times for real-time telemetry. |
| **Optimization Engine** | **Google OR-Tools (CP-SAT)** | Models STDP using interval variables, disjunctive constraints, and priority weights; finds optimal, conflict-free schedules over a 24–48 hour horizon. |
| **Reactive Solver** | **Custom Priority Dispatch Heuristic** | Fallback algorithm executing in $< 25$ ms. Solves headway conflicts sequentially based on train priority classes (P1 to P6) and inserts dynamic loop holds. |
| **Analytics Engine** | **Scott’s Capacity Math**, **4-Aspect Signal Simulator** | Implements the authentic Indian Railways Scott's Line Capacity formula ($C = \frac{1440}{T+t} \times E$) and simulates 44 colour-light signals dynamically. |
| **Frontend UI** | **Vanilla ES6+ JavaScript**, **HTML5 Canvas 2D**, **CSS3** | Built without heavy third-party UI framework bloat. The Marey chart renders hundreds of train trajectories at **60 FPS** on HTML5 Canvas with custom DPR scaling. |
| **Integration Pattern**| **Adapter Pattern (`BaseDataSource`)** | Decouples data ingestion. Toggles seamlessly between offline digital twin cache (`Sample Data/`) and live railway TMS/COA WebSocket/REST APIs. |
| **Testing & QA** | **Pytest / Assert-based tests**, **Playwright** | 9 end-to-end algorithmic verification tests + automated headless browser verification ensuring zero JavaScript errors and DOM stability. |

---

## 4. Key Architectural & Algorithmic Highlights

### A. Operations Research Optimization (CP-SAT Model)
The disjunctive dispatch problem is formulated as:
$$\min \sum_{t \in \mathcal{T}} \sum_{s \in \mathcal{S}_t} w_t \cdot \max(0, \text{arr}_{t,s} - \text{sched\_arr}_{t,s})$$
* **Headway Constraints**: Enforces minimum time headway separation between successive trains on the same block section ($h \ge 300\text{ s}$).
* **Precedence Disjunction**: For train pairs $(t_1, t_2)$ on common track segments, boolean choice variables enforce either $t_1 \prec t_2$ or $t_2 \prec t_1$ based on priority weights ($w_{\text{Vande Bharat}} = 100$, $w_{\text{Superfast}} = 60$, $w_{\text{Freight}} = 20$).
* **Physical Loop Feasibility**: Recommends loop holds only if train length with safety margin satisfies Clear Standing Room:
$$\text{Length}_{\text{train}} \times 1.10 \le \text{CSR}_{\text{loop}}$$

### B. Dynamic Recommendation Lifecycle
* **Automatic Section Expiration**: As trains pass block sections, pending recommendations are automatically marked `EXPIRED` once the train crosses the station approach.
* **Instant Timetable Mutation**: Approving a recommendation reallocates the train to the loop track (`Line 4`), extends dwell time by the hold duration, shifts downstream stops, and eliminates headway delay for overtaking services.
* **Live System Reflection**: The live Marey diagram, dynamic track schematic, KPI cards, and signal aspects update instantaneously upon approval.

### C. Multi-Condition Compound What-If Engine
* Supports testing **two compound disruptions simultaneously** (e.g. *Condition 1: Train Delay at VZM* + *Condition 2: Track Block on CPP-BTVA*).
* Produces side-by-side KPI comparison and a **Train-by-Train Schedule Delta Table** displaying baseline arrival, scenario arrival, and delay shift per service.
* Features a **Ghost Trajectory Overlay**: Toggles counterfactual dashed paths over baseline solid strings directly on the Marey Chart.

### D. Explainable AI (XAI)
Every recommendation includes contextual railway domain reasoning:
* Technical justification citing exact CSR length in meters.
* Quantified delay savings on following traffic.
* Counterfactual risk analysis if overridden by controller.
* Regulatory compliance: General & Subsidiary Rules (G&SR Rule 4.23 - Precedence of Passenger over Goods), Operating Manual Section 14, and Signal Engineering Manual (SEM).

---

## 5. Data Pipeline & Digital Twin Ingestion

The digital twin models the actual Waltair Division KTV–PSA corridor using official railway operational data:

```
Sample Data/
├── RouteSttnInfo.xlsx                     # Station sequences, chainage (KM), inter-station distances
├── KTV-PSA-Infra.xlsx                     # Station lines (103 lines), loop CSR lengths, speed limits
├── KTV_PSA_Passenger_Schedule.xlsx       # Timetables for 229 passenger services (VB, SF, MEX, PASS)
└── WAT_GOODS_TRAIN_AUG25_...csv           # Operating freight rakes (BCN, BOXN coal/ore trains)
```

* **Physical Direction Normalization**: Ingested Southbound (DN) trains are validated against physical arrival progression ($PSA \rightarrow KTV$), resolving schedule direction inversions.
* **Monotonic Timetable Enforcement**: Deduplicates overlapping operational proposals and strictly enforces non-decreasing dwell-arrival sequences.
* **Microsecond In-Memory Cache**: Parsed topology is serialized to JSON cache for sub-millisecond cold starts.

---

## 6. Testing Strategy & Verification

The project includes an assert-based self-checking test suite:

```bash
# 1. Run Core Verification Suite (9 tests covering OR engine, data, and signalling)
python tests/test_core.py

# 2. Run E2E Decision & Timetable Mutation Test
python tests/test_api_approval.py

# 3. Run Headless Playwright Browser Test (verifies UI rendering and zero console errors)
python tests/test_browser_e2e.py
```

### Verified Test Matrix:
* **Test 1**: Data Adapter ingestion (22 stations, 176.83 km, 229 trains loaded).
* **Test 2**: Network Graph & Loop Feasibility check ($L \le CSR$).
* **Test 3**: RailwayScheduleOptimizer (OR CP-SAT + fast priority dispatch).
* **Test 4**: Counterfactual What-If simulation engine.
* **Test 5**: Operational Explainability Engine & G&SR rule generation.
* **Test 6**: Immutable Audit Manager & Standby Live TMS Adapter health checks.
* **Test 7**: Scott's Line Capacity calculation ($C = 131\text{ trains/24h}$) & 44 colour-light signals.
* **Test 8**: Multi-condition compound What-If simulation with train-by-train diff list.
* **Test 9**: Dynamic recommendation lifecycle & loop line timetable mutation.

---

## 7. Quick Start & Execution

### Prerequisites
* Python 3.10+
* Google Chrome, Microsoft Edge, or any modern web browser

### Setup & Run
```bash
# Clone the repository
git clone https://github.com/<your-username>/AIDSS.git
cd AIDSS

# Install dependencies
pip install -r requirements.txt

# Start the application server
python run.py
```

Open your browser:
* **Railway Controller Console**: [http://127.0.0.1:8050](http://127.0.0.1:8050)
* **Interactive OpenAPI/Swagger Documentation**: [http://127.0.0.1:8050/docs](http://127.0.0.1:8050/docs)

---

## 8. Key API Endpoints

| Endpoint | Method | Function |
| :--- | :---: | :--- |
| `/api/status` | `GET` | System health, adapter state (`sample` / `live_tms`), division metadata |
| `/api/infrastructure` | `GET` | 22 stations, CSR lengths, speed limits, block sections |
| `/api/trains/active` | `GET` | Active train schedules across corridor |
| `/api/trains/positions` | `GET` | Real-time train positions & speeds at given operational second |
| `/api/recommendations` | `GET` | Dynamic active recommendations (supports `?time_sec=` filtering) |
| `/api/decisions/action` | `POST` | Approves or overrides recommendations; mutates active timetable |
| `/api/simulate` | `POST` | Executes compound What-If simulation across 1 or 2+ disruptions |
| `/api/signalling/aspects`| `GET` | Live 4-aspect signal states for UP & DN lines across all stations |
| `/api/analytics/capacity`| `GET` | Scott's Line Capacity, critical bottleneck section, saturation index |
| `/api/audit` | `GET` | Immutable audit trail records with controller override justifications |
| `/api/datasource/switch` | `POST` | Switches between `sample` digital twin and `live_tms` gateway |

---

## 9. Author & License

Developed for **Problem Statement 25022 (Ministry of Railways, Government of India)**.  
Built with Python, FastAPI, Google OR-Tools, and HTML5 Canvas.
