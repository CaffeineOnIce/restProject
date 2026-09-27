import argparse
import asyncio
import json
import os
import statistics
import time
import httpx
import psutil

# Configuration
ARCH1_URL = "https://restapi2.shares.zrok.io"       # Direct Zrok Tunnel
ARCH2_URL = "https://restproject-inbd.onrender.com" # Supabase Cloud Bridge

DURATION_SECONDS = 3600  # 1 Hour
INTERVAL_SECONDS = 30    # 30 Seconds apart

async def measure_request(client, name, url, method, endpoint, payload=None):
    start = time.perf_counter()
    req_bytes = len(json.dumps(payload).encode('utf-8')) if payload else 0
    
    try:
        if method == "GET":
            resp = await client.get(f"{url}{endpoint}", timeout=35.0)
        else:
            resp = await client.post(f"{url}{endpoint}", json=payload, timeout=35.0)
        
        latency = (time.perf_counter() - start) * 1000
        resp_bytes = len(resp.content)
        total_bytes = req_bytes + resp_bytes
        
        return {
            "arch": name,
            "success": resp.status_code == 200,
            "status": resp.status_code,
            "latency_ms": latency,
            "bytes_transferred": total_bytes
        }
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return {
            "arch": name, 
            "success": False, 
            "status": str(e), 
            "latency_ms": latency,
            "bytes_transferred": req_bytes
        }

async def run_sequential_benchmark(name, url, method, endpoint, payload=None):
    """Runs requests sequentially every INTERVAL_SECONDS for DURATION_SECONDS"""
    proc = psutil.Process(os.getpid())
    results = []
    cpu_samples = []
    mem_samples = []
    
    start_time = time.time()
    end_time = start_time + DURATION_SECONDS
    
    print(f"Starting {name} benchmark for {DURATION_SECONDS/60} minutes...")
    print(f"Interval: {INTERVAL_SECONDS}s | Endpoint: {endpoint}")
    
    async with httpx.AsyncClient() as client:
        while time.time() < end_time:
            # 1. Measure Resource Usage
            cpu_samples.append(proc.cpu_percent(interval=None))
            mem_samples.append(proc.memory_info().rss / (1024 * 1024)) # MB
            
            # 2. Perform Request
            print(f"[{time.strftime('%H:%M:%S')}] Sending request...", end=" ")
            result = await measure_request(client, name, url, method, endpoint, payload)
            results.append(result)
            
            status = "OK" if result["success"] else f"FAIL ({result['status']})"
            print(f"{status} - {result['latency_ms']:.2f}ms")
            
            # 3. Wait for next interval
            next_run = time.time() + INTERVAL_SECONDS
            if next_run < end_time:
                await asyncio.sleep(next_run - time.time())

    total_duration = time.time() - start_time
    return results, total_duration, cpu_samples, mem_samples

