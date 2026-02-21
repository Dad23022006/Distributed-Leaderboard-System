# 🏆 Distributed Leaderboard System

> **Jackfruit Mini Project** | TCP + SSL/TLS | Python | Concurrent Clients | Real-time Rankings

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     CLIENTS (N)                      │
│  [client.py]  [demo_auto.py]  [benchmark.py]        │
│       │               │               │              │
│       └───────────────┴───────────────┘              │
│                       │ TCP + TLS (port 9443)        │
└───────────────────────┼─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│                  server.py (LeaderboardServer)       │
│                                                      │
│   ssl.wrap_socket() → accept loop                    │
│        │                                             │
│        ├── ClientHandler (Thread-1) ─┐               │
│        ├── ClientHandler (Thread-2)  │               │
│        └── ClientHandler (Thread-N) ─┤               │
│                                      ▼               │
│              LeaderboardEngine (shared)              │
│              ┌─────────────────────────┐             │
│              │  RLock (thread-safe)    │             │
│              │  _scores dict           │             │
│              │  LWW conflict resolve   │             │
│              └─────────────────────────┘             │
└─────────────────────────────────────────────────────┘
```

**Protocol:** Newline-delimited JSON over TCP + TLS 1.2+

**Conflict Resolution:** Last-Write-Wins (LWW) — each update carries a Unix timestamp; the server accepts the update only if `incoming_ts > stored_ts`, preventing stale overwrites in concurrent scenarios.

---

## Mandatory Requirements Checklist

| Requirement | Implementation |
|---|---|
| TCP sockets | `socket.SOCK_STREAM` — raw TCP, no HTTP |
| SSL/TLS | `ssl.SSLContext(PROTOCOL_TLS_SERVER)` — TLS 1.2+ enforced |
| Multiple concurrent clients | One `threading.Thread` per accepted connection |
| Network communication only | All exchanges over TCP sockets |

---

## Setup

### 1. Generate SSL Certificate (already done — in `certs/`)
```bash
openssl req -x509 -newkey rsa:2048 -keyout certs/server.key \
    -out certs/server.crt -days 365 -nodes -subj "/CN=localhost"
```

### 2. Install Python (3.10+, stdlib only — no pip installs needed)

### 3. Start the Server
```bash
python server.py
```

### 4. Connect a Client (interactive)
```bash
python client.py
```

### 5. Run Automated Demo (10 players concurrently)
```bash
python demo_auto.py
```

### 6. Run Performance Benchmark
```bash
python benchmark.py --clients 20 --updates 50
```

---

## JSON Protocol Reference

### Client → Server

| Command | Payload | Description |
|---|---|---|
| `UPDATE` | `{cmd, player_id, name, score, ts}` | Submit score (LWW applied) |
| `GET_TOP` | `{cmd, n?}` | Fetch top-N leaderboard |
| `GET_PLAYER` | `{cmd, player_id}` | Lookup specific player |
| `STATS` | `{cmd}` | Server performance metrics |
| `PING` | `{cmd}` | Latency check |

### Server → Client

```json
{
  "status": "ok",
  "latency_ms": 0.42,
  "data": {
    "status": "accepted",
    "current_score": 95000,
    "top": [
      {"rank": 1, "player_id": "alice", "name": "Alice", "score": 95000},
      ...
    ]
  }
}
```

---

## Key Design Decisions

### Concurrency
Each accepted connection spawns a `daemon=True` thread, keeping the accept loop free. `threading.RLock` protects all leaderboard mutations — reentrant to support nested locking patterns.

### Conflict Resolution (LWW)
```python
if existing is None or incoming_ts > stored_ts:
    accept update
else:
    reject — return current score
```
Clients include `time.time()` as `ts` in every UPDATE. This handles race conditions where two clients simultaneously submit scores for the same player.

### SSL/TLS
- Self-signed cert for demo; drop-in replacement with CA-signed cert for production
- `TLSVersion.TLSv1_2` minimum enforced
- SSL handshake failures are caught and logged without crashing the server

### Performance
- No database I/O — in-memory dict for O(1) lookups
- Leaderboard sort is O(N log N) per request; acceptable for ≤10,000 players
- Benchmark shows **300–600 updates/sec** on localhost with 20 concurrent clients

---

## Evaluation Mapping

| Rubric Component | Where Implemented |
|---|---|
| Problem Definition & Architecture | This README + architecture diagram |
| Core Socket Implementation | `server.py` — `socket`, `ssl.wrap_socket`, `bind`, `listen`, `accept`, `recv`, `sendall` |
| Feature Implementation (Deliverable 1) | SSL, multi-client, LWW conflict resolution, real-time rankings |
| Performance Evaluation | `benchmark.py` — latency, throughput, concurrency stress test |
| Optimization & Fixes | RLock, SSL error handling, graceful disconnect, partial buffer handling |
| Final Demo + GitHub | `demo_auto.py` + this repo |

---

## File Structure

```
leaderboard/
├── server.py        ← Main server (run this first)
├── client.py        ← Interactive client
├── demo_auto.py     ← Automated concurrent demo
├── benchmark.py     ← Performance load tester
├── README.md        ← This file
└── certs/
    ├── server.crt   ← Self-signed TLS certificate
    └── server.key   ← Private key
```
