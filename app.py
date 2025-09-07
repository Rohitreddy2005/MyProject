from flask import Flask, render_template, request, jsonify, g
import sqlite3
import os
from datetime import datetime
import threading
import math

DB_PATH = os.path.join(os.getcwd(), "traffic.db")

app = Flask(__name__)

# ---------- Database helpers ----------
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

# ---------- Utility ----------
def haversine(lat1, lon1, lat2, lon2):
    # kilometers
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def revert_signals(junction_ids, original_signals, delay_seconds=15):
    def worker():
        db = sqlite3.connect(DB_PATH)
        cur = db.cursor()
        now = datetime.utcnow().isoformat()
        for jid, sig in zip(junction_ids, original_signals):
            cur.execute("UPDATE junctions SET signal = ?, last_update = ? WHERE id = ?", (sig, now, jid))
            # log revert
            cur.execute("INSERT INTO traffic_log (junction_id, cars, signal, timestamp) VALUES (?,?,?,?)",
                        (jid, 0, sig, now))
        db.commit()
        db.close()
    t = threading.Timer(delay_seconds, worker)
    t.start()

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/about")
def about():
    return render_template("about.html")

# Return all junctions with lat/lng and KPIs
@app.route("/api/junctions", methods=["GET"])
def api_junctions():
    db = get_db()
    cur = db.execute("SELECT id, name, lat, lng, current_cars, signal, last_update FROM junctions ORDER BY id")
    rows = [row_to_dict(r) for r in cur.fetchall()]
    return jsonify(rows)

# Manual signal update
@app.route("/api/junction/<int:jid>/signal", methods=["POST"])
def api_update_signal(jid):
    data = request.get_json(silent=True)
    if not data or "signal" not in data:
        return jsonify({"error": "signal required (GREEN or RED)"}), 400
    new_signal = data["signal"].upper()
    if new_signal not in ("GREEN", "RED"):
        return jsonify({"error": "invalid signal"}), 400

    db = get_db()
    now = datetime.utcnow().isoformat()
    db.execute("UPDATE junctions SET signal = ?, last_update = ? WHERE id = ?", (new_signal, now, jid))
    cur = db.execute("SELECT current_cars FROM junctions WHERE id = ?", (jid,))
    row = cur.fetchone()
    cars = row["current_cars"] if row else 0
    db.execute("INSERT INTO traffic_log (junction_id, cars, signal, timestamp) VALUES (?,?,?,?)",
               (jid, cars, new_signal, now))
    db.commit()
    return jsonify({"status": "ok", "id": jid, "signal": new_signal})

# Emergency preemption: ambulance or VIP
@app.route("/api/emergency", methods=["POST"])
def api_emergency():
    data = request.get_json(silent=True)
    if not data or ("lat" not in data or "lng" not in data or "type" not in data):
        return jsonify({"error": "lat,lng,type required"}), 400

    lat = float(data["lat"])
    lng = float(data["lng"])
    etype = data["type"]  # 'ambulance' or 'vip'
    radius_km = float(data.get("radius_km", 2.5))  # search radius
    affect_count = int(data.get("affect_count", 3))  # number of nearest junctions to preempt
    preempt_duration = int(data.get("duration", 20))  # seconds to keep green

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
        # fallback: pick nearest even if outside radius
        selected = [distances[i][1] for i in range(min(len(distances), affect_count))]

    selected_ids = [r["id"] for r in selected]
    original_signals = [r["signal"] for r in selected]

    now = datetime.utcnow().isoformat()
    # set selected to GREEN (preempt)
    for jid in selected_ids:
        db.execute("UPDATE junctions SET signal = ?, last_update = ? WHERE id = ?", ("GREEN", now, jid))
        db.execute("INSERT INTO traffic_log (junction_id, cars, signal, timestamp) VALUES (?,?,?,?)",
                   (jid, 0, "GREEN_PREEMPT", now))
    db.commit()

    # schedule reversion to original signals after preempt_duration seconds
    revert_signals(selected_ids, original_signals, delay_seconds=preempt_duration)

    return jsonify({
        "status": "ok",
        "type": etype,
        "affected": selected_ids,
        "duration": preempt_duration
    })

# Get traffic log for a junction (simple)
@app.route("/api/traffic_log")
def api_traffic_log():
    jid = request.args.get("junction_id", type=int)
    db = get_db()
    if jid:
        cur = db.execute("SELECT id, junction_id, cars, signal, timestamp FROM traffic_log WHERE junction_id = ? ORDER BY id DESC LIMIT 100", (jid,))
    else:
        cur = db.execute("SELECT id, junction_id, cars, signal, timestamp FROM traffic_log ORDER BY id DESC LIMIT 200")
    rows = [row_to_dict(r) for r in cur.fetchall()]
    return jsonify(rows)

if __name__ == "__main__":
    app.run(debug=True)
