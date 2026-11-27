# AI-Integrated Decision Support System (AIDSS)
### Train Traffic Control & Section Throughput Optimizer

> **Problem Statement ID: 25022** (Ministry of Railways, Government of India)  
> **Section**: Kottavalasa (KTV) to Palasa (PSA) Mainline Corridor (176.8 km, 22 Stations)  
> **Division**: Waltair (WAT), East Coast Railway (ECoR)

---

![AIDSS Controller Console](docs/screenshots/dashboard.png)

---

## 1. What is this project?

On busy Indian Railway tracks, fast passenger trains (like Vande Bharat and Superfast Express) share the same double-line tracks with slower, heavy goods trains (carrying coal, iron ore, and grain). 

When a train is delayed, section controllers have to quickly decide:
* Which train should go first?
* Where should a slower freight train be moved to a loop line (side track) so a faster train can overtake it?

Doing this manually is stressful and often causes cascading traffic jams across stations. 

**AIDSS** acts as an intelligent decision-support tool for train controllers:
1. It automatically detects headway conflicts and bottlenecks.
2. It suggests the best loop lines to divert and hold slower trains so priority trains pass through without delay.
3. It updates in real time as trains move across stations.
4. It lets controllers test **"What-If"** emergency scenarios (like engine breakdowns or track maintenance) before giving real orders in the field.

---

## 2. Technologies Used & Where

| Technology | Where It Is Used | Purpose |
| :--- | :--- | :--- |
| **Python 3.10+** | Entire Backend | Main programming language running the server and algorithms. |
| **FastAPI & Uvicorn** | Backend Web API | High-performance REST API that serves data to the dashboard and handles controller decisions. |
| **Google OR-Tools (CP-SAT)** | AI / Optimization Engine | Mathematical constraint programming used to calculate conflict-free train arrival/departure schedules. |
| **Pandas & OpenPyXL** | Data Ingestion | Reads and processes official railway Excel spreadsheets and goods train CSV records. |
| **Pydantic** | Domain Models | Validates data contracts for stations, loop lines, train schedules, conflicts, and decisions. |
| **HTML5 Canvas** | Frontend Marey Chart | High-speed, smooth vector rendering of the 24-hour Time-Distance string chart and simulation overlays. |
| **Vanilla JavaScript (ES6+)** | Frontend Dashboard | Lightweight and fast UI logic for the real-time playback clock, timeline scrubber, and tab navigation (zero heavy frameworks). |
| **CSS3 (Custom Dark Theme)** | User Interface | High-contrast industrial command-center styling designed for low eye-strain during 8-hour controller shifts. |
| **Playwright** | Automated Browser Testing | Headless browser testing to verify that all tabs, charts, and buttons work with zero JavaScript errors. |

---

## 3. How It Works (Step-by-Step)

```
[ Railway Data / Timetables ] 
             ↓
[ Network & Constraint Engine ]  -->  Checks loop line lengths (CSR) & safety distances
             ↓
[ OR-Tools Dispatch Optimizer ]  -->  Calculates conflict-free timings
             ↓
[ Real-Time Controller Console ] -->  Displays moving trains, Marey chart, and active loop recommendations
             ↓
[ Controller Action ]            -->  Approve loop diversion  -->  Schedule updates instantly across all screens
```

1. **Loads Corridor Infrastructure & Timetables**:
   The system loads 22 stations between Kottavalasa (KTV) and Palasa (PSA), including all 103 station lines, their physical Clear Standing Room (CSR) lengths, and train schedules.
2. **Conflict Detection & AI Recommendations**:
   The engine checks if a slower train is running ahead of a high-priority train. If a bottleneck is detected, it recommends moving the slower train onto an available loop line that is long enough to fit the rake.
3. **Interactive Timeline & Playback**:
   A scrubber bar lets controllers view any time of day (00:00 to 24:00) or play the timetable at 1x, 10x, 60x, or 180x speed to watch trains move across block sections.
