# -*- coding: utf-8 -*-
"""QuantGems 財報引擎 — 讀取 Neon 季報資料的 API。"""

from __future__ import annotations

import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS
from psycopg2.extras import RealDictCursor

from labels import (
    EMPHASIS_KEYS,
    EPS_KEYS,
    LABELS_ZH,
    RATIO_KEYS,
    RATIO_MULTIPLE_KEYS,
    RATIO_SECTIONS,
    INCOME_LINKED_RATIO_KEYS,
)
from fields import (
    build_statement_sections,
    fields_meta,
    filter_balance_columns,
    label_for,
    load_catalog,
)
from income_basis import ensure_income_year_context, parse_period, transform_income_rows
from screener import (
    list_industries,
    list_periods,
    list_presets,
    parse_screener_args,
    run_screener,
)

# 綜合報表：三表精選科目
COMBINED_SECTIONS = [
    (
        "income",
        "損益精選",
        [
            "Revenue",
            "OperatingCosts",
            "GrossProfitFromOperations",
            "ProfitLossFromOperatingActivities",
            "ProfitLossBeforeTax",
            "ProfitLoss",
            "BasicEarningsLossPerShareTotal",
            "DilutedEarningsLossPerShareTotal",
        ],
    ),
    (
        "balance",
        "資產負債精選",
        [
            "CashAndCashEquivalents",
            "CurrentAssets",
            "NoncurrentAssets",
            "Assets",
            "CurrentLiabilities",
            "Liabilities",
            "Equity",
            "EquityAndLiabilities",
        ],
    ),
    (
        "cashflow",
        "現金流精選",
        [
            "NetCashFlowsFromUsedInOperatingActivities",
            "NetCashFlowsFromUsedInInvestingActivities",
            "NetCashFlowsFromUsedInFinancingActivities",
            "NetIncreaseDecreaseInCashAndCashEquivalents",
            "CashAndCashEquivalentsAtEndOfPeriod",
        ],
    ),
]

ROOT = Path(__file__).resolve().parents[1]
PARENT_ENV = ROOT.parent / ".env"
LOCAL_ENV = ROOT / ".env"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    if PARENT_ENV.exists():
        load_dotenv(PARENT_ENV)
    if LOCAL_ENV.exists():
        load_dotenv(LOCAL_ENV, override=True)


_load_env()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

TABLES = {
    "income": os.getenv("NEON_INCOME_STATEMENT_TABLE")
    or os.getenv("INCOME_STATEMENT_TABLE")
    or "tw_income_statement",
    "balance": os.getenv("NEON_BALANCE_SHEET_TABLE")
    or os.getenv("BALANCE_SHEET_TABLE")
    or "tw_balance_sheet",
    "cashflow": os.getenv("NEON_CASH_FLOW_TABLE")
    or os.getenv("CASH_FLOW_TABLE")
    or "tw_cash_flow_statement",
    "ratios": os.getenv("NEON_FINANCIAL_RATIOS_TABLE")
    or os.getenv("FINANCIAL_RATIOS_TABLE")
    or "tw_financial_ratios",
    "symbols": os.getenv("SYMBOLS_TABLE") or "tw_stock_symbols",
}


def get_conn():
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")
    if url:
        return psycopg2.connect(url, cursor_factory=RealDictCursor)
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        dbname=os.getenv("DB_NAME", "postgres"),
        cursor_factory=RealDictCursor,
    )


def normalize_code(raw: str) -> str:
    s = (raw or "").strip().upper()
    s = s.replace(".TW", "").replace(".TWO", "")
    s = re.sub(r"[^0-9A-Z]", "", s)
    return s


def ratio_symbol(code: str) -> str:
    return f"{code}.TW"


