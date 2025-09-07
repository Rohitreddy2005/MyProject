import sqlite3
import random
import time
from datetime import datetime

congestion_levels = ['Low', 'Medium', 'High']

def insert_traffic():
    while True:
        total_vehicles = random.randint(200, 1500)
        congestion_level = random.choices(
            congestion_levels, weights=[0.4, 0.35, 0.25], k=1
        )[0]
        average_speed = round(random.uniform(20, 60), 1)
        timestamp = datetime.now().strftime('%H:%M:%S')

        conn = sqlite3.connect('traffic.db')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO traffic_stats (total_vehicles, congestion_level, average_speed, timestamp) VALUES (?, ?, ?, ?)",
            (total_vehicles, congestion_level, average_speed, timestamp)
        )
        conn.commit()
        conn.close()

        print(f"[{timestamp}] Inserted: {total_vehicles}, {congestion_level}, {average_speed} km/h")

        time.sleep(10)  # change to 60 for 1-minute updates

if __name__ == "__main__":
    insert_traffic()
