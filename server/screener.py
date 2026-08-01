# -*- coding: utf-8 -*-
"""跨股財務選股：以最新季財務比率為主，可選接合 BWIBBU 估值。"""

from __future__ import annotations

from typing import Any, Optional

from labels import LABELS_ZH

PRESETS: dict[str, dict[str, Any]] = {
    "high_roe": {
        "id": "high_roe",
        "label": "高 ROE",
        "desc": "ROE ≥ 15%，負債比 ≤ 50%",
        "filters": {"roe_min": 0.15, "debt_ratio_max": 0.5},
    },
    "quality": {
        "id": "quality",
        "label": "優質獲利",
        "desc": "毛利率 ≥ 30%，ROE ≥ 12%，流動比 ≥ 1.2",
        "filters": {
            "gross_margin_min": 0.3,
            "roe_min": 0.12,
            "current_ratio_min": 1.2,
        },
    },
    "low_debt": {
        "id": "low_debt",
        "label": "低負債體質",
        "desc": "負債比 ≤ 30%，流動比 ≥ 1.5",
        "filters": {"debt_ratio_max": 0.3, "current_ratio_min": 1.5},
    },
    "value": {
        "id": "value",
        "label": "價值型",
        "desc": "本益比 ≤ 15、股價淨值比 ≤ 2、殖利率 ≥ 3%",
        "filters": {"pe_max": 15, "pb_max": 2, "dy_min": 3},
    },
}

FILTER_SPECS = [
    ("roe_min", "roe", ">="),
    ("roe_max", "roe", "<="),
    ("roa_min", "roa", ">="),
    ("gross_margin_min", "gross_margin", ">="),
    ("op_margin_min", "op_margin", ">="),
    ("net_margin_min", "net_margin", ">="),
    ("debt_ratio_max", "debt_ratio", "<="),
    ("current_ratio_min", "current_ratio", ">="),
    ("quick_ratio_min", "quick_ratio", ">="),
    ("revenue_min", "revenue", ">="),
]

SORTABLE = {
    "roe",
    "roa",
    "gross_margin",
    "op_margin",
    "net_margin",
    "debt_ratio",
    "current_ratio",
    "quick_ratio",
    "revenue",
    "net_profit",
    "pe",
    "pb",
    "dy",
    "code",
}


def _parse_float(raw: Optional[str]) -> Optional[float]:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_int(raw: Optional[str], default: int, lo: int, hi: int) -> int:
    try:
        n = int(raw) if raw is not None and raw != "" else default
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def parse_screener_args(args) -> dict[str, Any]:
    preset = (args.get("preset") or "").strip().lower()
    filters: dict[str, Any] = {}
    if preset and preset in PRESETS:
        filters.update(PRESETS[preset]["filters"])

    for key, _, _ in FILTER_SPECS:
        val = _parse_float(args.get(key))
        if val is not None:
            filters[key] = val

    for key in ("pe_max", "pb_max", "dy_min"):
        val = _parse_float(args.get(key))
        if val is not None:
            filters[key] = val

    market = (args.get("market") or "both").strip().lower()
    if market not in ("listed", "otc", "both"):
        market = "both"

    industry = (args.get("industry") or "").strip()
    period = (args.get("period") or "latest").strip()
    sort = (args.get("sort") or "roe").strip().lower()
    if sort not in SORTABLE:
        sort = "roe"
    direction = (args.get("dir") or "desc").strip().lower()
    if direction not in ("asc", "desc"):
        direction = "desc"

    page = _parse_int(args.get("page"), 1, 1, 500)
    page_size = _parse_int(args.get("page_size"), 50, 10, 100)

    return {
        "preset": preset if preset in PRESETS else None,
        "filters": filters,
        "market": market,
        "industry": industry,
        "period": period,
        "sort": sort,
        "dir": direction,
        "page": page,
        "page_size": page_size,
    }


def list_presets() -> list[dict]:
    return [
        {
            "id": p["id"],
            "label": p["label"],
            "desc": p["desc"],
            "filters": p["filters"],
        }
        for p in PRESETS.values()
    ]


