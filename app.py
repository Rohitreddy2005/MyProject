from flask import Flask, render_template, request, jsonify, g
import sqlite3, os, json, csv
from datetime import datetime
import math, threading
from io import StringIO

DB_PATH = os.path.join(os.getcwd(), "traffic.db")

app = Flask(__name__)

# ---------- DB helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def row_to_dict(row):
    return {k: row[k] for k in row.keys()}

# ---------- Utilities ----------
def haversine(lat1, lon1, lat2, lon2):
    # returns distance in kilometers
    R = 6371.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def schedule_reopen_road(road_id, original_status, delay_seconds=60):
    def worker():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE roads SET status = ? WHERE id = ?", (original_status, road_id))
        conn.commit()
        conn.close()
    t = threading.Timer(delay_seconds, worker)
    t.daemon = True
    t.start()

def schedule_revert_signals(junction_ids, original_signals, delay_seconds=15):
    def worker():
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        now = datetime.utcnow().isoformat()
        for jid, sig in zip(junction_ids, original_signals):
            cur.execute("UPDATE junctions SET signal = ?, last_update = ? WHERE id = ?", (sig, now, jid))
            cur.execute("INSERT INTO traffic_log (junction_id, cars, signal, timestamp) VALUES (?,?,?,?)",
                        (jid, 0, sig, now))
        conn.commit()
        conn.close()
    t = threading.Timer(delay_seconds, worker)
    t.daemon = True
    t.start()

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/map")
def map_view():
    # alias for dashboard if you prefer /map
    return render_template("dashboard.html")

@app.route("/signal/<int:jid>")
def signal_page(jid):
    return render_template("signal.html", jid=jid)

@app.route("/about")
def about():
    return render_template("about.html")

# ---------- API endpoints ----------

# Return all junctions with lat/lng and KPIs
@app.route("/api/junctions", methods=["GET"])
def api_junctions():
    db = get_db()
    cur = db.execute("SELECT id, name, lat, lng, current_cars, signal, last_update FROM junctions ORDER BY id")
    rows = [row_to_dict(r) for r in cur.fetchall()]
    return jsonify(rows)

# Return all roads (coords JSON parsed)
@app.route("/api/roads", methods=["GET"])
def api_roads():
    db = get_db()
    cur = db.execute("SELECT id, name, coords, status, congestion, from_junction, to_junction FROM roads")
    result = []
    for r in cur.fetchall():
        item = row_to_dict(r)
        # coords stored as JSON text in DB
        try:
            item['coords'] = json.loads(item['coords']) if item['coords'] else []
        except Exception:
            item['coords'] = []
        result.append(item)
    return jsonify(result)

# Add an event: ACCIDENT, CONSTRUCTION, or CLEAR
@app.route("/api/event", methods=["POST"])
def api_event():
    data = request.get_json(silent=True)
    if not data or 'road_id' not in data or 'type' not in data:
        return jsonify({"error": "road_id and type required"}), 400
    road_id = int(data['road_id'])
    etype = data['type'].upper()  # ACCIDENT / CONSTRUCTION / CLEAR
    desc = data.get('description', '')
    now = datetime.utcnow().isoformat()

    db = get_db()
    if etype == 'CLEAR':
        db.execute("UPDATE roads SET status = 'OPEN' WHERE id = ?", (road_id,))
        db.execute("INSERT INTO events (road_id, type, description, start_time, end_time) VALUES (?,?,?,?,?)",
                   (road_id, 'CLEAR', desc, now, now))
        db.commit()
        return jsonify({"status": "cleared", "road_id": road_id})

    status = 'CLOSED' if etype == 'ACCIDENT' else 'CONSTRUCTION'
    db.execute("UPDATE roads SET status = ? WHERE id = ?", (status, road_id))
    db.execute("INSERT INTO events (road_id, type, description, start_time) VALUES (?,?,?,?)",
               (road_id, etype, desc, now))
    db.commit()

    # Simple diversion simulation: increase congestion on neighboring roads
    cur = db.execute("SELECT from_junction, to_junction FROM roads WHERE id = ?", (road_id,))
    row = cur.fetchone()
    if row:
        f = row['from_junction']; t = row['to_junction']
        cur2 = db.execute(
            "SELECT id, congestion FROM roads WHERE id != ? AND (from_junction = ? OR to_junction = ? OR from_junction = ? OR to_junction = ?)",
            (road_id, f, f, t, t)
        )
        for r in cur2.fetchall():
            newc = min(100, (r['congestion'] or 20) + 30)
            db.execute("UPDATE roads SET congestion = ? WHERE id = ?", (newc, r['id']))
    db.commit()

    # If accident, schedule auto reopen for demo after 120s
    if status == 'CLOSED':
        schedule_reopen_road(road_id, 'OPEN', delay_seconds=120)

    return jsonify({"status": "ok", "road_id": road_id, "new_status": status})

