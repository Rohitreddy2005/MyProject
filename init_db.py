import sqlite3
import os

DB = os.path.join(os.getcwd(), "traffic.db")
conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS junctions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE,
  lat REAL,
  lng REAL,
  current_cars INTEGER DEFAULT 0,
  signal TEXT DEFAULT 'RED',
  last_update TEXT
);

CREATE TABLE IF NOT EXISTS traffic_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  junction_id INTEGER,
  cars INTEGER,
  signal TEXT,
  timestamp TEXT
);
""")

# Insert sample Bhubaneswar junctions (name, lat, lng)
junctions = [
    ("Vani Vihar", 20.2871, 85.8260),
    ("Jaydev Vihar", 20.2698, 85.8265),
    ("Sachivalaya Marg", 20.2961, 85.8245),
    ("Unit 1 Crossing", 20.2715, 85.8317),
    ("Master Canteen", 20.2749, 85.8284),
    ("Khandagiri Road", 20.2542, 85.8099),
    ("Janpath", 20.2985, 85.8269),
    ("Market Building", 20.2989, 85.8240),
    ("Bapuji Nagar", 20.2968, 85.8182),
    ("Sachivalaya Marg North", 20.3011, 85.8286),
    ("Infocity Crossing", 20.2890, 85.8370),
    ("Patia Junction", 20.3450, 85.8200)
]

for name, lat, lng in junctions:
    cur.execute(
        "INSERT OR IGNORE INTO junctions (name, lat, lng, current_cars, signal) VALUES (?,?,?,?,?)",
        (name, lat, lng, 0, "RED")
    )

conn.commit()
conn.close()
print("Initialized traffic.db with sample Bhubaneswar junctions.")