def to_number(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def safe_div(numerator: Any, denominator: Any) -> Optional[float]:
    num = to_number(numerator)
    den = to_number(denominator)
    if num is None or den is None or den == 0:
        return None
    return num / den


def enrich_highlight_ratios(hl: dict, ratio_row: Optional[dict] = None) -> dict:
    """以 highlight 同期財報計算比率；ratios 表有值時優先採用。"""
    computed = {
        "gross_margin": safe_div(hl.get("gross_profit"), hl.get("revenue")),
        "op_margin": safe_div(hl.get("op_profit"), hl.get("revenue")),
        "net_margin": safe_div(hl.get("net_profit"), hl.get("revenue")),
        "roa": safe_div(hl.get("net_profit"), hl.get("assets")),
        "roe": safe_div(hl.get("net_profit"), hl.get("equity")),
        "debt_ratio": safe_div(hl.get("liabilities"), hl.get("assets")),
    }
    same_period = (
        ratio_row
        and str(ratio_row.get("period") or "") == str(hl.get("period") or "")
    )
    for key, val in computed.items():
        from_table = ratio_row.get(key) if same_period and ratio_row else None
        hl[key] = to_number(from_table) if from_table is not None else val
    return hl


def period_label(period: str) -> str:
    p = str(period or "")
    if len(p) >= 6 and p[:4].isdigit() and p[4:6].isdigit():
        y, s = p[:4], int(p[4:6])
        if 1 <= s <= 4:
            return f"{y} Q{s}"
    return p


def serialize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k in ("created_at", "updated_at"):
            out[k] = v.isoformat() if v else None
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


_schema_cache: dict[str, list[str]] = {}


def table_columns(table: str) -> list[str]:
    if table in _schema_cache:
        return _schema_cache[table]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            )
            cols = [r["column_name"] for r in cur.fetchall()]
    data_cols = [c for c in cols if c not in {"股票代號", "period", "created_at", "updated_at"}]
    _schema_cache[table] = data_cols
    return data_cols


