import sqlite3, time, random, os
from datetime import datetime

DB = os.path.join(os.getcwd(), "traffic.db")

def update_simulation():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id, lat, lng FROM junctions")
    rows = cur.fetchall()
    now = datetime.utcnow().isoformat()
    for (jid, lat, lng) in rows:
        # simulate queue length depending on location randomness
        base = random.randint(0, 60)
        # small correlation to time of day (simple)
        t = int(time.time()) % 86400
        hour = (t // 3600)
        if 8 <= hour <= 10 or 17 <= hour <= 20:
            base += random.randint(10, 40)  # rush hour bump
        cars = max(0, base + random.randint(-5, 10))
        cur.execute("UPDATE junctions SET current_cars = ?, last_update = ? WHERE id = ?", (cars, now, jid))
        cur.execute("INSERT INTO traffic_log (junction_id, cars, signal, timestamp) VALUES (?,?,?,?)",
                    (jid, cars, "SIM", now))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    print("Simulation started. Ctrl+C to stop.")
    try:
        while True:
            update_simulation()
            time.sleep(4)
    except KeyboardInterrupt:
        print("Simulation stopped.")
