import urllib.request
import json

recs_url = 'http://127.0.0.1:8050/api/recommendations?time_sec=21600'
recs = json.loads(urllib.request.urlopen(recs_url).read().decode('utf-8'))
assert len(recs) > 0, "No recommendations returned"
rec_to_approve = recs[0]
rec_id = rec_to_approve['recommendation_id']
t_no = rec_to_approve['train_number']
sttn = rec_to_approve['station_code']
print(f"Approving rec {rec_id} for train {t_no} at {sttn}...")

# Submit decision
dec_url = 'http://127.0.0.1:8050/api/decisions/action'
payload = json.dumps({
    'recommendation_id': rec_id,
    'action_taken': 'APPROVED',
    'controller_id': 'WAT-SCOR-01'
}).encode('utf-8')
req = urllib.request.Request(dec_url, data=payload, headers={'Content-Type': 'application/json'})
res = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
print("Decision response status:", res['status'], "KPIs resolved count:", res['updated_kpis']['conflicts_resolved_count'])

# Check train in active trains
trains_url = 'http://127.0.0.1:8050/api/trains/active?limit=80'
trains = json.loads(urllib.request.urlopen(trains_url).read().decode('utf-8'))
target_train = next(t for t in trains if t['train_number'] == t_no)
target_stop = next(s for s in target_train['stops'] if s['station_code'] == sttn)
assigned = target_stop.get('assigned_line')
print(f"Train {t_no} stop at {sttn}: assigned_line={assigned}, dep_delay={target_stop.get('delay_departure_mins')}m")
assert assigned in ['1', '4'], f"Must be loop line (1 or 4), got {assigned}"

# Check KPIs
kpis_url = 'http://127.0.0.1:8050/api/kpis?time_sec=21600'
kpis = json.loads(urllib.request.urlopen(kpis_url).read().decode('utf-8'))
print("Live KPIs after approval: resolved =", kpis.get('conflicts_resolved_count'), ", saved =", kpis.get('total_delay_saved_mins'), "mins")
assert kpis.get('conflicts_resolved_count') >= 1, "Resolved count should be >= 1"

print("E2E APPROVAL & LIVE SYSTEM MUTATION VERIFIED SUCCESSFULLY!")
