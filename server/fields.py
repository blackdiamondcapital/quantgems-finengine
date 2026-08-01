# -*- coding: utf-8 -*-
"""資料庫科目目錄：欄位順序、中文標籤、分組。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from labels import EMPHASIS_KEYS, EPS_KEYS, LABELS_ZH

CATALOG_PATH = Path(__file__).resolve().parent / "field_catalog.json"
META_COLS = {"股票代號", "period", "created_at", "updated_at"}

TABLE_KIND = {
    "income": "income",
    "balance": "balance",
    "cashflow": "cashflow",
}

# 資產負債表：別名欄位 → 標準欄位（兩者並存時隱藏別名）
BALANCE_ALIASES: dict[str, Optional[str]] = {
    "TotalCurrentAssets": "CurrentAssets",
    "TotalNoncurrentAssets": "NoncurrentAssets",
    "TotalAssets": "Assets",
    "TotalCurrentLiabilities": "CurrentLiabilities",
    "TotalNoncurrentLiabilities": "NoncurrentLiabilities",
    "TotalLiabilities": "Liabilities",
    "TotalEquity": "Equity",
    "TotalEquityAndLiabilities": "EquityAndLiabilities",
    "TotalLiabilitiesAndEquity": "EquityAndLiabilities",
    "ShortTermBorrowings": "ShorttermBorrowings",
    "LongTermBorrowings": "LongtermBorrowings",
    "RightOfUseAssets": "RightofuseAssets",
    "InvestmentsAccountedForUsingEquityMethod": "InvestmentAccountedForUsingEquityMethod",
    "ShareCapital": "OrdinaryShare",
    "CapitalSurplus": "CapitalReserve",
    "CapitalStock": "OrdinaryShare",
    "AccountsReceivableRelatedPartiesNet": "AccountsReceivableDueFromRelatedPartiesNet",
    "OtherReceivables": "OtherCurrentReceivables",
    "Prepayments": "CurrentPrepayments",
    "AccountsPayable": "TradeAndOtherCurrentPayablesToTradeSuppliers",
    "OtherPayables": "OtherCurrentPayables",
    "FinancialAssetsCurrentAtFairValueThroughProfitOrLoss": "CurrentFinancialAssetsAtFairValueThroughProfitOrLoss",
    "FinancialAssetsCurrentAtFVOCI": "CurrentFinancialAssetsAtFairValueThroughOtherComprehensiveIncome",
    "FinancialAssetsNoncurrentAtFVOCI": "NoncurrentFinancialAssetsAtFairValueThroughOtherComprehensiveIncome",
    "FinancialLiabilitiesCurrentAtFairValueThroughProfitOrLoss": "CurrentFinancialLiabilitiesAtFairValueThroughProfitOrLoss",
    "CurrentFinancialAssetsAtFairValueThroughOCI": "CurrentFinancialAssetsAtFairValueThroughOtherComprehensiveIncome",
    "NoncurrentFinancialAssetsAtFairValueThroughOCI": "NoncurrentFinancialAssetsAtFairValueThroughOtherComprehensiveIncome",
    "ContractLiabilitiesCurrent": "CurrentContractLiabilities",
    "BondsPayable": "NoncurrentPortionOfNoncurrentBondsIssued",
    "LeaseLiabilitiesCurrent": "CurrentLeaseLiabilities",
    "LeaseLiabilitiesNoncurrent": "NoncurrentFinanceLeaseLiabilities",
    "OtherEquity": "OtherEquityInterest",
    "IssuedCapital": "OrdinaryShare",
}

BALANCE_SECTION_DEFS = [
    ("ca", "流動資產"),
    ("nca", "非流動資產"),
    ("at", "資產合計"),
    ("cl", "流動負債"),
    ("ncl", "非流動負債"),
    ("lt", "負債合計"),
    ("eq", "權益"),
    ("fin", "金控／銀行"),
    ("other", "其他"),
]

# 依 catalog 順序建立科目 → 區塊對照
def _build_balance_key_section() -> dict[str, str]:
    catalog = load_catalog().get("balance", {}).get("order", [])
    idx = {k: i for i, k in enumerate(catalog)}
    mapping: dict[str, str] = {}

    ca_end = idx.get("CurrentAssets", 10**9)
    nca_start = idx.get("NoncurrentFinancialAssetsAtFairValueThroughProfitOrLoss", 10**9)
    nca_end = idx.get("NoncurrentAssets", 10**9)
    liab_start = idx.get("ShorttermBorrowings", 10**9)
    liab_end = idx.get("OtherNoncurrentLiabilitiesOthers", 10**9)
    eq_start = idx.get("OrdinaryShare", 10**9)
    eq_end = idx.get("Equity", 10**9)
    fin_start = idx.get("DueFromTheCentralBankAndCallLoansToBanks", 10**9)

    for key in catalog:
        i = idx[key]
        if key == "CurrentAssets":
            mapping[key] = "ca"
        elif key == "CurrentLiabilities":
            mapping[key] = "cl"
        elif i <= ca_end and key != "CurrentLiabilities":
            mapping[key] = "ca"
        elif nca_start <= i <= nca_end:
            mapping[key] = "nca"
        elif key in ("NoncurrentAssets", "TotalNoncurrentAssets"):
            mapping[key] = "nca"
        elif key in ("Assets", "TotalAssets"):
            mapping[key] = "at"
        elif key in ("Liabilities", "TotalLiabilities"):
            mapping[key] = "lt"
        elif key in ("Equity", "EquityAndLiabilities", "TotalEquity", "TotalEquityAndLiabilities", "TotalLiabilitiesAndEquity"):
            mapping[key] = "eq"
        elif liab_start <= i <= liab_end:
            mapping[key] = "ncl" if key in _NONCURRENT_LIAB_KEYS else "cl"
        elif eq_start <= i <= eq_end:
            mapping[key] = "eq"
        elif i >= fin_start:
            mapping[key] = "fin"
        else:
            mapping[key] = "other"

    return mapping


_NONCURRENT_LIAB_KEYS = {
    "NoncurrentFinancialLiabilitiesAtFairValueThroughProfitOrLoss",
    "NoncurrentContractLiabilities",
    "NoncurrentPortionOfNoncurrentBondsIssued",
    "LongtermBorrowings",
    "LongTermBorrowings",
    "NoncurrentProvisions",
    "DeferredTaxLiabilities",
    "NoncurrentFinanceLeaseLiabilities",
    "LeaseLiabilitiesNoncurrent",
    "OtherNoncurrentLiabilities",
    "NoncurrentRecognisedLiabilitiesDefinedBenefitPlan",
    "GuaranteeDepositsReceived",
    "OtherNoncurrentLiabilitiesOthers",
    "BondsPayable",
    "NoncurrentLiabilities",
    "TotalNoncurrentLiabilities",
    "LeaseLiabilities",
}


@lru_cache(maxsize=1)
def _balance_key_section() -> dict[str, str]:
    base = _build_balance_key_section()
    # DB 別名欄位的區塊跟標準欄位一致
    for alias, canonical in BALANCE_ALIASES.items():
        if canonical and canonical in base:
            base[alias] = base[canonical]
    base["BookValuePerShare"] = "eq"
    base["NotesReceivableNet"] = "ca"
    base["NotesPayable"] = "cl"
    base["CurrentTaxAssets"] = "ca"
    base["IntangibleAssets"] = "nca"
    base["CurrentFinancialLiabilitiesAtFairValueThroughProfitOrLoss"] = "cl"
    base["NoncurrentLiabilities"] = "ncl"
    base["TotalNoncurrentLiabilities"] = "ncl"
    base["CurrentCommercialPapersIssuedAndCurrentPortionOfNoncurrentCommercialPapersIssued"] = "cl"
    base["NoncurrentAssetsRecognisedAsIncrementalCostsToObtainContractWithCustomers"] = "nca"
    return base

INCOME_SECTIONS = [
    ("ops", "營運表現", {
        "Revenue", "RevenueFromInterest", "OtherRevenue", "OtherGainsLossesNet",
        "OperatingCosts", "GrossProfitFromOperations", "SellingExpense",
        "AdministrativeExpense", "ResearchAndDevelopmentExpense",
        "NetOtherIncomeExpenses", "ProfitLossFromOperatingActivities",
    }),
    ("below", "營業外與稅後", {
        "FinanceCosts", "EquityMethodShareOfProfitLoss", "NonoperatingIncomeAndExpenses",
        "ProfitLossBeforeTax", "ProfitLoss", "ProfitLossAttributableToOwnersOfParent",
        "ProfitLossAttributableToNoncontrollingInterests",
        "BasicEarningsLossPerShareTotal", "DilutedEarningsLossPerShareTotal",
    }),
    ("oci", "其他綜合損益", {
        "OCIEquityInstruments", "EquityMethodOCINotReclassified", "OCINotReclassifiedTotal",
        "ExchangeDifferencesOnTranslation", "EquityMethodOCIReclassified",
        "OCIReclassifiedTotal", "OtherComprehensiveIncomeTotal", "ComprehensiveIncome",
        "ComprehensiveIncomeAttributableToOwnersOfParent",
        "ComprehensiveIncomeAttributableToNoncontrollingInterests",
    }),
]

CASHFLOW_SECTIONS = [
    ("op", "營業活動", {
        "ProfitLossBeforeTax", "AdjustmentsToReconcileProfitLoss", "DepreciationExpense",
        "AmortisationExpense", "InterestExpense", "InterestIncome",
        "CashFlowsFromUsedInOperations", "InterestReceived", "DividendsReceived",
        "InterestPaid", "IncomeTaxesPaid", "NetCashFlowsFromUsedInOperatingActivities",
    }),
    ("inv", "投資活動", {
        "AcquisitionOfPropertyPlantAndEquipment", "ProceedsFromDisposalOfPropertyPlantAndEquipment",
        "AcquisitionOfIntangibleAssets", "AcquisitionOfInvestments", "ProceedsFromDisposalOfInvestments",
        "NetCashFlowsFromUsedInInvestingActivities",
    }),
    ("fin", "籌資活動", {
        "ProceedsFromIssuingShares", "PaymentsToAcquireTreasuryShares",
        "ProceedsFromBorrowings", "RepaymentsOfBorrowings", "DividendsPaid",
        "PaymentsOfLeaseLiabilities", "NetCashFlowsFromUsedInFinancingActivities",
        "EffectOfExchangeRateChangesOnCashAndCashEquivalents",
        "NetIncreaseDecreaseInCashAndCashEquivalents",
        "CashAndCashEquivalentsAtBeginningOfPeriod", "CashAndCashEquivalentsAtEndOfPeriod",
    }),
]


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _match_catalog_key(kind: str, col: str) -> Optional[str]:
    labels = load_catalog().get(kind, {}).get("labels", {})
    if col in labels:
        return col
    for key in labels:
        if key.startswith(col) or col.startswith(key):
            return key
        if len(col) >= 48 and key[: len(col)] == col:
            return key
    return None


def label_for(kind: str, col: str) -> str:
    if col in LABELS_ZH:
        return LABELS_ZH[col]
    catalog_key = _match_catalog_key(kind, col)
    catalog = load_catalog().get(kind, {}).get("labels", {})
    if catalog_key and catalog_key in catalog:
        zh = catalog[catalog_key]
        if re.search(r"[\u4e00-\u9fff]", zh):
            return zh
    if catalog_key and catalog_key in LABELS_ZH:
        return LABELS_ZH[catalog_key]
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", col)


def ordered_columns(kind: str, db_columns: list[str]) -> list[str]:
    catalog_order = load_catalog().get(kind, {}).get("order", [])
    seen: set[str] = set()
    ordered: list[str] = []

    for key in catalog_order:
        if key in db_columns and key not in seen:
            ordered.append(key)
            seen.add(key)

    for col in db_columns:
        if col not in seen:
            ordered.append(col)
            seen.add(col)

    return ordered


def filter_balance_columns(db_columns: list[str]) -> list[str]:
    cols = ordered_columns("balance", db_columns)
    hide: set[str] = set()
    col_set = set(cols)
    for alias, canonical in BALANCE_ALIASES.items():
        if alias in col_set and canonical and canonical in col_set:
            hide.add(alias)

    # PostgreSQL 63 字截斷欄位：保留完整名稱、隱藏截短版
    for col in cols:
        for other in cols:
            if col == other:
                continue
            if col.startswith(other) or other.startswith(col):
                shorter, longer = (col, other) if len(col) < len(other) else (other, col)
                if len(shorter) >= 40 and longer in col_set:
                    hide.add(shorter)

    return [c for c in cols if c not in hide]


def _resolve_balance_section(col: str) -> str:
    key_section = _balance_key_section()
    if col in key_section:
        return key_section[col]
    for known, sid in key_section.items():
        if col == known:
            continue
        if (col.startswith(known) or known.startswith(col)) and min(len(col), len(known)) >= 30:
            return sid
    return "other"


def section_plan(kind: str, columns: list[str]) -> list[tuple[str, str, list[str]]]:
    if kind == "balance":
        columns = filter_balance_columns(columns)

        titles = {sid: title for sid, title in BALANCE_SECTION_DEFS}
        buckets: dict[str, list[str]] = {sid: [] for sid, _ in BALANCE_SECTION_DEFS}

        for col in columns:
            sid = _resolve_balance_section(col)
            buckets[sid].append(col)

        return [(sid, titles[sid], buckets[sid]) for sid, _ in BALANCE_SECTION_DEFS if buckets[sid]]

    section_defs = INCOME_SECTIONS if kind == "income" else CASHFLOW_SECTIONS
    assigned: set[str] = set()
    sections: list[tuple[str, str, list[str]]] = []

    for sid, title, keys in section_defs:
        items = [c for c in columns if c in keys]
        if not items:
            continue
        assigned.update(items)
        sections.append((sid, title, items))

    remaining = [c for c in columns if c not in assigned]
    if remaining:
        sections.append(("other", "其他科目", remaining))

    return sections


def build_statement_sections(
    kind: str,
    rows: list[dict],
    db_columns: list[str],
    *,
    only_with_values: bool = False,
) -> list[dict]:
    if kind == "balance":
        db_columns = filter_balance_columns(db_columns)
    columns = ordered_columns(kind, db_columns)
    sections: list[dict] = []

    for sid, title, keys in section_plan(kind, columns):
        items = []
        for key in keys:
            values: dict[str, Any] = {}
            any_val = False
            for row in rows:
                period = row.get("period")
                raw = row.get(key)
                if raw is None and key not in row:
                    matched = _match_catalog_key(kind, key)
                    if matched:
                        raw = row.get(matched)
                val = None
                if raw is not None:
                    try:
                        val = float(raw)
                    except (TypeError, ValueError):
                        val = None
                values[period] = val
                if val is not None:
                    any_val = True
            if only_with_values and not any_val:
                continue
            items.append(
                {
                    "key": key,
                    "label": label_for(kind, key),
                    "emphasis": key in EMPHASIS_KEYS,
                    "isEps": key in EPS_KEYS,
                    "values": values,
                }
            )
        if items:
            sections.append({"section": title, "id": sid, "items": items})

    return sections


def fields_meta(db_counts: Optional[dict[str, int]] = None) -> dict:
    catalog = load_catalog()
    out = {}
    for kind in ("income", "balance", "cashflow"):
        order = catalog.get(kind, {}).get("order", [])
        db_count = (db_counts or {}).get(kind)
        out[kind] = {
            "count": db_count if db_count is not None else len(order),
            "catalogCount": len(order),
            "fields": [
                {
                    "key": key,
                    "label": label_for(kind, key),
                    "emphasis": key in EMPHASIS_KEYS,
                    "isEps": key in EPS_KEYS,
                }
                for key in order
            ],
            "labels": {k: label_for(kind, k) for k in order},
        }
    return out
