import argparse
import asyncio
import json
import os
import statistics
import time
import httpx
import psutil
import csv

# Configuration
ARCH1_URL = "https://restapi3.shares.zrok.io"       # Direct Zrok Tunnel (Arch 1)
ARCH2_URL = "https://restproject-inbd.onrender.com" # Supabase Cloud Bridge (Arch 2)

NUM_REQUESTS = 120  
INTERVAL_SECONDS = 30

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
    proc = psutil.Process(os.getpid())
    results = []
    cpu_samples = []
    mem_samples = []
    
    start_time = time.time()
    
    print(f"Starting {name} benchmark for {NUM_REQUESTS} requests (approx 1 hour)...")
    print(f"Interval: {INTERVAL_SECONDS}s | Method: {method} | Endpoint: {endpoint}")
    
    async with httpx.AsyncClient() as client:
        for i in range(NUM_REQUESTS):
            # 1. Measure Resource Usage
            cpu_samples.append(proc.cpu_percent(interval=None))
            mem_samples.append(proc.memory_info().rss / (1024 * 1024)) # MB
            
            # 2. Perform Request
            print(f"[{i+1}/{NUM_REQUESTS}] Sending {method} {endpoint}...", end=" ")
            result = await measure_request(client, name, url, method, endpoint, payload)
            results.append(result)
            
            status = "OK" if result["success"] else f"FAIL ({result['status']})"
            print(f"{status} - {result['latency_ms']:.2f}ms")
            
            # 3. Wait for next interval (skip sleep after the very last request)
            if i < NUM_REQUESTS - 1:
                await asyncio.sleep(INTERVAL_SECONDS)

    total_duration = time.time() - start_time
    return results, total_duration, cpu_samples, mem_samples

def process_and_save(results, total_duration, cpu_samples, mem_samples, filename):
    latencies = [r["latency_ms"] for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    bytes_list = [r["bytes_transferred"] for r in results]
    
    total = len(results)
    success_count = len(latencies)
    
    # Calculate P95
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
    print(f"\nSaved metrics to {filename}")

def generate_report():
    if not os.path.exists("arch1_metrics.json") or not os.path.exists("arch2_metrics.json"):
        print("❌ Error: missing metric logs. Run both architecture benchmarks first.")
        return

    with open("arch1_metrics.json") as f:
        m1 = json.load(f)
    with open("arch2_metrics.json") as f:
        m2 = json.load(f)

    report_rows = [
        ["Category", "Metric", "Arch 1 (Zrok)", "Arch 2 (DB Poll)"],
        ["Latency", "End-to-End Avg (ms)", f"{m1['avg_lat_ms']:.2f}", f"{m2['avg_lat_ms']:.2f}"],
        ["Latency", "P95 Tail Latency (ms)", f"{m1['p95_lat_ms']:.2f}", f"{m2['p95_lat_ms']:.2f}"],
        ["Latency", "Min / Max (ms)", f"{m1['min_lat_ms']:.0f} / {m1['max_lat_ms']:.0f}", f"{m2['min_lat_ms']:.0f} / {m2['max_lat_ms']:.0f}"],
        ["Throughput", "Requests / Min", f"{m1['throughput_rpm']:.2f}", f"{m2['throughput_rpm']:.2f}"],
        ["Reliability", "Success Rate (%)", f"{m1['success_rate']:.1f}", f"{m2['success_rate']:.1f}"],
        ["Reliability", "Failed Requests", str(m1['failed']), str(m2['failed'])],
        ["Network", "Avg Bytes / Op", f"{m1['avg_bytes_per_op']:.1f}", f"{m2['avg_bytes_per_op']:.1f}"],
        ["Resources", "Avg CPU Usage (%)", f"{m1['avg_cpu_percent']:.2f}", f"{m2['avg_cpu_percent']:.2f}"],
        ["Resources", "Peak Memory (MB)", f"{m1['peak_mem_mb']:.2f}", f"{m2['peak_mem_mb']:.2f}"],
        ["Summary", "Total Requests", str(m1['total_requests']), str(m2['total_requests'])],
        ["Summary", "Total Duration (sec)", f"{m1['total_duration_sec']:.2f}", f"{m2['total_duration_sec']:.2f}"],
    ]

    # 1. Print to Console
    print("\n" + "=" * 85)
    print(f"{'Category':<15} | {'Metric':<25} | {'Arch 1 (Zrok)':<18} | {'Arch 2 (DB Poll)':<18}")
    print("=" * 85)
    for row in report_rows[1:]: # Skip header for console print
        print(f"{row[0]:<15} | {row[1]:<25} | {row[2]:<18} | {row[3]:<18}")
    print("=" * 85 + "\n")

    # 2. Export to CSV
    csv_filename = "benchmark_report.csv"
    with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerows(report_rows)
    
    print(f"Successfully exported comparative report to: {csv_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Comparative Benchmark Engine (Sequential)")
    parser.add_argument("--run", choices=["arch1", "arch2"], help="Run target architecture benchmark")
    parser.add_argument("--report", action="store_true", help="Generate comparative report")
    args = parser.parse_args()

    if args.run == "arch1":
        print("--- Benchmarking Architecture 1 (Direct Zrok Tunnel) ---")
        res, duration, cpu, mem = asyncio.run(run_sequential_benchmark("Arch 1", ARCH1_URL, "GET", "/temphum"))
        process_and_save(res, duration, cpu, mem, "arch1_metrics.json")
        
    elif args.run == "arch2":
        print("--- Benchmarking Architecture 2 (Supabase Cloud Polling) ---")
        res, duration, cpu, mem = asyncio.run(run_sequential_benchmark("Arch 2", ARCH2_URL, "POST", "/th"))
        process_and_save(res, duration, cpu, mem, "arch2_metrics.json")
        
    elif args.report:
        generate_report()
    else:
        parser.print_help()