from app import build_ratio_sections, schema_select_expressions
from labels import RATIO_KEYS, RATIO_SECTIONS, RATIO_UNITS


NEW_FIELDS = {
    "operating_cash_flow",
    "free_cash_flow",
    "operating_cash_to_net_income",
    "free_cash_flow_margin",
    "roic",
    "interest_coverage",
    "asset_turnover",
    "inventory_turnover",
    "receivable_turnover",
    "payable_turnover",
    "inventory_days",
    "receivable_days",
    "payable_days",
    "cash_conversion_cycle",
    "revenue_yoy",
    "op_profit_yoy",
    "eps_yoy",
    "revenue_cagr_3y",
    "eps_cagr_3y",
    "book_value_per_share",
    "free_cash_flow_per_share",
    "dupont_net_margin",
    "dupont_asset_turnover",
    "dupont_equity_multiplier",
}


def test_new_ratio_contract_has_labels_groups_and_units():
    grouped = {key for _, _, keys in RATIO_SECTIONS for key in keys}
    assert NEW_FIELDS <= set(RATIO_KEYS)
    assert NEW_FIELDS <= grouped
    assert NEW_FIELDS <= set(RATIO_UNITS)
    assert set(RATIO_UNITS.values()) == {"percent", "multiple", "days", "currency"}


def test_schema_select_replaces_unmigrated_columns_with_null():
    expressions = schema_select_expressions(
        ["roe", "roic", "cash_conversion_cycle"], {"roe"}
    )
    assert expressions == [
        '"roe"',
        'NULL AS "roic"',
        'NULL AS "cash_conversion_cycle"',
    ]


def test_ratio_payload_metadata_and_cashflow_fallback():
    sections = build_ratio_sections(
        ["202501"],
        ratio_rows=[{"period": "202501"}],
        income_rows=[{"period": "202501", "Revenue": 100, "ProfitLoss": 20}],
        balance_rows=[],
        cashflow_rows=[
            {
                "period": "202501",
                "NetCashFlowsFromUsedInOperatingActivities": 30,
                "AcquisitionOfPropertyPlantAndEquipment": 10,
            }
        ],
        only_with_values=False,
    )
    items = {item["key"]: item for section in sections for item in section["items"]}
    assert items["operating_cash_flow"]["values"]["202501"] == 30
    assert items["free_cash_flow"]["values"]["202501"] == 20
    assert items["operating_cash_to_net_income"]["values"]["202501"] == 1.5
    assert items["free_cash_flow_margin"]["values"]["202501"] == 0.2
    assert items["roic"]["applicable"] is True
    assert items["roic"]["source"] is None
    assert items["free_cash_flow"]["source"] == "fallback"
    assert items["cash_conversion_cycle"]["unit"] == "days"


def test_financial_guard_marks_only_guarded_metrics_not_applicable():
    sections = build_ratio_sections(
        ["202501"],
        ratio_rows=[{"period": "202501"}],
        income_rows=[{"period": "202501"}],
        balance_rows=[],
        only_with_values=False,
        not_applicable_keys={"roic", "cash_conversion_cycle"},
    )
    items = {item["key"]: item for section in sections for item in section["items"]}
    assert items["roic"]["applicable"] is False
    assert items["cash_conversion_cycle"]["applicable"] is False
    assert items["revenue_yoy"]["applicable"] is True