@app.get("/api/health")
def health():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                cur.fetchone()
        return jsonify({"ok": True, "service": "quantgems-finengine"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.get("/api/meta")
def meta():
    catalog = load_catalog()
    fields = fields_meta()
    db_counts = {}
    for kind in ("income", "balance", "cashflow"):
        try:
            cols = table_columns(TABLES[kind])
            if kind == "balance":
                cols = filter_balance_columns(cols)
            db_counts[kind] = len(cols)
        except Exception:
            db_counts[kind] = fields[kind]["count"]
        fields[kind]["dbCount"] = db_counts[kind]
    combined_count = sum(len(keys) for _, _, keys in COMBINED_SECTIONS)
    ratio_count = sum(len(keys) for _, _, keys in RATIO_SECTIONS)
    db_counts["combined"] = combined_count + ratio_count
    db_counts["ratios"] = ratio_count
    return jsonify(
        {
            "brand": "QuantGems",
            "product": "財報引擎",
            "labels": LABELS_ZH,
            "fields": fields,
            "fieldCounts": db_counts,
            "catalogCounts": {
                k: len(catalog.get(k, {}).get("order", []))
                for k in ("income", "balance", "cashflow")
            },
            "emphasis": sorted(EMPHASIS_KEYS),
            "epsKeys": sorted(EPS_KEYS),
            "ratioKeys": RATIO_KEYS,
        }
    )


@app.get("/api/fields")
def api_fields():
    kind = (request.args.get("kind") or "").strip().lower()
    meta_all = fields_meta()
    if kind:
        if kind not in meta_all:
            return jsonify({"error": "kind must be income|balance|cashflow"}), 400
        return jsonify({"kind": kind, **meta_all[kind]})
    return jsonify(meta_all)


@app.get("/api/symbols/search")
def search_symbols():
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify({"items": []})
    limit = min(int(request.args.get("limit") or 20), 50)
    code = normalize_code(q)
    like = f"%{q}%"
    table = TABLES["symbols"]
    sql = f"""
        SELECT symbol, name, short_name, market, industry
        FROM {table}
        WHERE symbol ILIKE %s
           OR short_name ILIKE %s
           OR name ILIKE %s
           OR REPLACE(symbol, '.TW', '') = %s
           OR REPLACE(symbol, '.TWO', '') = %s
        ORDER BY
          CASE
            WHEN REPLACE(symbol, '.TW', '') = %s OR REPLACE(symbol, '.TWO', '') = %s THEN 0
            WHEN symbol ILIKE %s THEN 1
            WHEN short_name ILIKE %s THEN 2
            ELSE 3
          END,
          symbol
        LIMIT %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (like, like, like, code, code, code, code, f"{code}%", f"{q}%", limit),
            )
            rows = [serialize_row(r) for r in cur.fetchall()]
    for r in rows:
        r["code"] = normalize_code(r.get("symbol") or "")
        r["label"] = r.get("short_name") or r.get("name") or r["code"]
    return jsonify({"items": rows, "q": q})


@app.get("/api/reports/<code>/overview")
def report_overview(code: str):
    code = normalize_code(code)
    if not code:
        return jsonify({"error": "invalid code"}), 400

    basis = (request.args.get("basis") or "single").strip().lower()
    if basis not in ("single", "cumulative"):
        basis = "single"

    income_t = TABLES["income"]
    balance_t = TABLES["balance"]
    cash_t = TABLES["cashflow"]
    ratios_t = TABLES["ratios"]
    symbols_t = TABLES["symbols"]
    rsym = ratio_symbol(code)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT symbol, name, short_name, market, industry
                FROM {symbols_t}
                WHERE REPLACE(symbol, '.TW', '') = %s
                   OR REPLACE(symbol, '.TWO', '') = %s
                LIMIT 1
                """,
                (code, code),
            )
            meta_row = cur.fetchone()

            cur.execute(
                f"""
                SELECT period FROM {income_t}
                WHERE "股票代號" = %s
                ORDER BY period DESC
                """,
                (code,),
            )
            periods = [r["period"] for r in cur.fetchall()]

            latest = periods[0] if periods else None
            highlight = None
            if latest:
                cur.execute(
                    f"""
                    SELECT
                      i.period,
                      i."Revenue" AS revenue,
                      i."GrossProfitFromOperations" AS gross_profit,
                      i."ProfitLossFromOperatingActivities" AS op_profit,
                      i."ProfitLoss" AS net_profit,
                      i."BasicEarningsLossPerShareTotal" AS eps,
                      b."Assets" AS assets,
                      b."Equity" AS equity,
                      b."Liabilities" AS liabilities,
                      c."NetCashFlowsFromUsedInOperatingActivities" AS cfo,
                      c."NetCashFlowsFromUsedInInvestingActivities" AS cfi,
                      c."NetCashFlowsFromUsedInFinancingActivities" AS cff
                    FROM {income_t} i
                    LEFT JOIN {balance_t} b
                      ON i."股票代號" = b."股票代號" AND i.period = b.period
                    LEFT JOIN {cash_t} c
                      ON i."股票代號" = c."股票代號" AND i.period = c.period
                    WHERE i."股票代號" = %s AND i.period = %s
                    """,
                    (code, latest),
                )
                highlight = cur.fetchone()

            cur.execute(
                f"""
                SELECT period, gross_margin, op_margin, net_margin, roa, roe,
                       debt_ratio, current_ratio, quick_ratio,
                       revenue, gross_profit, op_profit, net_profit, assets, equity
                FROM {ratios_t}
                WHERE symbol = %s OR symbol = %s OR REPLACE(symbol, '.TW', '') = %s
                ORDER BY period DESC
                LIMIT 16
                """,
                (rsym, code, code),
            )
            ratios = [serialize_row(r) for r in cur.fetchall()]

    symbol = serialize_row(meta_row) if meta_row else {
        "symbol": f"{code}.TW",
        "name": None,
        "short_name": None,
        "market": None,
        "industry": None,
    }
    symbol["code"] = code
    symbol["label"] = symbol.get("short_name") or symbol.get("name") or code

    hl = serialize_row(highlight) if highlight else None
    if hl:
        hl["periodLabel"] = period_label(hl.get("period"))
        matched_ratio = next(
            (r for r in ratios if str(r.get("period") or "") == str(hl.get("period") or "")),
            ratios[0] if ratios else None,
        )
        _, hq = parse_period(hl.get("period"))
        needs_basis_rows = (basis == "single" and hq == 4) or (
            basis == "cumulative" and hq in (2, 3)
        )
        if needs_basis_rows:
            hy = str(hl.get("period") or "")[:4]
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT * FROM {income_t}
                        WHERE "股票代號" = %s AND period LIKE %s
                        ORDER BY period
                        """,
                        (code, f"{hy}%"),
                    )
                    year_rows = [serialize_row(r) for r in cur.fetchall()]
            transformed = transform_income_rows(year_rows, basis)
            hl = next(
                (r for r in transformed if r.get("period") == hl.get("period")),
                hl,
            )
            hl["periodLabel"] = period_label(hl.get("period"))
        hl = enrich_highlight_ratios(hl, matched_ratio)

    return jsonify(
        {
            "symbol": symbol,
            "periods": [{"value": p, "label": period_label(p)} for p in periods],
            "latestPeriod": latest,
            "highlight": hl,
            "incomeBasis": basis,
            "ratios": [
                {**r, "periodLabel": period_label(r.get("period"))} for r in ratios
            ],
        }
    )


def _fetch_table_rows(code: str, kind: str, *, limit: int, periods: Optional[list[str]] = None) -> list[dict]:
    table = TABLES[kind]
    with get_conn() as conn:
        with conn.cursor() as cur:
            if periods:
                cur.execute(
                    f"""
                    SELECT * FROM {table}
                    WHERE "股票代號" = %s AND period = ANY(%s)
                    ORDER BY period DESC
                    """,
                    (code, periods),
                )
            else:
                cur.execute(
                    f"""
                    SELECT * FROM {table}
                    WHERE "股票代號" = %s
                    ORDER BY period DESC
                    LIMIT %s
                    """,
                    (code, limit),
                )
            return [serialize_row(r) for r in cur.fetchall()]


def _apply_income_basis(code: str, rows: list[dict], basis: str) -> list[dict]:
    if not rows:
        return rows
    original_periods = {str(r.get("period")) for r in rows}
    extra_rows: list[dict] = []
    years_q4 = {
        parse_period(r.get("period"))[0]
        for r in rows
        if parse_period(r.get("period"))[1] == 4
    }
    if years_q4:
        table = TABLES["income"]
        with get_conn() as conn:
            with conn.cursor() as cur:
                for year in years_q4:
                    cur.execute(
                        f"""
                        SELECT * FROM {table}
                        WHERE "股票代號" = %s AND period LIKE %s
                        ORDER BY period
                        """,
                        (code, f"{year}%"),
                    )
                    extra_rows.extend(serialize_row(r) for r in cur.fetchall())
    ctx_rows = ensure_income_year_context(rows, extra_rows)
    transformed = transform_income_rows(ctx_rows, basis)
    return [r for r in transformed if str(r.get("period")) in original_periods]


def _rows_by_period(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("period")): r for r in rows if r.get("period") is not None}


def _fetch_ratio_rows(code: str, *, limit: int, periods: Optional[list[str]] = None) -> list[dict]:
    table = TABLES["ratios"]
    rsym = ratio_symbol(code)
    with get_conn() as conn:
        with conn.cursor() as cur:
            if periods:
                cur.execute(
                    f"""
                    SELECT * FROM {table}
                    WHERE (symbol = %s OR symbol = %s OR REPLACE(symbol, '.TW', '') = %s)
                      AND period = ANY(%s)
                    ORDER BY period DESC
                    """,
                    (rsym, code, code, periods),
                )
            else:
                cur.execute(
                    f"""
                    SELECT * FROM {table}
                    WHERE symbol = %s OR symbol = %s OR REPLACE(symbol, '.TW', '') = %s
                    ORDER BY period DESC
                    LIMIT %s
                    """,
                    (rsym, code, code, limit),
                )
            return [serialize_row(r) for r in cur.fetchall()]


def _first_number(row: dict, *keys: str) -> Optional[float]:
    for key in keys:
        val = to_number(row.get(key))
        if val is not None:
            return val
    return None


def _compute_ratio_fallback(
    key: str,
    income_row: Optional[dict],
    balance_row: Optional[dict],
) -> Optional[float]:
    income_row = income_row or {}
    balance_row = balance_row or {}
    rev = to_number(income_row.get("Revenue"))
    gp = to_number(income_row.get("GrossProfitFromOperations"))
    op = to_number(income_row.get("ProfitLossFromOperatingActivities"))
    np_ = to_number(income_row.get("ProfitLoss"))
    assets = _first_number(balance_row, "Assets", "TotalAssets")
    equity = _first_number(
        balance_row,
        "Equity",
        "TotalEquity",
        "EquityAttributableToOwnersOfParent",
    )
    liab = _first_number(balance_row, "Liabilities", "TotalLiabilities")
    ca = _first_number(balance_row, "CurrentAssets", "TotalCurrentAssets")
    cl = _first_number(balance_row, "CurrentLiabilities", "TotalCurrentLiabilities")
    cash = to_number(balance_row.get("CashAndCashEquivalents"))

    if key == "gross_margin":
        return safe_div(gp, rev)
    if key == "op_margin":
        return safe_div(op, rev)
    if key == "net_margin":
        return safe_div(np_, rev)
    if key == "roa":
        return safe_div(np_, assets)
    if key == "roe":
        return safe_div(np_, equity)
    if key == "debt_ratio":
        return safe_div(liab, assets)
    if key == "equity_ratio":
        return safe_div(equity, assets)
    if key == "debt_to_equity":
        return safe_div(liab, equity)
    if key == "current_ratio":
        return safe_div(ca, cl)
    if key == "quick_ratio":
        # 無細項時以流動資產近似
        return safe_div(ca, cl)
    if key == "cash_ratio" or key == "cash_cl_ratio":
        return safe_div(cash, cl)
    return None


def _ratio_value_for_period(
    key: str,
    period: str,
    ratio_by_period: dict[str, dict],
    income_by_period: dict[str, dict],
    balance_by_period: dict[str, dict],
    *,
    prefer_computed_income: bool = False,
) -> Optional[float]:
    # 獲利相關比率：依單季／累計損益重算，避免吃到資料庫累計 Q4
    if prefer_computed_income and key in INCOME_LINKED_RATIO_KEYS:
        computed = _compute_ratio_fallback(
            key,
            income_by_period.get(period),
            balance_by_period.get(period),
        )
        if computed is not None:
            return computed

    row = ratio_by_period.get(period) or {}
    val = to_number(row.get(key))
    if val is not None:
        return val
    return _compute_ratio_fallback(
        key,
        income_by_period.get(period),
        balance_by_period.get(period),
    )


def build_ratio_sections(
    periods: list[str],
    *,
    ratio_rows: list[dict],
    income_rows: list[dict],
    balance_rows: list[dict],
    only_with_values: bool = True,
    prefer_computed_income: bool = False,
) -> list[dict]:
    ratio_by = _rows_by_period(ratio_rows)
    income_by = _rows_by_period(income_rows)
    balance_by = _rows_by_period(balance_rows)
    sections = []
    for sid, title, keys in RATIO_SECTIONS:
        items = []
        for key in keys:
            values = {}
            any_val = False
            for p in periods:
                val = _ratio_value_for_period(
                    key,
                    p,
                    ratio_by,
                    income_by,
                    balance_by,
                    prefer_computed_income=prefer_computed_income,
                )
                values[p] = val
                if val is not None:
                    any_val = True
            if only_with_values and not any_val:
                continue
            items.append(
                {
                    "key": key,
                    "label": LABELS_ZH.get(key, key),
                    "emphasis": key in {"gross_margin", "roe", "debt_ratio", "current_ratio"},
                    "isEps": False,
                    "isRatio": True,
                    "isMultiple": key in RATIO_MULTIPLE_KEYS,
                    "values": values,
                }
            )
        if items:
            sections.append({"section": title, "id": sid, "items": items})
    return sections


def build_ratios_statement(
    code: str,
    *,
    limit: int = 8,
    basis: str = "single",
    only_with_values: bool = True,
) -> dict:
    if basis not in ("single", "cumulative"):
        basis = "single"

    income_rows = _fetch_table_rows(code, "income", limit=limit)
    income_rows = _apply_income_basis(code, income_rows, basis)[:limit]
    periods = [str(r.get("period")) for r in income_rows if r.get("period")]
    if not periods:
        ratio_rows = _fetch_ratio_rows(code, limit=limit)
        periods = [str(r.get("period")) for r in ratio_rows if r.get("period")]
        income_rows = []
        balance_rows = []
        ratio_rows = ratio_rows[:limit]
    else:
        balance_rows = _fetch_table_rows(code, "balance", limit=limit, periods=periods)
        ratio_rows = _fetch_ratio_rows(code, limit=limit, periods=periods)

    sections = build_ratio_sections(
        periods,
        ratio_rows=ratio_rows,
        income_rows=income_rows,
        balance_rows=balance_rows,
        only_with_values=only_with_values,
        prefer_computed_income=True,
    )
    field_total = sum(len(keys) for _, _, keys in RATIO_SECTIONS)
    return {
        "code": code,
        "kind": "ratios",
        "periods": [{"value": p, "label": period_label(p)} for p in periods],
        "sections": sections,
        "fieldTotal": field_total,
        "fieldShown": sum(len(s["items"]) for s in sections),
        "showAllFields": not only_with_values,
        "incomeBasis": basis,
        "raw": ratio_rows,
    }


def build_combined_statement(
    code: str,
    *,
    limit: int = 8,
    basis: str = "single",
    only_with_values: bool = True,
) -> dict:
    income_rows = _fetch_table_rows(code, "income", limit=limit)
    income_rows = _apply_income_basis(code, income_rows, basis)[:limit]
    periods = [str(r.get("period")) for r in income_rows if r.get("period")]
    if not periods:
        field_total = sum(len(keys) for _, _, keys in COMBINED_SECTIONS) + sum(
            len(keys) for _, _, keys in RATIO_SECTIONS
        )
        return {
            "code": code,
            "kind": "combined",
            "periods": [],
            "sections": [],
            "fieldTotal": field_total,
            "fieldShown": 0,
            "showAllFields": not only_with_values,
            "incomeBasis": basis,
            "raw": [],
        }

    balance_rows = _fetch_table_rows(code, "balance", limit=limit, periods=periods)
    cash_rows = _fetch_table_rows(code, "cashflow", limit=limit, periods=periods)
    ratio_rows = _fetch_ratio_rows(code, limit=limit, periods=periods)
    by_kind = {
        "income": _rows_by_period(income_rows),
        "balance": _rows_by_period(balance_rows),
        "cashflow": _rows_by_period(cash_rows),
    }

    sections = []
    for sid, title, keys in COMBINED_SECTIONS:
        items = []
        source = by_kind[sid]
        for key in keys:
            values = {}
            any_val = False
            for p in periods:
                raw = source.get(p, {}).get(key)
                val = to_number(raw)
                values[p] = val
                if val is not None:
                    any_val = True
            if only_with_values and not any_val:
                continue
            items.append(
                {
                    "key": key,
                    "label": label_for(sid, key),
                    "emphasis": key in EMPHASIS_KEYS,
                    "isEps": key in EPS_KEYS,
                    "isRatio": False,
                    "values": values,
                }
            )
        if items:
            sections.append({"section": title, "id": sid, "items": items})

    ratio_sections = build_ratio_sections(
        periods,
        ratio_rows=ratio_rows,
        income_rows=income_rows,
        balance_rows=balance_rows,
        only_with_values=only_with_values,
        prefer_computed_income=True,
    )
    sections.extend(ratio_sections)

    field_total = sum(len(keys) for _, _, keys in COMBINED_SECTIONS) + sum(
        len(keys) for _, _, keys in RATIO_SECTIONS
    )
    field_shown = sum(len(s["items"]) for s in sections)
    return {
        "code": code,
        "kind": "combined",
        "periods": [{"value": p, "label": period_label(p)} for p in periods],
        "sections": sections,
        "fieldTotal": field_total,
        "fieldShown": field_shown,
        "showAllFields": not only_with_values,
        "incomeBasis": basis,
        "raw": income_rows,
    }


@app.get("/api/reports/<code>/<kind>")
def report_statement(code: str, kind: str):
    code = normalize_code(code)
    kind = (kind or "").strip().lower()
    if not code:
        return jsonify({"error": "invalid code"}), 400

    limit = min(int(request.args.get("limit") or 8), 20)
    periods_arg = (request.args.get("periods") or "").strip()
    show_all = request.args.get("full", "").lower() in ("1", "true", "yes")
    basis = (request.args.get("basis") or "single").strip().lower()
    if basis not in ("single", "cumulative"):
        basis = "single"

    if kind == "combined":
        return jsonify(
            build_combined_statement(
                code,
                limit=limit,
                basis=basis,
                only_with_values=not show_all,
            )
        )

    if kind == "ratios":
        return jsonify(
            build_ratios_statement(
                code,
                limit=limit,
                basis=basis,
                only_with_values=not show_all,
            )
        )

    if kind not in TABLES or kind in ("ratios", "symbols"):
        return jsonify(
            {"error": "kind must be income|balance|cashflow|combined|ratios"}
        ), 400
    table = TABLES[kind]

    if periods_arg:
        wanted = [p.strip() for p in periods_arg.split(",") if p.strip()]
        rows = _fetch_table_rows(code, kind, limit=limit, periods=wanted)
    else:
        rows = _fetch_table_rows(code, kind, limit=limit)

    if kind == "income":
        rows = _apply_income_basis(code, rows, basis)

    db_columns = table_columns(table)
    if kind == "balance":
        db_columns = filter_balance_columns(db_columns)
    rows = rows[:limit]
    periods = [r.get("period") for r in rows]
    sections = build_statement_sections(
        kind,
        rows,
        db_columns,
        only_with_values=not show_all,
    )
    field_total = len(db_columns)
    field_shown = sum(len(s["items"]) for s in sections)

    return jsonify(
        {
            "code": code,
            "kind": kind,
            "periods": [{"value": p, "label": period_label(p)} for p in periods],
            "sections": sections,
            "fieldTotal": field_total,
            "fieldShown": field_shown,
            "showAllFields": show_all,
            "incomeBasis": basis if kind in ("income", "combined") else None,
            "raw": rows,
        }
    )


@app.get("/api/screener/meta")
def screener_meta():
    with get_conn() as conn:
        industries = list_industries(conn, TABLES["symbols"])
        periods = list_periods(conn, TABLES["ratios"], 16)
    return jsonify(
        {
            "presets": list_presets(),
            "industries": industries,
            "periods": periods,
            "markets": [
                {"id": "both", "label": "上市＋上櫃"},
                {"id": "listed", "label": "上市"},
                {"id": "otc", "label": "上櫃"},
            ],
        }
    )


@app.get("/api/screener")
def screener():
    params = parse_screener_args(request.args)
    try:
        with get_conn() as conn:
            payload = run_screener(conn, TABLES, params)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/stats")
def stats():
    with get_conn() as conn:
        with conn.cursor() as cur:
            out = {}
            for key, table in TABLES.items():
                if key == "symbols":
                    continue
                cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
                out[key] = cur.fetchone()["n"]
            cur.execute(
                f'SELECT COUNT(DISTINCT "股票代號") AS n FROM {TABLES["income"]}'
            )
            out["companies"] = cur.fetchone()["n"]
            cur.execute(f"SELECT MAX(period) AS p FROM {TABLES['income']}")
            out["latestPeriod"] = cur.fetchone()["p"]
            for fk, table in (
                ("incomeFields", TABLES["income"]),
                ("balanceFields", TABLES["balance"]),
                ("cashflowFields", TABLES["cashflow"]),
            ):
                try:
                    cols = table_columns(table)
                    if fk == "balanceFields":
                        cols = filter_balance_columns(cols)
                    out[fk] = len(cols)
                except Exception:
                    out[fk] = None
    return jsonify(out)


if __name__ == "__main__":
    port = int(os.getenv("FINENGINE_PORT", "8787"))
    app.run(host="0.0.0.0", port=port, debug=True)
