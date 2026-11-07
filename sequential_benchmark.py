import argparse
import asyncio
import csv
import glob
import time

import httpx
import numpy as np

# Configuration
ARCH1_URL = "https://restapi5.shares.zrok.io"        # Direct Zrok Tunnel (Arch 1)
ARCH2_URL = "https://restproject-inbd.onrender.com"  # Supabase Cloud Bridge (Arch 2)
ENDPOINT = "/th"         # same endpoint, method and response format on both architectures

NUM_REQUESTS = 120
INTERVAL_SECONDS = 30    # fixed schedule: request i starts at start + i * 30 s
TIMEOUT = 35.0           # per-request timeout (s)
BOOTSTRAP = 2000

ARCHS = {"arch1": ("Arch 1 (Zrok)", ARCH1_URL), "arch2": ("Arch 2 (DB Poll)", ARCH2_URL)}

TIMING_KEYS = [
    "t_pi_rx", "t_pi_seen", "t_esp_start", "t_esp_end", "t_db_done",
    "t_pi_done", "t_pi_tx",
    "t_render_rx", "t_render_insert", "t_render_detect", "t_render_tx",
]
FIELDS = ["arch", "session", "index", "t_client_send", "t_client_recv",
          "latency_ms", "http_status", "success", "error"] + TIMING_KEYS


def now_ms():
    return time.time() * 1000


def valid_reading(body):
    return isinstance(body.get("temp"), (int, float)) and isinstance(body.get("hum"), (int, float))


async def measure_request(client, arch, session, index):
    url = ARCHS[arch][1] + ENDPOINT
    body, http_status, error = {}, "", ""
    t_send = now_ms()
    start = time.perf_counter()
    try:
        resp = await client.post(url, timeout=TIMEOUT)
        latency = (time.perf_counter() - start) * 1000
        http_status = resp.status_code
        try:
            body = resp.json()
        except ValueError:
            body = {}
        # Same rule for both architectures: HTTP 200 and a valid reading in the body.
        success = http_status == 200 and valid_reading(body)
        if not success:
            error = str(body.get("error") or resp.text[:100])
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        success = False
        error = type(e).__name__ + ": " + str(e)
    t_recv = now_ms()

    timing = body.get("timing") or {}
    row = {
        "arch": arch, "session": session, "index": index,
        "t_client_send": round(t_send, 1), "t_client_recv": round(t_recv, 1),
        "latency_ms": round(latency, 1), "http_status": http_status,
        "success": int(success), "error": error,
    }
    row.update({k: timing.get(k) for k in TIMING_KEYS})
    return row


async def run_session(arch, session):
    name = ARCHS[arch][0]
    path = f"raw_{arch}_{session}.csv"
    print(f"--- {name}, session '{session}': {NUM_REQUESTS} requests, one every {INTERVAL_SECONDS}s ---")
    print(f"Writing raw results to {path}")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            start = time.monotonic()
            for i in range(NUM_REQUESTS):
                # Fixed schedule (start-to-start); if a request overruns its slot,
                # the next one starts immediately.
                delay = start + i * INTERVAL_SECONDS - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                row = await measure_request(client, arch, session, i)
                writer.writerow(row)
                f.flush()
                state = "OK" if row["success"] else f"FAIL ({row['http_status']} {row['error']})"
                print(f"[{i + 1}/{NUM_REQUESTS}] {state} - {row['latency_ms']:.0f} ms")