# Manual signal update
@app.route("/api/junction/<int:jid>/signal", methods=["POST"])
def api_set_signal(jid):
    data = request.get_json(silent=True)
    if not data or 'signal' not in data:
        return jsonify({"error": "signal required"}), 400
    sig = data['signal'].upper()
    if sig not in ('GREEN', 'RED'):
        return jsonify({"error": "signal must be GREEN or RED"}), 400
    db = get_db()
    now = datetime.utcnow().isoformat()
    db.execute("UPDATE junctions SET signal = ?, last_update = ? WHERE id = ?", (sig, now, jid))
    db.execute("INSERT INTO traffic_log (junction_id, cars, signal, timestamp) VALUES (?,?,?,?)",
               (jid, 0, sig, now))
    db.commit()
    return jsonify({"status": "ok", "id": jid, "signal": sig})

# Traffic log (for signal page)
@app.route("/api/traffic_log", methods=["GET"])
def api_traffic_log():
    jid = request.args.get("junction_id", type=int)
    limit = request.args.get("limit", default=200, type=int)
    db = get_db()
    if jid:
        cur = db.execute("SELECT id, junction_id, cars, signal, timestamp FROM traffic_log WHERE junction_id = ? ORDER BY id DESC LIMIT ?",
                         (jid, limit))
    else:
        cur = db.execute("SELECT id, junction_id, cars, signal, timestamp FROM traffic_log ORDER BY id DESC LIMIT ?", (limit,))
    rows = [row_to_dict(r) for r in cur.fetchall()]
    return jsonify(rows)

# Export CSV for a junction
@app.route("/api/junction/<int:jid>/export", methods=["GET"])
def api_export_csv(jid):
    db = get_db()
    cur = db.execute("SELECT id, junction_id, cars, signal, timestamp FROM traffic_log WHERE junction_id = ? ORDER BY id DESC", (jid,))
    rows = cur.fetchall()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['id','junction_id','cars','signal','timestamp'])
    for r in rows:
        cw.writerow([r['id'], r['junction_id'], r['cars'], r['signal'], r['timestamp']])
    mem = si.getvalue()
    return (mem, 200, {
        'Content-Type': 'text/csv',
        'Content-Disposition': f'attachment; filename=junction_{jid}_log.csv'
    })

# Emergency preemption endpoint (ambulance / vip)
@app.route("/api/emergency", methods=["POST"])
def api_emergency():
    data = request.get_json(silent=True)
    if not data or ("lat" not in data or "lng" not in data or "type" not in data):
        return jsonify({"error": "lat,lng,type required"}), 400

    lat = float(data["lat"]); lng = float(data["lng"])
    etype = data["type"].lower()  # 'ambulance' or 'vip'
    radius_km = float(data.get("radius_km", 2.5))
    affect_count = int(data.get("affect_count", 4))
    duration = int(data.get("duration", 20))

    db = get_db()
    cur = db.execute("SELECT id, name, lat, lng, signal FROM junctions")
    rows = cur.fetchall()
    distances = []
    for r in rows:
        if r["lat"] is None or r["lng"] is None:
            continue
        d = haversine(lat, lng, r["lat"], r["lng"])
        distances.append((d, r))
    distances.sort(key=lambda x: x[0])
    selected = [r for d, r in distances if d <= radius_km][:affect_count]
    if not selected:
        selected = [distances[i][1] for i in range(min(len(distances), affect_count))]

    selected_ids = [r["id"] for r in selected]
    original_signals = [r["signal"] for r in selected]

    now = datetime.utcnow().isoformat()
    for jid in selected_ids:
        db.execute("UPDATE junctions SET signal = ?, last_update = ? WHERE id = ?", ("GREEN", now, jid))
        db.execute("INSERT INTO traffic_log (junction_id, cars, signal, timestamp) VALUES (?,?,?,?)",
                   (jid, 0, "GREEN_PREEMPT", now))
    db.commit()

    # revert signals after duration
    schedule_revert_signals(selected_ids, original_signals, delay_seconds=duration)

    return jsonify({
        "status": "ok",
        "type": etype,
        "affected": selected_ids,
        "duration": duration
    })

# ---------- end APIs ----------

if __name__ == "__main__":
    app.run(debug=True)