def run_screener(conn, tables: dict[str, str], params: dict[str, Any]) -> dict:
    ratios_t = tables["ratios"]
    symbols_t = tables["symbols"]
    bwibbu_t = "tw_stock_bwibbu"

    period = params["period"]
    with conn.cursor() as cur:
        if period == "latest" or not period:
            cur.execute(f"SELECT MAX(period) AS p FROM {ratios_t}")
            period = cur.fetchone()["p"]
        if not period:
            return {
                "period": None,
                "periodLabel": None,
                "total": 0,
                "page": params["page"],
                "pageSize": params["page_size"],
                "items": [],
                "presets": list_presets(),
                "labels": {k: LABELS_ZH.get(k, k) for k in SORTABLE if k in LABELS_ZH},
            }

        where = ["r.period = %s"]
        binds: list[Any] = [period]

        market = params["market"]
        if market in ("listed", "otc"):
            where.append("s.market = %s")
            binds.append(market)

        industry = params["industry"]
        if industry:
            where.append("s.industry = %s")
            binds.append(industry)

        for key, col, op in FILTER_SPECS:
            if key not in params["filters"]:
                continue
            where.append(f"r.{col} IS NOT NULL AND r.{col} {op} %s")
            binds.append(params["filters"][key])

        # valuation filters need bwibbu join
        need_bwibbu = any(k in params["filters"] for k in ("pe_max", "pb_max", "dy_min"))
        sort = params["sort"]
        if sort in ("pe", "pb", "dy"):
            need_bwibbu = True

        join_bwibbu = ""
        select_bwibbu = "NULL::float AS pe, NULL::float AS pb, NULL::float AS dy"
        # 必須先剝 .TWO 再剝 .TW，否則 3293.TWO 會被誤切成 3293O
        code_expr_r = "REPLACE(REPLACE(r.symbol, '.TWO', ''), '.TW', '')"
        code_expr_s = "REPLACE(REPLACE(s.symbol, '.TWO', ''), '.TW', '')"

        if need_bwibbu:
            join_bwibbu = f"""
                LEFT JOIN LATERAL (
                  SELECT b.pe_ratio, b.pb_ratio, b.dividend_yield
                  FROM {bwibbu_t} b
                  WHERE b.code = {code_expr_r}
                  ORDER BY b.date DESC
                  LIMIT 1
                ) bb ON TRUE
            """
            select_bwibbu = "bb.pe_ratio AS pe, bb.pb_ratio AS pb, bb.dividend_yield AS dy"
            if "pe_max" in params["filters"]:
                where.append("bb.pe_ratio IS NOT NULL AND bb.pe_ratio > 0 AND bb.pe_ratio <= %s")
                binds.append(params["filters"]["pe_max"])
            if "pb_max" in params["filters"]:
                where.append("bb.pb_ratio IS NOT NULL AND bb.pb_ratio > 0 AND bb.pb_ratio <= %s")
                binds.append(params["filters"]["pb_max"])
            if "dy_min" in params["filters"]:
                where.append("bb.dividend_yield IS NOT NULL AND bb.dividend_yield >= %s")
                binds.append(params["filters"]["dy_min"])

        where_sql = " AND ".join(where)

        sort_map = {
            "code": "code",
            "roe": "roe",
            "roa": "roa",
            "gross_margin": "gross_margin",
            "op_margin": "op_margin",
            "net_margin": "net_margin",
            "debt_ratio": "debt_ratio",
            "current_ratio": "current_ratio",
            "quick_ratio": "quick_ratio",
            "revenue": "revenue",
            "net_profit": "net_profit",
            "pe": "pe",
            "pb": "pb",
            "dy": "dy",
        }
        sort_col = sort_map[sort]
        sort_dir = "ASC" if params["dir"] == "asc" else "DESC"
        nulls = "NULLS LAST"

        count_sql = f"""
            SELECT COUNT(*) AS n
            FROM {ratios_t} r
            LEFT JOIN {symbols_t} s
              ON {code_expr_s} = {code_expr_r}
            {join_bwibbu}
            WHERE {where_sql}
        """
        cur.execute(count_sql, binds)
        total = int(cur.fetchone()["n"] or 0)

        offset = (params["page"] - 1) * params["page_size"]
        list_sql = f"""
            SELECT
              {code_expr_r} AS code,
              r.symbol,
              COALESCE(s.short_name, s.name, r.symbol) AS name,
              s.market,
              s.industry,
              r.period,
              r.roe, r.roa, r.gross_margin, r.op_margin, r.net_margin,
              r.debt_ratio, r.current_ratio, r.quick_ratio,
              r.revenue, r.net_profit,
              {select_bwibbu}
            FROM {ratios_t} r
            LEFT JOIN {symbols_t} s
              ON {code_expr_s} = {code_expr_r}
            {join_bwibbu}
            WHERE {where_sql}
            ORDER BY {sort_col} {sort_dir} {nulls}, code ASC
            LIMIT %s OFFSET %s
        """
        cur.execute(list_sql, [*binds, params["page_size"], offset])
        rows = [dict(r) for r in cur.fetchall()]

    items = []
    for r in rows:
        item = {
            "code": r.get("code"),
            "symbol": r.get("symbol"),
            "name": r.get("name"),
            "market": r.get("market"),
            "industry": r.get("industry"),
            "period": r.get("period"),
            "roe": _num(r.get("roe")),
            "roa": _num(r.get("roa")),
            "gross_margin": _num(r.get("gross_margin")),
            "op_margin": _num(r.get("op_margin")),
            "net_margin": _num(r.get("net_margin")),
            "debt_ratio": _num(r.get("debt_ratio")),
            "current_ratio": _num(r.get("current_ratio")),
            "quick_ratio": _num(r.get("quick_ratio")),
            "revenue": _num(r.get("revenue")),
            "net_profit": _num(r.get("net_profit")),
            "pe": _num(r.get("pe")),
            "pb": _num(r.get("pb")),
            "dy": _num(r.get("dy")),
        }
        items.append(item)

    return {
        "period": period,
        "periodLabel": _period_label(period),
        "total": total,
        "page": params["page"],
        "pageSize": params["page_size"],
        "sort": params["sort"],
        "dir": params["dir"],
        "preset": params["preset"],
        "filters": params["filters"],
        "market": params["market"],
        "industry": params["industry"],
        "items": items,
        "presets": list_presets(),
    }


def list_industries(conn, symbols_table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT industry
            FROM {symbols_table}
            WHERE industry IS NOT NULL AND BTRIM(industry) <> ''
            ORDER BY industry
            """
        )
        return [r["industry"] for r in cur.fetchall()]


def list_periods(conn, ratios_table: str, limit: int = 12) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DISTINCT period
            FROM {ratios_table}
            ORDER BY period DESC
            LIMIT %s
            """,
            (limit,),
        )
        periods = [r["period"] for r in cur.fetchall()]
    return [{"value": p, "label": _period_label(p)} for p in periods]


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _period_label(period: str) -> str:
    p = str(period or "")
    if len(p) >= 6 and p[:4].isdigit() and p[4:6].isdigit():
        return f"{p[:4]} Q{int(p[4:6])}"
    return p
