from screener import (
    FILTER_SPECS,
    SORTABLE,
    parse_screener_args,
    run_screener,
)


class FakeCursor:
    def __init__(self):
        self.sql = []
        self.last = ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, binds=None):
        self.last = str(sql)
        self.sql.append((self.last, binds))

    def fetchone(self):
        if "MAX(period)" in self.last:
            return {"p": "202501"}
        if "COUNT(*)" in self.last:
            return {"n": 0}
        return {}

    def fetchall(self):
        if "information_schema.columns" in self.last:
            return [
                {"column_name": "symbol"},
                {"column_name": "period"},
                {"column_name": "roe"},
            ]
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()

    def cursor(self):
        return self.cursor_instance


def test_advanced_screener_params_and_sorting():
    params = parse_screener_args(
        {
            "roic_min": "0.12",
            "cash_conversion_cycle_max": "90",
            "sort": "free_cash_flow_per_share",
            "dir": "asc",
        }
    )
    assert params["filters"]["roic_min"] == 0.12
    assert params["filters"]["cash_conversion_cycle_max"] == 90
    assert params["sort"] == "free_cash_flow_per_share"
    assert params["dir"] == "asc"
    assert "roic" in SORTABLE
    specs = {key for key, _, _ in FILTER_SPECS}
    assert {"roic_min", "roic_max", "inventory_days_min", "inventory_days_max"} <= specs


def test_missing_schema_column_filters_to_zero_without_invalid_select():
    conn = FakeConnection()
    params = parse_screener_args(
        {"roic_min": "0.1", "sort": "roic", "page_size": "10"}
    )
    payload = run_screener(
        conn,
        {"ratios": "tw_financial_ratios", "symbols": "tw_stock_symbols"},
        params,
    )
    sql = "\n".join(statement for statement, _ in conn.cursor_instance.sql)
    assert payload["total"] == 0
    assert "FALSE" in sql
    assert 'NULL::numeric AS "roic"' in sql
    assert 'r."roic"' not in sql