def load_rows():
    rows = []
    for path in sorted(glob.glob("raw_arch*_*.csv")):
        with open(path, encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    return rows


def num(value):
    return float(value) if value not in (None, "") else None


def diff(r, a, b):
    x, y = num(r.get(a)), num(r.get(b))
    return y - x if x is not None and y is not None else None


def segments(r):
    """Per-hop segments in ms. Segments marked (x-host) use timestamps from two
    machines and include their clock offset; the others use one machine's clock."""
    e2e = num(r["latency_ms"])
    if r["arch"] == "arch1":
        pi_total = diff(r, "t_pi_rx", "t_pi_tx")
        esp, db = diff(r, "t_esp_start", "t_esp_end"), diff(r, "t_esp_end", "t_db_done")
        return {
            "network_tunnel": e2e - pi_total if pi_total is not None else None,
            "esp_read": esp,
            "db_log": db,
            "pi_other": pi_total - (esp or 0) - (db or 0) if pi_total is not None else None,
        }
    render_total = diff(r, "t_render_rx", "t_render_tx")
    return {
        "network_render": e2e - render_total if render_total is not None else None,
        "render_insert": diff(r, "t_render_rx", "t_render_insert"),
        "pi_poll_wait (x-host)": diff(r, "t_render_insert", "t_pi_seen"),
        "pi_claim": diff(r, "t_pi_seen", "t_esp_start"),
        "esp_read": diff(r, "t_esp_start", "t_esp_end"),
        "db_log": diff(r, "t_esp_end", "t_db_done"),
        "pi_complete": diff(r, "t_db_done", "t_pi_done"),
        "render_poll_wait (x-host)": diff(r, "t_pi_done", "t_render_detect"),
    }


def p95(a, axis=None):
    return np.percentile(a, 95, axis=axis)


def generate_report():
    rows = load_rows()
    if not rows:
        print("❌ Error: no raw_arch*_*.csv files found. Run sessions first.")
        return
    rng = np.random.default_rng(0)
    order = ["arch1", "arch2"]
    lat, summary = {}, {}

    for arch in order:
        sent = [r for r in rows if r["arch"] == arch]
        ok = np.array([float(r["latency_ms"]) for r in sent if r["success"] == "1"])
        lat[arch] = ok
        if len(ok) == 0:
            summary[arch] = None
            continue
        q1, med, q3 = np.percentile(ok, [25, 50, 75])
        boot = p95(rng.choice(ok, size=(BOOTSTRAP, len(ok)), replace=True), axis=1)
        summary[arch] = {
            "median": med, "iqr": f"{q1:.0f}-{q3:.0f}", "p95": p95(ok),
            "p95_ci": f"{np.percentile(boot, 2.5):.0f}-{np.percentile(boot, 97.5):.0f}",
            "min": ok.min(), "max": ok.max(), "success": f"{len(ok)}/{len(sent)}",
        }

    report_rows = [["Metric", ARCHS["arch1"][0], ARCHS["arch2"][0]]]
    for key, label in [("median", "Median (ms)"), ("iqr", "IQR (ms)"), ("p95", "P95 (ms)"),
                       ("p95_ci", "P95 95% CI (ms)"), ("min", "Min (ms)"), ("max", "Max (ms)"),
                       ("success", "Successful / sent")]:
        vals = []
        for arch in order:
            v = summary[arch][key] if summary[arch] else "-"
            vals.append(f"{v:.0f}" if isinstance(v, (float, np.floating)) else str(v))
        report_rows.append([label] + vals)

    for session in sorted({r["session"] for r in rows}):
        meds = []
        for arch in order:
            x = [float(r["latency_ms"]) for r in rows
                 if r["session"] == session and r["arch"] == arch and r["success"] == "1"]
            meds.append(f"{np.median(x):.0f}" if x else "-")
        report_rows.append([f"Session {session} median (ms)"] + meds)

    # Comparison between the two architectures (one value + its CI, not per-architecture)
    comparison_rows = []
    if len(lat["arch1"]) and len(lat["arch2"]):
        a, b = lat["arch1"], lat["arch2"]
        d = np.median(b) - np.median(a)
        dd = (np.median(rng.choice(b, size=(BOOTSTRAP, len(b)), replace=True), axis=1)
              - np.median(rng.choice(a, size=(BOOTSTRAP, len(a)), replace=True), axis=1))
        comparison_rows = [
            ["Comparison", "Value", "95% CI"],
            ["Median difference, Arch 2 - Arch 1 (ms)", f"{d:.0f}",
             f"{np.percentile(dd, 2.5):.0f}-{np.percentile(dd, 97.5):.0f}"],
            ["Median ratio, Arch 2 / Arch 1", f"{np.median(b) / np.median(a):.2f}", ""],
        ]

    print("\n" + "=" * 78)
    for row in report_rows:
        print(f"{row[0]:<40} | {row[1]:<16} | {row[2]:<16}")
    if comparison_rows:
        print("-" * 78)
        for row in comparison_rows:
            print(f"{row[0]:<40} | {row[1]:<16} | {row[2]:<16}")
    print("=" * 78)
    with open("benchmark_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerows(report_rows)
        if comparison_rows:
            w.writerow([])
            w.writerows(comparison_rows)

    seg_rows = [["Arch", "Segment", "Median (ms)", "N"]]
    seg_medians = {}
    for arch in order:
        per = {}
        for r in rows:
            if r["arch"] == arch and r["success"] == "1":
                for k, v in segments(r).items():
                    if v is not None:
                        per.setdefault(k, []).append(v)
        seg_medians[arch] = {k: float(np.median(v)) for k, v in per.items()}
        for k, v in per.items():
            seg_rows.append([ARCHS[arch][0], k, f"{np.median(v):.0f}", len(v)])
    with open("segments_report.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(seg_rows)
    print("\nPer-segment medians:")
    for row in seg_rows[1:]:
        print(f"  {row[0]:<18} {row[1]:<28} {row[2]:>7} ms  (n={row[3]})")

    plot_figures(lat, seg_medians, order)
    print("\nSaved benchmark_report.csv, segments_report.csv, latency_cdf.png, latency_breakdown.png")


SEGMENT_LABELS = {
    "network_tunnel": "Network (tunnel)",
    "network_render": "Network (Render)",
    "esp_read": "ESP32 read",
    "db_log": "DB write",
    "pi_other": "Pi other",
    "render_insert": "Render insert",
    "pi_poll_wait (x-host)": "Pi poll wait*",
    "pi_claim": "Pi claim",
    "pi_complete": "Pi complete",
    "render_poll_wait (x-host)": "Render poll wait*",
}


def plot_figures(lat, seg_medians, order):
    import math
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Sized for half a two-column page: small canvas, relatively large text.
    plt.rcParams.update({"font.size": 10, "axes.labelsize": 10,
                         "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 8.5})
    figsize = (4.8, 3.2)

    # CDF of end-to-end latency
    fig, ax = plt.subplots(figsize=figsize)
    for arch in order:
        x = np.sort(lat[arch])
        if len(x):
            ax.step(x, np.arange(1, len(x) + 1) / len(x), where="post",
                    linewidth=1.8, label=ARCHS[arch][0])
    ax.set_xlabel("End-to-end latency (ms)")
    ax.set_ylabel("Cumulative fraction")
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.savefig("latency_cdf.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # Stacked per-segment median latency, legend under the plot in 2 rows
    fig, ax = plt.subplots(figsize=figsize)
    cmap = plt.get_cmap("tab20")
    seen = {}
    for i, arch in enumerate(order):
        left = 0.0
        for k, v in seg_medians[arch].items():
            v = max(v, 0.0)
            if v < 1:          # skip empty segments so they don't clutter the legend
                continue
            if k not in seen:
                seen[k] = cmap(len(seen) % 20)
            ax.barh(i, v, left=left, color=seen[k], edgecolor="white", height=0.6,
                    label=SEGMENT_LABELS.get(k, k))
            left += v
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([ARCHS[a][0].replace(" (", "\n(") for a in order])
    ax.invert_yaxis()
    ax.set_xlabel("Median latency per segment (ms)")
    ax.grid(axis="x", alpha=0.3)
    handles, labels = ax.get_legend_handles_labels()
    uniq = dict(zip(labels, handles))
    ax.legend(uniq.values(), uniq.keys(), loc="upper center", bbox_to_anchor=(0.5, -0.22),
              ncol=math.ceil(len(uniq) / 2), frameon=False,
              columnspacing=0.9, handlelength=1.1, handletextpad=0.4)
    fig.savefig("latency_breakdown.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark: Arch 1 (Zrok) vs Arch 2 (DB Poll), one architecture per session")
    parser.add_argument("--run", choices=["arch1", "arch2"], help="Run one session of the given architecture")
    parser.add_argument("--session", default="s1", help="Session label, e.g. s1, s2, s3 (default: s1)")
    parser.add_argument("--report", action="store_true", help="Report over all raw_arch*_*.csv files")
    args = parser.parse_args()

    if args.run:
        asyncio.run(run_session(args.run, args.session))
    elif args.report:
        generate_report()
    else:
        parser.print_help()
