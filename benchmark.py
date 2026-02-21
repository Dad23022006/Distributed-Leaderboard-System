"""
Performance Benchmark / Load Test
====================================
Spawns N concurrent threads each submitting M score updates.
Measures: throughput, avg latency, success rate, updates/sec.

Usage:  python benchmark.py [--clients 20] [--updates 50]
"""

import socket, ssl, json, time, threading, argparse, statistics, random

HOST = "127.0.0.1"; PORT = 9443


def make_tls_socket():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    raw  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock = ctx.wrap_socket(raw, server_hostname=HOST)
    sock.connect((HOST, PORT))
    return sock


def send_recv(sock, obj):
    sock.sendall((json.dumps(obj) + "\n").encode())
    buf = ""
    while "\n" not in buf:
        buf += sock.recv(4096).decode()
    return json.loads(buf.split("\n")[0])


def worker(pid, n_updates, results, barrier):
    latencies, errors = [], 0
    try:
        sock = make_tls_socket()
        barrier.wait()
        for _ in range(n_updates):
            score = random.randint(1, 100000)
            t0    = time.perf_counter()
            try:
                resp = send_recv(sock, {"cmd": "UPDATE", "player_id": pid,
                                         "name": f"Bot-{pid}", "score": score, "ts": time.time()})
                latencies.append((time.perf_counter() - t0) * 1000)
                if resp.get("status") != "ok":
                    errors += 1
            except Exception:
                errors += 1
        sock.close()
    except Exception:
        errors += n_updates
    results.append({"latencies": latencies, "errors": errors})


def run_benchmark(n_clients, n_updates):
    print(f"\n{'='*55}")
    print(f"  BENCHMARK: {n_clients} clients × {n_updates} updates each")
    print(f"{'='*55}")

    results, threads = [], []
    barrier = threading.Barrier(n_clients)
    t_start = time.perf_counter()

    for i in range(n_clients):
        t = threading.Thread(target=worker, args=(f"bot_{i:04d}", n_updates, results, barrier))
        t.start(); threads.append(t)
    for t in threads: t.join()

    t_total   = time.perf_counter() - t_start
    all_lat   = [l for r in results for l in r["latencies"]]
    total_ok  = len(all_lat)
    total_err = sum(r["errors"] for r in results)

    print(f"\n  Total updates : {n_clients * n_updates}")
    print(f"  Successful    : {total_ok}")
    print(f"  Errors        : {total_err}")
    print(f"  Wall time     : {t_total:.2f}s")
    print(f"  Throughput    : {total_ok / t_total:.1f} updates/sec")
    if all_lat:
        print(f"\n  Latency (ms)  : min={min(all_lat):.2f}  max={max(all_lat):.2f}"
              f"  mean={statistics.mean(all_lat):.2f}  median={statistics.median(all_lat):.2f}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clients", type=int, default=10)
    ap.add_argument("--updates", type=int, default=20)
    args = ap.parse_args()
    run_benchmark(args.clients, args.updates)
