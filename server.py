"""
Distributed Leaderboard Server
================================
TCP + SSL/TLS secured server with:
  - Concurrent client handling (threading)
  - Thread-safe score updates with RLock
  - Last-Write-Wins (LWW) conflict resolution using timestamps
  - Real-time leaderboard broadcast to all connected clients
  - Performance metrics: latency, throughput, update rate
"""

import socket, ssl, threading, json, time, logging

HOST, PORT   = "0.0.0.0", 9443
CERTFILE     = "certs/server.crt"
KEYFILE      = "certs/server.key"
TOP_N        = 10
MAX_CLIENTS  = 50

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("server")


class LeaderboardEngine:
    """Thread-safe leaderboard with Last-Write-Wins (LWW) conflict resolution."""

    def __init__(self):
        self._scores = {}
        self._lock   = threading.RLock()
        self._update_count = 0
        self._start_time   = time.time()

    def update(self, player_id, name, score, timestamp):
        """Accept update only if timestamp is newer (LWW)."""
        with self._lock:
            existing = self._scores.get(player_id)
            if existing is None or timestamp > existing["ts"]:
                self._scores[player_id] = {"score": score, "name": name, "ts": timestamp}
                self._update_count += 1
                return {"status": "accepted", "current_score": score}
            return {"status": "rejected", "current_score": existing["score"]}

    def get_top(self, n=TOP_N):
        with self._lock:
            ranked = sorted(
                [{"rank": 0, "player_id": pid, "name": d["name"], "score": d["score"]}
                 for pid, d in self._scores.items()],
                key=lambda x: x["score"], reverse=True
            )
            for i, e in enumerate(ranked[:n], 1):
                e["rank"] = i
            return ranked[:n]

    def get_player(self, player_id):
        with self._lock:
            return self._scores.get(player_id)

    def stats(self):
        elapsed = time.time() - self._start_time
        with self._lock:
            return {
                "total_players"   : len(self._scores),
                "total_updates"   : self._update_count,
                "uptime_seconds"  : round(elapsed, 2),
                "updates_per_sec" : round(self._update_count / max(elapsed, 1), 2),
            }


class ClientHandler(threading.Thread):
    """
    One thread per SSL client. Protocol: newline-delimited JSON.

    Commands:
      UPDATE     { cmd, player_id, name, score, ts }
      GET_TOP    { cmd, n? }
      GET_PLAYER { cmd, player_id }
      STATS      { cmd }
      PING       { cmd }
    """

    def __init__(self, conn, addr, engine, registry):
        super().__init__(daemon=True)
        self.conn, self.addr = conn, addr
        self.engine, self.registry = engine, registry

    def run(self):
        log.info(f"Client connected: {self.addr}")
        self.registry[self.addr] = self.conn
        try:
            buf = ""
            while True:
                chunk = self.conn.recv(4096).decode("utf-8")
                if not chunk:
                    break
                buf += chunk
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    if line.strip():
                        self._send(self._handle(line.strip()))
        except Exception as e:
            if not isinstance(e, (ssl.SSLError, ConnectionResetError, BrokenPipeError)):
                log.warning(f"Error {self.addr}: {e}")
        finally:
            self.registry.pop(self.addr, None)
            try: self.conn.close()
            except: pass
            log.info(f"Client disconnected: {self.addr}")

    def _handle(self, raw):
        t0 = time.perf_counter()
        try:
            msg = json.loads(raw)
            cmd = msg.get("cmd", "").upper()
            if cmd == "UPDATE":
                result = self.engine.update(
                    msg["player_id"], msg.get("name", msg["player_id"]),
                    int(msg["score"]), float(msg.get("ts", time.time()))
                )
                data = {**result, "top": self.engine.get_top(TOP_N)}
            elif cmd == "GET_TOP":
                data = {"top": self.engine.get_top(int(msg.get("n", TOP_N)))}
            elif cmd == "GET_PLAYER":
                p = self.engine.get_player(msg["player_id"])
                data = p if p else {"error": "player not found"}
            elif cmd == "STATS":
                data = self.engine.stats()
            elif cmd == "PING":
                data = {"pong": True, "server_time": time.time()}
            else:
                data = {"error": f"unknown command: {cmd}"}
            return {"status": "ok", "latency_ms": round((time.perf_counter()-t0)*1000, 3), "data": data}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _send(self, obj):
        try: self.conn.sendall((json.dumps(obj) + "\n").encode())
        except: pass


class LeaderboardServer:
    def __init__(self):
        self.engine  = LeaderboardEngine()
        self.clients = {}

    def run(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERTFILE, KEYFILE)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        raw.bind((HOST, PORT))
        raw.listen(MAX_CLIENTS)
        log.info(f"Leaderboard Server on {HOST}:{PORT} (TLS 1.2+)")

        threading.Thread(target=self._stats_loop, daemon=True).start()

        with ctx.wrap_socket(raw, server_side=True) as tls:
            while True:
                try:
                    conn, addr = tls.accept()
                    ClientHandler(conn, addr, self.engine, self.clients).start()
                except ssl.SSLError as e:
                    log.warning(f"SSL handshake failed: {e}")
                except KeyboardInterrupt:
                    break
        log.info("Server stopped.")

    def _stats_loop(self):
        while True:
            time.sleep(10)
            s = self.engine.stats()
            log.info(f"STATS | Players:{s['total_players']} Updates:{s['total_updates']} "
                     f"Rate:{s['updates_per_sec']}/s Clients:{len(self.clients)}")


if __name__ == "__main__":
    LeaderboardServer().run()
