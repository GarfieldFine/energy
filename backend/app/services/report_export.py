from __future__ import annotations

import io
import pandas as pd

from app.services.energy_store import load_energy


def period_summary_csv(
    building_id: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
) -> tuple[str, bytes]:
    """导出时段内原始小时级明细 CSV（演示报表）。"""
    df = load_energy()
    if building_id:
        df = df[df["building_id"] == building_id]
    if time_from:
        df = df[df["monitor_time"] >= pd.to_datetime(time_from)]
    if time_to:
        df = df[df["monitor_time"] <= pd.to_datetime(time_to)]
    df = df.sort_values("monitor_time")
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    raw = buf.getvalue().encode("utf-8-sig")
    name = f"energy_export_{building_id or 'all'}.csv"
    return name, raw
