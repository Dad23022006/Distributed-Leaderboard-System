"""
Distributed Leaderboard Client
================================
Interactive CLI client with SSL/TLS connection to the leaderboard server.
"""

import socket, ssl, json, time, threading

HOST     = "127.0.0.1"
PORT     = 9443
CERTFILE = "certs/server.crt"


class LeaderboardClient:
    def __init__(self, host=HOST, port=PORT):
        self.host, self.port = host, port
        self._sock = None
        self._buf  = ""
        self._lock = threading.Lock()

    def connect(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE   # self-signed cert; use CA cert in production
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock = ctx.wrap_socket(raw, server_hostname=self.host)
        self._sock.connect((self.host, self.port))
        print(f"[+] Connected to {self.host}:{self.port} over TLS")

    def close(self):
        if self._sock:
            self._sock.close()

    def _send_recv(self, obj):
        with self._lock:
            self._sock.sendall((json.dumps(obj) + "\n").encode())
            while "\n" not in self._buf:
                chunk = self._sock.recv(4096).decode()
                if not chunk:
                    raise ConnectionError("Server closed connection")
                self._buf += chunk
            line, self._buf = self._buf.split("\n", 1)
            return json.loads(line)

    def ping(self):
        return self._send_recv({"cmd": "PING"})

    def update_score(self, player_id, name, score):
        return self._send_recv({"cmd": "UPDATE", "player_id": player_id,
                                 "name": name, "score": score, "ts": time.time()})

    def get_top(self, n=10):
        return self._send_recv({"cmd": "GET_TOP", "n": n})

    def get_player(self, player_id):
        return self._send_recv({"cmd": "GET_PLAYER", "player_id": player_id})

    def get_stats(self):
        return self._send_recv({"cmd": "STATS"})


def print_leaderboard(top):
    print("\n" + "=" * 42)
    print(f"{'🏆  LEADERBOARD':^42}")
    print("=" * 42)
    print(f"{'#':<4} {'Name':<20} {'Score':>8}")
    print("-" * 42)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for e in top:
        medal = medals.get(e["rank"], "  ")
        print(f"{medal} {e['rank']:<2} {e['name']:<20} {e['score']:>8}")
    print("=" * 42 + "\n")


def interactive_menu(client):
    print("\n=== Distributed Leaderboard Client ===")
    player_id = input("Enter your player ID: ").strip() or "player_1"
    name      = input("Enter your display name: ").strip() or player_id

    while True:
        print("\n[1] Submit score   [2] View leaderboard   [3] Lookup player")
        print("[4] Server stats   [5] Ping               [Q] Quit")
        choice = input("Choice: ").strip().lower()

        if choice == "1":
            try:
                score = int(input("Enter score: ").strip())
                resp  = client.update_score(player_id, name, score)
                d     = resp.get("data", {})
                print(f"[{d.get('status','?').upper()}] Score: {d.get('current_score')}  | {resp.get('latency_ms')} ms")
                if d.get("top"):
                    print_leaderboard(d["top"])
            except ValueError:
                print("Invalid score.")
        elif choice == "2":
            print_leaderboard(client.get_top(10)["data"]["top"])
        elif choice == "3":
            pid  = input("Player ID: ").strip()
            d    = client.get_player(pid)["data"]
            if "error" in d: print(f"  {d['error']}")
            else: print(f"  {d['name']}: {d['score']}")
        elif choice == "4":
            s = client.get_stats()["data"]
            print(f"\n  Players:{s['total_players']} Updates:{s['total_updates']} Rate:{s['updates_per_sec']}/s Uptime:{s['uptime_seconds']}s")
        elif choice == "5":
            t0 = time.time()
            resp = client.ping()
            print(f"  PONG! RTT={round((time.time()-t0)*1000,2)}ms  Server={resp.get('latency_ms')}ms")
        elif choice in ("q", "quit", "exit"):
            print("Goodbye!")
            break
        else:
            print("Unknown option.")


if __name__ == "__main__":
    c = LeaderboardClient()
    try:
        c.connect()
        interactive_menu(c)
    except ConnectionRefusedError:
        print(f"[!] Cannot connect to {HOST}:{PORT}. Is the server running?")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        c.close()
