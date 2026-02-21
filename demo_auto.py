"""
Automated Demo Script
=======================
Simulates 10 players submitting scores concurrently, then prints final leaderboard.
"""

import socket, ssl, json, time, threading, random

HOST = "127.0.0.1"; PORT = 9443

PLAYERS = [("alice","Alice"),("bob","Bob"),("carol","Carol"),("dave","Dave"),
           ("eve","Eve"),("frank","Frank"),("grace","Grace"),("hiro","Hiro"),
           ("isha","Isha"),("jay","Jay")]


def make_client():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    raw = socket.socket(); sock = ctx.wrap_socket(raw, server_hostname=HOST)
    sock.connect((HOST, PORT)); return sock


def sr(sock, obj):
    sock.sendall((json.dumps(obj)+"\n").encode())
    buf=""
    while "\n" not in buf: buf += sock.recv(4096).decode()
    return json.loads(buf.split("\n")[0])


def player_thread(pid, name, n_rounds, barrier, log):
    sock = make_client()
    barrier.wait()
    for _ in range(n_rounds):
        score = random.randint(1000, 99999)
        resp  = sr(sock, {"cmd":"UPDATE","player_id":pid,"name":name,"score":score,"ts":time.time()})
        log.append(f"  {name:10s} → {score:>6}  [{resp['data']['status']}]")
        time.sleep(random.uniform(0.02, 0.1))
    sock.close()


def main():
    print("=== Automated Leaderboard Demo ===\n")
    log, threads = [], []
    barrier = threading.Barrier(len(PLAYERS))

    for pid, name in PLAYERS:
        t = threading.Thread(target=player_thread, args=(pid, name, 5, barrier, log))
        t.start(); threads.append(t)
    for t in threads: t.join()

    print("Score updates submitted:")
    for line in sorted(log): print(line)

    sock = make_client()
    top  = sr(sock, {"cmd":"GET_TOP","n":10})["data"]["top"]
    sock.close()

    print("\n" + "="*45)
    print(f"{'🏆  FINAL LEADERBOARD':^45}")
    print("="*45)
    medals = {1:"🥇",2:"🥈",3:"🥉"}
    for e in top:
        print(f"  {medals.get(e['rank'],'  ')} #{e['rank']:<2}  {e['name']:<15} {e['score']:>8}")
    print("="*45)

    sock = make_client()
    s = sr(sock, {"cmd":"STATS"})["data"]; sock.close()
    print(f"\n  Stats: {s['total_updates']} updates | {s['updates_per_sec']}/s | uptime {s['uptime_seconds']}s\n")


if __name__ == "__main__":
    main()
