"""
本地联调：模拟外部能耗 API（返回 CSV 末 48 行 JSON）。

用法（在 backend 目录）：
  python scripts/mock_energy_api.py
  # 默认 http://127.0.0.1:9876/energy/latest

在 backend/.env 中配置：
  ENERGY_API_URL=http://127.0.0.1:9876/energy/latest
  ENERGY_SYNC_INTERVAL_SEC=60
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.dataset_paths import energy_csv_path  # noqa: E402

import pandas as pd  # noqa: E402

HOST = "127.0.0.1"
PORT = 9876
TAIL_ROWS = 48


def _payload() -> bytes:
    path = energy_csv_path()
    if not path.is_file():
        body = {"items": []}
    else:
        df = pd.read_csv(path, encoding="utf-8-sig")
        df = df.tail(TAIL_ROWS)
        df["monitor_time"] = pd.to_datetime(df["monitor_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        body = {"items": df.fillna("").to_dict(orient="records")}
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/energy/latest", "/"):
            self.send_response(404)
            self.end_headers()
            return
        data = _payload()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[mock-energy-api] {self.address_string()} {fmt % args}")


def main() -> None:
    server = HTTPServer((HOST, PORT), Handler)
    print(f"mock energy API on http://{HOST}:{PORT}/energy/latest")
    print("Set ENERGY_API_URL to the URL above and restart backend.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
