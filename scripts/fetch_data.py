import urllib.request
import json
import os

def fetch_f1_calendar():
    url = "https://api.jolpi.ca/ergast/f1/current.json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'MotorSport-Calendar-App'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception as e:
        print(f"Błąd podczas pobierania danych F1: {e}")
        return None

if __name__ == "__main__":
    print("Rozpoczynam pobieranie danych motorsportowych...")
    f1_data = fetch_f1_calendar()
    
    if f1_data:
        os.makedirs("data", exist_ok=True)
        filepath = "data/motorsport_data.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"f1": f1_data}, f, ensure_ascii=False, indent=2)
        print(f"Dane zapisane pomyślnie w {filepath}")
    else:
        print("Nie udało się zaktualizować danych.")
