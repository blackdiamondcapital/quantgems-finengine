# -*- coding: utf-8 -*-
"""跨股財務選股：以最新季財務比率為主，可選接合 BWIBBU 估值。"""

from __future__ import annotations

from typing import Any, Optional

from labels import LABELS_ZH, RATIO_KEYS, RATIO_UNITS

PRESETS: dict[str, dict[str, Any]] = {
    "high_roe": {
        "id": "high_roe",
        "label": "高 ROE",
        "desc": "ROE ≥ 15%，負債比 ≤ 50%",
        "filters": {"roe_min": 0.15, "debt_ratio_max": 0.5},
    },
    "roe_streak2": {
        "id": "roe_streak2",
        "label": "連續兩季高 ROE",
        "desc": "連續兩季 ROE ≥ 15%",
        "filters": {"roe_min": 0.15, "roe_min_streak": 2},
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
    "cashflow_quality": {
        "id": "cashflow_quality",
        "label": "現金流品質",
        "desc": "營業現金流／淨利 ≥ 1 倍，自由現金流率 ≥ 5%",
        "filters": {
            "operating_cash_to_net_income_min": 1,
            "free_cash_flow_margin_min": 0.05,
        },
    },
    "high_roic": {
        "id": "high_roic",
        "label": "高 ROIC",
        "desc": "ROIC ≥ 12%，利息保障倍數 ≥ 5 倍",
        "filters": {"roic_min": 0.12, "interest_coverage_min": 5},
    },
    "operating_efficiency": {
        "id": "operating_efficiency",
        "label": "營運效率",
        "desc": "資產週轉率 ≥ 0.8 倍，現金轉換週期 ≤ 120 天",
        "filters": {"asset_turnover_min": 0.8, "cash_conversion_cycle_max": 120},
    },
    "growth_quality": {
        "id": "growth_quality",
        "label": "成長品質",
        "desc": "營收與 EPS 年增 ≥ 10%，自由現金流率 ≥ 5%",
        "filters": {
            "revenue_yoy_min": 0.1,
            "eps_yoy_min": 0.1,
            "free_cash_flow_margin_min": 0.05,
        },
    },
}

FILTERABLE_COLUMNS = [*RATIO_KEYS, "revenue", "net_profit"]
FILTER_SPECS = [
    spec
    for column in FILTERABLE_COLUMNS
    for spec in (
        (f"{column}_min", column, ">="),
        (f"{column}_max", column, "<="),
    )
]

SORTABLE = {
    *RATIO_KEYS,
    "revenue",
    "net_profit",
    "pe",
    "pb",
    "dy",
    "code",
}

RESULT_FIELDS = [*RATIO_KEYS, "revenue", "net_profit"]


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


def _prev_period(period: str) -> Optional[str]:
    """YYYYQQ（如 202501）→ 上一季（202404）。"""
    p = str(period or "")
    if len(p) < 6 or not p[:4].isdigit() or not p[4:6].isdigit():
        return None
    year = int(p[:4])
    quarter = int(p[4:6])
    if quarter < 1 or quarter > 4:
        return None
    if quarter <= 1:
        return f"{year - 1}04"
    return f"{year}{quarter - 1:02d}"


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

    # 連續 N 季 ROE：query 可覆寫 preset
    streak_raw = args.get("roe_min_streak")
    if streak_raw is not None and str(streak_raw).strip() != "":
        streak = _parse_int(streak_raw, 0, 0, 8)
        if streak >= 2:
            filters["roe_min_streak"] = streak
        else:
            filters.pop("roe_min_streak", None)
    elif "roe_min_streak" in filters:
        streak = int(filters.get("roe_min_streak") or 0)
        if streak < 2:
            filters.pop("roe_min_streak", None)

    # 勾選連續兩季但未給 ROE 門檻時，預設 15%
    if int(filters.get("roe_min_streak") or 0) >= 2 and "roe_min" not in filters:
        filters["roe_min"] = 0.15

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


def ratio_table_columns(conn, table: str) -> set[str]:
    """讀取實際 schema，讓尚未 migration 的資料庫也能安全查詢。"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        return {r["column_name"] for r in cur.fetchall()}


def schema_column_expr(column: str, available: set[str], alias: str = "r") -> str:
    if column in available:
        return f'{alias}."{column}"'
    return "NULL::numeric"


def run_screener(conn, tables: dict[str, str], params: dict[str, Any]) -> dict:
    ratios_t = tables["ratios"]
    symbols_t = tables["symbols"]
    bwibbu_t = "tw_stock_bwibbu"
    available = ratio_table_columns(conn, ratios_t)

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
            if col not in available:
                where.append("FALSE")
                continue
            where.append(f'r."{col}" IS NOT NULL AND r."{col}" {op} %s')
            binds.append(params["filters"][key])

        # 連續兩季（或以上）ROE：當季已由 roe_min 約束，再要求前一季達標
        streak = int(params["filters"].get("roe_min_streak") or 0)
        if streak >= 2:
            if "roe" not in available:
                where.append("FALSE")
                streak = 0
            roe_floor = params["filters"].get("roe_min")
            if roe_floor is None:
                roe_floor = 0.15
            prev = _prev_period(str(period))
            if prev and streak >= 2:
                where.append(
                    f"""EXISTS (
                      SELECT 1 FROM {ratios_t} r_prev
                      WHERE r_prev.symbol = r.symbol
                        AND r_prev.period = %s
                        AND r_prev.roe IS NOT NULL
                        AND r_prev.roe >= %s
                    )"""
                )
                binds.extend([prev, roe_floor])
            else:
                # 無法推算上一季 → 不通過任何人
                where.append("FALSE")

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

        if sort == "code":
            sort_col = "code"
        elif sort in ("pe", "pb", "dy"):
            sort_col = sort
        else:
            sort_col = schema_column_expr(sort, available)
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
        ratio_select = ",\n              ".join(
            f'{schema_column_expr(field, available)} AS "{field}"'
            for field in RESULT_FIELDS
        )
        list_sql = f"""
            SELECT
              {code_expr_r} AS code,
              r.symbol,
              COALESCE(s.short_name, s.name, r.symbol) AS name,
              s.market,
              s.industry,
              r.period,
              {ratio_select},
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
            "pe": _num(r.get("pe")),
            "pb": _num(r.get("pb")),
            "dy": _num(r.get("dy")),
        }
        item.update({field: _num(r.get(field)) for field in RESULT_FIELDS})
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
        "fieldMeta": {
            key: {"label": LABELS_ZH.get(key, key), "unit": RATIO_UNITS.get(key)}
            for key in RATIO_KEYS
        },
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
