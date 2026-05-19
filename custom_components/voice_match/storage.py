import os, json

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def save_json(path, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(data, f)

def load_json(path, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default
