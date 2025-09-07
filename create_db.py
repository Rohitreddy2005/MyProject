import sqlite3

conn = sqlite3.connect('traffic.db')
cursor = conn.cursor()

# Create table
cursor.execute("""
CREATE TABLE IF NOT EXISTS traffic_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_vehicles INTEGER,
    congestion_level TEXT,
    average_speed REAL,
    timestamp TEXT
)
""")

# Insert some initial dummy data
data = [
    (500, 'Low', 50.0, '08:00'),
    (800, 'Medium', 40.5, '08:10'),
    (1200, 'High', 30.2, '08:20'),
]

cursor.executemany(
    "INSERT INTO traffic_stats (total_vehicles, congestion_level, average_speed, timestamp) VALUES (?, ?, ?, ?)",
    data
)

conn.commit()
conn.close()
print("Database created and initial data inserted.")