def process_and_save(results, total_duration, cpu_samples, mem_samples, filename):
    latencies = [r["latency_ms"] for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    bytes_list = [r["bytes_transferred"] for r in results]
    
    total = len(results)
    success_count = len(latencies)
    
    # Calculate P95 safely
    if len(latencies) >= 20:
        p95 = statistics.quantiles(latencies, n=20)[18]
    elif len(latencies) > 0:
        p95 = max(latencies)
    else:
        p95 = 0

    metrics = {
        "success_rate": (success_count / total) * 100 if total > 0 else 0,
        "throughput_rpm": (success_count / total_duration) * 60 if total_duration > 0 else 0,
        "avg_lat_ms": statistics.mean(latencies) if latencies else 0,
        "p95_lat_ms": p95,
        "min_lat_ms": min(latencies, default=0),
        "max_lat_ms": max(latencies, default=0),
        "avg_bytes_per_op": statistics.mean(bytes_list) if bytes_list else 0,
        "avg_cpu_percent": statistics.mean(cpu_samples) if cpu_samples else 0,
        "peak_mem_mb": max(mem_samples, default=0),
        "failed": len(failures),
        "total_duration_sec": total_duration,
        "total_requests": total
    }
    
    with open(filename, "w") as f:
        json.dump(metrics, f, indent=4)
    print(f"\n Saved metrics to {filename}")

def generate_report():
    if not os.path.exists("arch1_metrics.json") or not os.path.exists("arch2_metrics.json"):
        print("Error: missing metric logs. Run both architecture benchmarks first.")
        return

    with open("arch1_metrics.json") as f:
        m1 = json.load(f)
    with open("arch2_metrics.json") as f:
        m2 = json.load(f)

    print("\n" + "=" * 80)
    print(f"{'Category':<15} | {'Metric':<25} | {'Arch 1 (Zrok)':<15} | {'Arch 2 (DB Poll)':<15}")
    print("=" * 80)
    print(f"{'Latency':<15} | {'End-to-End Avg (ms)':<25} | {m1['avg_lat_ms']:<15.2f} | {m2['avg_lat_ms']:<15.2f}")
    print(f"{'Latency':<15} | {'P95 Tail Latency (ms)':<25} | {m1['p95_lat_ms']:<15.2f} | {m2['p95_lat_ms']:<15.2f}")
    print(f"{'Latency':<15} | {'Min / Max (ms)':<25} | {m1['min_lat_ms']:.0f} / {m1['max_lat_ms']:.0f}{'':<4} | {m2['min_lat_ms']:.0f} / {m2['max_lat_ms']:.0f}")
    print("-" * 80)
    print(f"{'Throughput':<15} | {'Requests / Min (T)':<25} | {m1['throughput_rpm']:<15.2f} | {m2['throughput_rpm']:<15.2f}")
    print(f"{'Reliability':<15} | {'Success Rate (%)':<25} | {m1['success_rate']:<15.1f} | {m2['success_rate']:<15.1f}")
    print(f"{'Reliability':<15} | {'Failed Requests':<25} | {m1['failed']:<15} | {m2['failed']:<15}")
    print("-" * 80)
    print(f"{'Network':<15} | {'Avg Bytes / Op (B)':<25} | {m1['avg_bytes_per_op']:<15.1f} | {m2['avg_bytes_per_op']:<15.1f}")
    print(f"{'Resources':<15} | {'Avg CPU Usage (%)':<25} | {m1['avg_cpu_percent']:<15.2f} | {m2['avg_cpu_percent']:<15.2f}")
    print(f"{'Resources':<15} | {'Peak Memory (MB)':<25} | {m1['peak_mem_mb']:<15.2f} | {m2['peak_mem_mb']:<15.2f}")
    print(f"{'Summary':<15} | {'Total Requests':<25} | {m1['total_requests']:<15} | {m2['total_requests']:<15}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Comparative Benchmark Engine (Sequential)")
    parser.add_argument("--run", choices=["arch1", "arch2"], help="Run target architecture benchmark")
    parser.add_argument("--report", action="store_true", help="Generate comparative report")
    args = parser.parse_args()

    if args.run == "arch1":
        print("--- Benchmarking Architecture 1 (Zrok Tunnel) ---")
        # Arch 1 uses GET /temphum
        res, duration, cpu, mem = asyncio.run(run_sequential_benchmark("Arch 1", ARCH1_URL, "GET", "/temphum"))
        process_and_save(res, duration, cpu, mem, "arch1_metrics.json")
    elif args.run == "arch2":
        print("--- Benchmarking Architecture 2 (Cloud DB Polling) ---")
        # Arch 2 uses POST /th
        res, duration, cpu, mem = asyncio.run(run_sequential_benchmark("Arch 2", ARCH2_URL, "POST", "/th"))
        process_and_save(res, duration, cpu, mem, "arch2_metrics.json")
    elif args.report:
        generate_report()
    else:
        parser.print_help()