4. **Dynamic Recommendation Lifecycle**:
   * **Real-time Countdown**: As a train approaches a station, the recommendation shows how many minutes are left to act.
   * **Automatic Expiration**: If the train passes the station without diversion, the recommendation automatically expires and disappears from the active list.
   * **Instant System Update**: When the controller clicks **"Approve"**, the train is immediately routed into the loop track, the following express train is given a clear mainline green signal, and live delay savings update on screen.
5. **Compound "What-If" Simulation**:
   Controllers can test 2 disruptions at the same time (e.g. *Train delayed by 35 mins at Vizianagaram* **AND** *Track block between Chipurupalle and Batuva*). The system re-calculates the timetable in seconds and shows a train-by-train comparison table and a visual ghost curve overlay on the chart.
6. **Immutable Audit Trail**:
   Every approval or manual override (with controller justification) is recorded for accountability.

---

## 4. Data Used

The system runs on the official reference data provided in the `Sample Data/` folder:

* **`RouteSttnInfo.xlsx`**: Distance (chainage in km) and sequence of all 22 stations from Kottavalasa (0.0 km) to Palasa (176.8 km).
* **`KTV-PSA-Infra.xlsx`**: Detailed station track layouts, line types (Main Line vs Loop Line), platform availability, speed limits (15 km/h turnouts vs 100–110 km/h mainlines), and Clear Standing Room (CSR) in meters.
* **`KTV_PSA_Passenger_Schedule.xlsx`**: Arrival and departure timetables for passenger trains, Mail/Express, and Vande Bharat services.
* **`WAT_GOODS_TRAIN_AUG25_01082025_27082025.csv`**: Actual movement data of freight rakes (BOXN coal, BCN grain).

> **Real Data Ready**: The backend uses an abstracted data adapter (`BaseDataSource`). Switching from sample data to live Indian Railways feeds (COA / TMS) only requires toggling the endpoint configuration without changing the optimization engine.

---

## 5. How to Run the Project

### Prerequisites
* Python 3.10 or higher installed on your computer.

### Quick Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/<your-username>/AIDSS.git
   cd AIDSS
   ```

2. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the application**:
   ```bash
   python run.py
   ```

4. **Open your browser**:
   * **Controller Console**: [http://127.0.0.1:8050](http://127.0.0.1:8050)
   * **API Documentation (Swagger)**: [http://127.0.0.1:8050/docs](http://127.0.0.1:8050/docs)

---

## 6. Automated Tests

The project includes built-in verification tests to prove that every module works properly:

1. **Run Core Backend Verification**:
   ```bash
   python tests/test_core.py
   ```
   *Runs 9 automated tests verifying station data loading, conflict detection, OR-Tools optimization, compound What-If simulation, explainability rules, signal capacity, and recommendation lifecycle.*

2. **Run Controller Approval Test**:
   ```bash
   python tests/test_api_approval.py
   ```
   *Tests the live API to ensure approving a recommendation correctly mutates the train's line to a loop track and saves delay minutes.*

3. **Run Headless Browser Test** (optional):
   ```bash
   playwright install chromium
   python tests/test_browser_e2e.py
   ```
   *Launches an automated headless browser, tests all navigation tabs, clicks buttons, runs a simulation, and confirms 0 console errors.*

---

## 7. Project Structure

```
AIDSS/
├── backend/                  # Python backend services
│   ├── adapters/             # Data loaders (Sample Excel/CSV + Standby Live TMS)
│   ├── api/                  # FastAPI web server and REST endpoints
│   ├── domain/               # Data structures (Station, Line, Train, Recommendation)
│   └── engine/               # Core algorithms (OR-Tools solver, simulator, signals)
├── frontend/                 # Web interface
│   ├── css/style.css         # Dark theme styling
│   ├── js/app.js             # Dashboard controller & API connection
│   ├── js/marey_chart.js     # Time-Distance string chart visualizer
│   ├── js/track_schematic.js # Station & block line occupancy visualizer
│   └── index.html            # Main console page
├── docs/screenshots/         # Console screenshot for README
├── Sample Data/              # Reference railway data files
├── tests/                    # Automated test scripts
├── requirements.txt          # Python dependencies
└── run.py                    # Application startup script
```
