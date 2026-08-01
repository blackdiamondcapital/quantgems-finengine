# -*- coding: utf-8 -*-
"""損益表單季／累計轉換。

台股季報慣例：Q1–Q3 為當季單季數，Q4 為當年度累計（全年）。
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from typing import Any, Optional

from labels import EPS_KEYS

META_COLS = {"股票代號", "period", "created_at", "updated_at"}


def parse_period(period: str) -> tuple[str, int]:
    p = str(period or "")
    if len(p) >= 6 and p[:4].isdigit() and p[4:6].isdigit():
        return p[:4], int(p[4:6])
    return p, 0


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _implied_shares(net: Optional[float], eps: Optional[float]) -> Optional[float]:
    if net is None or eps is None or eps == 0:
        return None
    return net / eps


def _eps_from_net(net: Optional[float], shares: Optional[float]) -> Optional[float]:
    if net is None or shares is None or shares == 0:
        return None
    return net / shares


def _numeric_keys(row: dict) -> list[str]:
    keys = []
    for k, v in row.items():
        if k in META_COLS or k in EPS_KEYS:
            continue
        if _to_float(v) is not None:
            keys.append(k)
    return keys


def _group_rows_by_year(rows: list[dict]) -> dict[str, dict[int, dict]]:
    grouped: dict[str, dict[int, dict]] = defaultdict(dict)
    for row in rows:
        year, quarter = parse_period(row.get("period"))
        if 1 <= quarter <= 4:
            grouped[year][quarter] = row
    return grouped


def _shares_for_year(year_rows: dict[int, dict]) -> Optional[float]:
    for q in (1, 2, 3):
        row = year_rows.get(q)
        if not row:
            continue
        for eps_key in EPS_KEYS:
            eps = _to_float(row.get(eps_key))
            net = _to_float(row.get("ProfitLoss"))
            shares = _implied_shares(net, eps)
            if shares:
                return shares
    row = year_rows.get(4)
    if row:
        for eps_key in EPS_KEYS:
            eps = _to_float(row.get(eps_key))
            net = _to_float(row.get("ProfitLoss"))
            shares = _implied_shares(net, eps)
            if shares:
                return shares
    return None


def _apply_eps(
    target: dict,
    year_rows: dict[int, dict],
    *,
    basis: str,
    quarter: int,
) -> None:
    shares = _shares_for_year(year_rows)
    if not shares:
        return

    if basis == "single":
        if quarter == 4:
            net = _to_float(target.get("ProfitLoss"))
            for eps_key in EPS_KEYS:
                val = _eps_from_net(net, shares)
                if val is not None:
                    target[eps_key] = val
        return

    nets = [
        _to_float(year_rows.get(q, {}).get("ProfitLoss"))
        for q in range(1, quarter + 1)
        if q in year_rows
    ]
    if quarter == 4:
        net = _to_float(target.get("ProfitLoss"))
    elif nets and all(v is not None for v in nets):
        net = sum(nets)
    else:
        return

    for eps_key in EPS_KEYS:
        val = _eps_from_net(net, shares)
        if val is not None:
            target[eps_key] = val


def ensure_income_year_context(
    rows: list[dict],
    extra_rows: list[dict] | None = None,
) -> list[dict]:
    """合併同年度其他季別，供換算使用。"""
    merged: dict[str, dict] = {str(r.get("period")): r for r in rows}
    if extra_rows:
        for r in extra_rows:
            merged[str(r.get("period"))] = r
    return sorted(
        merged.values(),
        key=lambda r: str(r.get("period") or ""),
        reverse=True,
    )


def transform_income_rows(rows: list[dict], basis: str = "single") -> list[dict]:
    """basis: single（單季）| cumulative（累計）"""
    if not basis or basis == "raw":
        return rows
    if basis not in ("single", "cumulative"):
        basis = "single"
    if not rows:
        return rows

    requested_periods = {str(r.get("period")) for r in rows}
    grouped = _group_rows_by_year(rows)
    numeric_keys = _numeric_keys(rows[0])
    output: list[dict] = []

    for row in rows:
        year, quarter = parse_period(row.get("period"))
        year_rows = grouped.get(year, {})
        converted = deepcopy(row)

        if basis == "single":
            if quarter == 4 and all(q in year_rows for q in (1, 2, 3)):
                for key in numeric_keys:
                    annual = _to_float(row.get(key))
                    if annual is None:
                        continue
                    partial = sum(
                        _to_float(year_rows[q].get(key)) or 0.0 for q in (1, 2, 3)
                    )
                    converted[key] = annual - partial
                _apply_eps(converted, year_rows, basis="single", quarter=4)
        else:
            if 1 <= quarter <= 3:
                if all(q in year_rows for q in range(1, quarter + 1)):
                    for key in numeric_keys:
                        vals = [
                            _to_float(year_rows[q].get(key))
                            for q in range(1, quarter + 1)
                        ]
                        if vals and all(v is not None for v in vals):
                            converted[key] = sum(vals)
                    _apply_eps(converted, year_rows, basis="cumulative", quarter=quarter)

        output.append(converted)

    return [r for r in output if str(r.get("period")) in requested_periods]
