"""
Pattern Detection package.

Each detector module exposes a single function:
    detect(ticker: str, df: pd.DataFrame) -> list[dict]

The returned dicts are partial Signal field dicts — the scorer and writer
complete them before DB insertion.
"""
