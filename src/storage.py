import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
HISTORY_FILE = os.path.join(DATA_DIR, 'history.jsonl')

def get_next_run_id(project_id: str) -> str:
    """
    Reads the history to count existing runs for a given project_id
    and returns the next sequential ID (e.g., 'SITE_A-003').
    """
    history = load_history()
    count = 0
    for record in history:
        if record.get("project_id") == project_id:
            count += 1
            
    return f"{project_id}-{count + 1:03d}"

def save_run(project_id: str, inputs: dict, metrics: dict, raw_hourly_kw: list) -> str:
    """
    Appends a simulation run to the JSONLines datastore, including the 
    raw hourly data so multiple arrays can be combined later.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    
    run_id = get_next_run_id(project_id)
    
    record = {
        "project_id": project_id,
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "inputs": inputs,
        "metrics": metrics,
        "raw_hourly_kw": raw_hourly_kw  # Required for combining results later
    }
    
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record) + '\n')
        
    return run_id

def load_history() -> list:
    """Loads all historical runs from the datastore."""
    if not os.path.exists(HISTORY_FILE):
        return []
        
    history = []
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                history.append(json.loads(line))
    return history