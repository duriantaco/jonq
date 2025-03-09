import json
import random
try:
    import names
except ImportError:
    names = None
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

def generate_entry(_):
    name = names.get_full_name() if names else ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))
    age = random.randint(18, 65)
    salary = round(random.uniform(30000, 100000), 2)
    return {"name": name, "age": age, "salary": salary}

with ThreadPoolExecutor(max_workers=10) as executor:
    data = list(tqdm(executor.map(generate_entry, range(50000)), total=50000))

with open('output.json', 'w') as f:
    json.dump(data, f, indent=4)