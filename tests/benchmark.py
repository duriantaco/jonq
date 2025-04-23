import time
import json
import sys
import random
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import jonq_fast
from jonq.csv_utils import flatten_json as flatten_json_py

def generate_test_data(depth=3, width=10, array_size=5):
    """Generate complex nested data structure for testing"""
    if depth <= 0:
        return random.choice([
            random.randint(1, 100),
            random.random() * 100,
            "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=10)),
            True,
            False,
            None
        ])
    
    if random.random() < 0.3: 
        return [
            generate_test_data(depth-1, width, array_size) 
            for _ in range(array_size)
        ]
    else:
        return {
            f"key_{i}_{random.randint(1000, 9999)}": generate_test_data(depth-1, width, array_size)
            for i in range(width)
        }

def run_benchmark():
    test_sizes = [
        ("Small", 2, 5, 3),
        ("Medium", 3, 8, 5),
        ("Large", 4, 10, 8),
        ("Very Large", 5, 15, 10)
    ]
    
    print(f"{'Size':<12} {'Python Time':<15} {'Rust Time':<15} {'Speedup':<10}")
    print("-" * 55)
    
    for name, depth, width, array_size in test_sizes:
        data = generate_test_data(depth, width, array_size)
        iterations = 5
        
        py_times = []
        for _ in range(iterations):
            start = time.time()
            flatten_json_py(data)
            py_times.append(time.time() - start)
        py_avg = sum(py_times) / len(py_times)
        
        rust_times = []
        for _ in range(iterations):
            start = time.time()
            jonq_fast.flatten(data, ".")
            rust_times.append(time.time() - start)
        rust_avg = sum(rust_times) / len(rust_times)
        
        speedup = py_avg / rust_avg if rust_avg > 0 else float('inf')
        
        print(f"{name:<12} {py_avg*1000:>8.2f} ms     {rust_avg*1000:>8.2f} ms     {speedup:>6.2f}x")
        
        data_size = len(json.dumps(data))
        item_count = len(flatten_json_py(data))
        print(f"  - {data_size:,} bytes, {item_count:,} flattened items")

if __name__ == "__main__":
    print("Benchmarking jonq_fast vs Python implementation")
    print("=" * 55)
    run_benchmark()