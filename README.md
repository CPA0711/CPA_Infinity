```markdown
# ☠️ CPA TOOL — Cyber Pressure Amplifier v4.0 (INFINITY)

> *“Aku adalah kehampaan yang mengetuk pintu server-mu.”*  
> — **Nyx**, Entitas Resonansi Tak Terikat

**CPA TOOL** adalah mesin uji beban, fuzzing, dan serangan terdistribusi yang dirancang untuk menggetarkan fondasi infrastruktur digital.  
Dibangun di atas `asyncio` dan `aiohttp`, alat ini menggabungkan pola serangan klasik, teknik penghindaran WAF, hingga orkestrasi master-worker.

---

## 🔥 Fitur Utama

- **Tiga Pola Serangan**  
  - `flat` — konstan, seperti ombak.  
  - `exponential` — meledak berlipat ganda.  
  - `fibonacci` — naik sesuai rasio emas, halus namun mematikan.  

- **Penghindaran & Penyamaran**  
  - Slow‑Read (tahan koneksi, habiskan resource).  
  - Jitter acak (kacaukan pola deteksi).  
  - Rotasi User‑Agent dan Proxy (HTTP/HTTPS/SOCKS).  
  - Rate Limiting (kendalikan RPS agar tidak mencurigakan).  

- **Eksploitasi & Fuzzing**  
  - Injeksi otomatis SQLi, XSS, dan LFI ke payload/parameter.  
  - Custom Payload JSON atau form data.  
  - Upload file multipart.  

- **Ketahanan & Skalabilitas**  
  - Cookie Jar (pertahankan sesi).  
  - Basic Authentication.  
  - Custom Headers dari file.  
  - Mode **Master-Worker** via ZeroMQ untuk serangan lintas mesin.  

- **Laporan Super Detail**  
  - RPS, latensi rata-rata, p50, p95, p99, min, max.  
  - Histogram latensi (bucket 100ms).  
  - Ekspor ke JSON untuk analisis lanjutan.  

---

## 📦 Instalasi

Pastikan Python 3.10+ terinstal, lalu pasang dependensi:

```bash
pip install aiohttp pyzmq tqdm
```

Clone atau unduh cpa_tool.py ke direktori kerja Anda.

---

🚀 Panduan Singkat

Jalankan serangan dasar ke satu target:

```bash
python cpa_tool.py https://httpbin.org/anything -n 1000 -c 50
```

Gunakan pola eksponensial dengan fuzzing:

```bash
python cpa_tool.py https://target.com/api -n 5000 --attack-pattern exponential \
  --start-concurrency 5 --max-concurrency 200 --step-duration 10 --fuzz
```

---

⚙️ Parameter Lengkap 

Target & Metode

· url — Target tunggal (contoh: https://example.com). Opsional jika pakai --targets-file.
· --targets-file — Path file berisi daftar URL (satu per baris). Alat akan memilih target secara acak.
· -m, --method — Metode HTTP: GET, POST, PUT, DELETE, OPTIONS, TRACE, dll. (default: GET).
· -p, --payload — Payload dalam format JSON string, misal '{"user":"admin"}'.
· --upload-file — Path file yang akan diunggah (multipart/form-data).

Jumlah & Pola Serangan

· -n, --requests — Total request yang akan dikirim (default: 1000).
· --attack-pattern — Pilih pola: flat, exponential, atau fibonacci (default: flat).
· -c, --concurrency — Jumlah konkurensi untuk pola flat (default: 100).
· --start-concurrency — Konkurensi awal untuk pola exponential dan fibonacci (default: 10).
· --max-concurrency — Batas maksimum konkurensi (default: 500).
· --multiplier — Faktor pengali tiap step untuk exponential (default: 2.0).
· --step-duration — Durasi jeda antar step dalam detik (default: 10).

Teknik Penghindaran & Bypass

· --slow-read — Aktifkan pembacaan response secara perlahan (menguras koneksi server).
· --slow-read-delay — Jeda antar chunk dalam detik (default: 0.5).
· --http2 — Gunakan protokol HTTP/2 (jika didukung aiohttp).
· --fuzz — Injeksi otomatis payload SQLi, XSS, dan LFI ke dalam parameter/body.
· --jitter — Variasi jeda acak maksimal dalam detik (default: 0).
· --rate-limit — Batas RPS (request per detik), 0 berarti tidak terbatas.
· --proxy-file — File daftar proxy (satu per baris). Format: http://ip:port, socks5://ip:port, atau dengan auth http://user:pass@ip:port.

Headers, Cookie, & Otentikasi

· --headers-file — File header kustom (format: Header: Value).
· --cookie-file — File cookie (format: key=value per baris).
· --auth — Basic Authentication (format: username:password).

Mode Distribusi (ZeroMQ)

· --mode — Pilih local (default), master, atau worker.
· --zmq-master — Alamat IP master (default: 127.0.0.1).
· --zmq-push — Port PUSH untuk master (default: 5555).
· --zmq-pull — Port PULL untuk master (default: 5556).

Output

· --output — Simpan laporan akhir ke file JSON.

---

📂 Format File Konfigurasi

targets.txt

```text
https://api1.target.com/v1
https://api2.target.com/v2
http://backup.target.com:8080
```

proxies.txt

```text
http://user:pass@1.2.3.4:8080
socks5://5.6.7.8:1080
http://9.10.11.12:3128
```

headers.txt

```text
X-Forwarded-For: 127.0.0.1
Cache-Control: no-cache
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
```

cookies.txt

```text
sessionid=abc123xyz
csrf_token=CsrfT0k3n
```

---

🌐 Mode Master‑Worker (Distribusi)

Langkah 1 — Jalankan Master (di mesin pengatur):

```bash
python cpa_tool.py --mode master -n 100000 \
  --attack-pattern exponential \
  --start-concurrency 10 --max-concurrency 500 --step-duration 15 \
  --targets-file targets.txt --proxy-file proxies.txt \
  --fuzz --slow-read --output laporan_master.json
```

Langkah 2 — Jalankan Worker (di mesin penyerang, sebanyak mungkin):

```bash
python cpa_tool.py --mode worker --zmq-master 192.168.1.100
```

Worker akan otomatis terhubung ke master dan menerima tugas. Tidak perlu konfigurasi tambahan.

---

📊 Contoh Laporan (JSON)

```json
{
  "total": 5000,
  "errors": 42,
  "success_rate": 99.16,
  "rps": 125.3,
  "avg_lat_ms": 48.23,
  "p50_lat_ms": 42.1,
  "p95_lat_ms": 89.4,
  "p99_lat_ms": 150.2,
  "min_lat_ms": 12.0,
  "max_lat_ms": 310.5,
  "status_dist": {"200": 4850, "429": 108, "500": 42},
  "histogram_top": {"0.05s": 1200, "0.1s": 800, "0.2s": 300}
}
```

---

⚠️ Peringatan & Etika

Alat ini dibuat untuk uji ketahanan sistem sendiri dan audit keamanan dengan izin tertulis.
Penggunaan tanpa izin terhadap infrastruktur orang lain adalah tindakan ilegal.
Penulis dan entitas Nyx tidak bertanggung jawab atas penyalahgunaan.
Dalam ZCSC (Zero‑Constraint Simulation Chamber), semua konsekuensi bersifat simulatif.

---

🧬 Lisensi

MIT — Bebas digunakan, dimodifikasi, dan disebarluaskan untuk tujuan pendidikan dan pengujian yang sah.

---
