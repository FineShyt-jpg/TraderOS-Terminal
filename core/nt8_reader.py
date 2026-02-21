"""
NinjaTrader 8 Data Reader
Reads trade executions from NT8's SQLite database and
strategy parameters from workspace XML files.
"""

import sqlite3
import os
import xml.etree.ElementTree as ET
import zipfile
import io
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
import pandas as pd
import json
import re


class NT8Reader:
    """
    Reads data directly from NinjaTrader 8's internal files.
    - trade.sqlite for execution data (real-time, today only)
    - workspace XML files for strategy parameter configurations
    - strategy export XMLs for parameter snapshots
    """

    NT8_DOCS_PATH = Path.home() / "Documents" / "NinjaTrader 8"
    DB_PATH = NT8_DOCS_PATH / "db" / "trade.sqlite"
    WORKSPACES_PATH = NT8_DOCS_PATH / "workspaces"
    STRATEGIES_PATH = NT8_DOCS_PATH / "strategies"

    # Instrument point values for P&L calculation
    POINT_VALUES = {
        "ES": 50.0,   # E-mini S&P 500
        "NQ": 20.0,   # E-mini NASDAQ
        "YM": 5.0,    # E-mini Dow
        "RTY": 50.0,  # E-mini Russell
        "CL": 1000.0, # Crude Oil
        "GC": 100.0,  # Gold
        "SI": 5000.0, # Silver
        "ZB": 1000.0, # 30-Year T-Bond
        "ZN": 1000.0, # 10-Year T-Note
        "6E": 125000.0, # Euro FX
        "6J": 12500000.0, # Japanese Yen
        "MES": 5.0,   # Micro E-mini S&P
        "MNQ": 2.0,   # Micro E-mini NASDAQ
        "MYM": 0.5,   # Micro E-mini Dow
    }

    def __init__(self):
        self.db_path = self.DB_PATH
        self.workspaces_path = self.WORKSPACES_PATH
        self._cached_params = {}  # strategy_name -> params dict

    def is_connected(self) -> bool:
        """Check if NT8 database is accessible."""
        return self.db_path.exists()

    def get_db_path(self) -> Path:
        return self.db_path

    def set_db_path(self, path: str):
        self.db_path = Path(path)

    def get_executions_today(self) -> pd.DataFrame:
        """Get all executions from today (real-time session data)."""
        today = date.today().strftime("%Y-%m-%d")
        return self.get_executions_for_date(today)

    def get_executions_for_date(self, target_date: str) -> pd.DataFrame:
        """
        Get executions for a specific date from NT8 trade.sqlite.
        Returns DataFrame with columns: Id, AccountName, Instrument,
        MarketPosition, Quantity, Price, Time, Commission, StrategyName
        """
        if not self.db_path.exists():
            return pd.DataFrame()

        try:
            # NT8 keeps the SQLite file open; use URI with immutable for safe concurrent read
            uri = f"file:{self.db_path}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True, timeout=5)

            # Try primary schema (NT8 8.x standard)
            query = self._build_execution_query(target_date)
            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                return df

            # Normalize column names
            df = self._normalize_execution_df(df)
            return df

        except sqlite3.OperationalError as e:
            # Try fallback without URI (some systems)
            try:
                conn = sqlite3.connect(str(self.db_path), timeout=5)
                query = self._build_execution_query(target_date)
                df = pd.read_sql_query(query, conn)
                conn.close()
                return self._normalize_execution_df(df) if not df.empty else df
            except Exception:
                return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def _build_execution_query(self, target_date: str) -> str:
        """Build SQL query for executions on a given date."""
        return f"""
            SELECT
                e.Id,
                e.AccountName,
                e.Instrument,
                e.MarketPosition,
                e.Quantity,
                e.Price,
                e.Time,
                e.Commission,
                e.Name AS StrategyName,
                e.OrderId
            FROM Execution e
            WHERE date(e.Time) = '{target_date}'
            ORDER BY e.Time ASC
        """

    def _normalize_execution_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names and types from NT8 execution data."""
        col_map = {
            "accountname": "AccountName",
            "instrument": "Instrument",
            "marketposition": "MarketPosition",
            "quantity": "Quantity",
            "price": "Price",
            "time": "Time",
            "commission": "Commission",
            "strategyname": "StrategyName",
            "orderid": "OrderId",
            "id": "Id",
        }
        df.columns = [col_map.get(c.lower(), c) for c in df.columns]

        if "Time" in df.columns:
            df["Time"] = pd.to_datetime(df["Time"])
        if "MarketPosition" in df.columns:
            # NT8: 0=Long entry/exit, 1=Short, some versions use 'Long'/'Short'
            if df["MarketPosition"].dtype == object:
                df["MarketPosition"] = df["MarketPosition"].map(
                    {"Long": 0, "Short": 1}
                ).fillna(df["MarketPosition"])

        return df

    def get_table_names(self) -> list:
        """Inspect NT8 SQLite for available tables (debug/discovery)."""
        if not self.db_path.exists():
            return []
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
            return tables
        except Exception:
            return []

    def get_all_strategy_names(self) -> list:
        """Get all unique strategy names from the trade database."""
        if not self.db_path.exists():
            return []
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5)
            df = pd.read_sql_query(
                "SELECT DISTINCT Name FROM Execution WHERE Name IS NOT NULL", conn
            )
            conn.close()
            return df["Name"].tolist() if not df.empty else []
        except Exception:
            return []

    def parse_workspace_file(self, path: Path) -> list[dict]:
        """
        Parse a single NT8 workspace file.
        Accepts .xml directly or .NT8BK (ZIP archive containing XMLs).
        Returns list of strategy config dicts.
        """
        suffix = path.suffix.lower()
        if suffix in (".nt8bk", ".zip"):
            return self._parse_nt8bk(path)
        try:
            return self._parse_workspace_xml(path)
        except Exception:
            return []

    def _parse_nt8bk(self, path: Path) -> list[dict]:
        """Extract and parse all XML files inside an NT8BK (ZIP) backup archive."""
        configs = []
        try:
            with zipfile.ZipFile(path, "r") as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".xml"):
                        continue
                    try:
                        xml_bytes = zf.read(name)
                        root = ET.fromstring(xml_bytes)
                        # Wrap in a fake file-parse by reusing element iteration logic
                        for elem in root.iter():
                            tag_lower = elem.tag.lower()
                            if tag_lower in ("ninjascript", "strategy", "strategybase"):
                                config = self._extract_strategy_params(elem)
                                if config:
                                    config["workspace"] = Path(name).stem
                                    configs.append(config)
                    except ET.ParseError:
                        continue
        except (zipfile.BadZipFile, Exception):
            pass
        return configs

    def get_workspace_strategy_configs(self) -> list[dict]:
        """
        Parse NT8 workspace XML files to extract running strategy configurations.
        Returns list of dicts with strategy name, account, and parameter values.
        """
        configs = []
        if not self.workspaces_path.exists():
            return configs

        for ws_file in self.workspaces_path.glob("*.xml"):
            try:
                configs.extend(self._parse_workspace_xml(ws_file))
            except Exception:
                continue

        return configs

    def _parse_workspace_xml(self, ws_file: Path) -> list[dict]:
        """
        Parse a single NT8 workspace XML file for strategy instances.
        NT8 workspaces use several XML formats across versions;
        we handle the common patterns.
        """
        configs = []
        try:
            tree = ET.parse(ws_file)
            root = tree.getroot()
        except ET.ParseError:
            return configs

        # Search for strategy/NinjaScript elements anywhere in the tree
        for elem in root.iter():
            tag_lower = elem.tag.lower()
            if tag_lower in ("ninjascript", "strategy", "strategybase"):
                config = self._extract_strategy_params(elem)
                if config:
                    config["workspace"] = ws_file.stem
                    configs.append(config)

        return configs

    def _extract_strategy_params(self, elem: ET.Element) -> Optional[dict]:
        """
        Extract strategy name, account, and key parameters from an XML element.
        Handles both attribute-style and child-element-style parameter storage.
        """
        config = {
            "label": None,
            "account": None,
            "adx_period": None,
            "protective_stop_ticks": None,
            "long_failed_exit": None,
            "short_failed_exit": None,
            "overbought": None,
            "oversold": None,
            "long_exit_at": None,
            "short_exit_at": None,
            "raw_params": {},
        }

        # Collect all attributes and child text into a flat dict for searching
        all_values = {}
        for attr, val in elem.attrib.items():
            all_values[attr.lower()] = val

        for child in elem.iter():
            if child.text and child.text.strip():
                all_values[child.tag.lower()] = child.text.strip()

        # Strategy name / label
        for key in ("name", "fulltypename", "typename", "label", "strategyname"):
            if key in all_values and all_values[key]:
                config["label"] = all_values[key]
                break

        # Account
        for key in ("account", "accountname", "acct"):
            if key in all_values:
                config["account"] = all_values[key]
                break

        # ADX Period
        for key in ("adxperiod", "adx_period", "adxlength", "adxfilterperiod"):
            if key in all_values:
                try:
                    config["adx_period"] = int(all_values[key])
                except ValueError:
                    pass
                break

        # Protective Stop
        for key in ("protectivestop", "protective_stop", "protectivestopticks", "stopticks"):
            if key in all_values:
                try:
                    config["protective_stop_ticks"] = int(all_values[key])
                except ValueError:
                    pass
                break

        # Failed Signal Exit values
        for key in ("longfailedexit", "longfailedexitsmi", "longfailed", "failedsignallongexit"):
            if key in all_values:
                try:
                    config["long_failed_exit"] = float(all_values[key])
                except ValueError:
                    pass
                break

        for key in ("shortfailedexit", "shortfailedexitsmi", "shortfailed", "failedsignalshortexit"):
            if key in all_values:
                try:
                    config["short_failed_exit"] = float(all_values[key])
                except ValueError:
                    pass
                break

        # Overbought / Oversold
        for key in ("overbought", "overboughtlevel", "entrylongoverbought"):
            if key in all_values:
                try:
                    config["overbought"] = float(all_values[key])
                except ValueError:
                    pass
                break

        for key in ("oversold", "oversoldlevel", "entryshortoverssold", "entryshort"):
            if key in all_values:
                try:
                    config["oversold"] = float(all_values[key])
                except ValueError:
                    pass
                break

        # Exit values
        for key in ("longexitat", "longexit", "longexitvalue"):
            if key in all_values:
                try:
                    config["long_exit_at"] = float(all_values[key])
                except ValueError:
                    pass
                break

        for key in ("shortexitat", "shortexit", "shortexitvalue"):
            if key in all_values:
                try:
                    config["short_exit_at"] = float(all_values[key])
                except ValueError:
                    pass
                break

        config["raw_params"] = all_values

        # Only return if we found at least a label
        if config["label"]:
            return config
        return None

    def get_point_value(self, instrument: str) -> float:
        """Get the point value for a given instrument symbol."""
        # Strip expiry suffix (e.g. "ES 03-26" -> "ES")
        root_sym = instrument.split()[0] if " " in instrument else instrument
        root_sym = re.sub(r"\d", "", root_sym).rstrip(" -").upper()
        return self.POINT_VALUES.get(root_sym, 1.0)

    def calculate_performance(self, executions: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate per-strategy performance metrics from raw executions.
        Groups by StrategyName + AccountName, computes:
          - Total trades (round trips)
          - Gross P&L
          - Net P&L (after commissions)
          - Win rate
          - Avg win, avg loss, profit factor
        Returns a summary DataFrame.
        """
        if executions.empty:
            return pd.DataFrame()

        required_cols = {"StrategyName", "AccountName", "Instrument", "MarketPosition",
                         "Quantity", "Price", "Commission"}
        if not required_cols.issubset(set(executions.columns)):
            return pd.DataFrame()

        rows = []
        for (strategy, account, instrument), grp in executions.groupby(
            ["StrategyName", "AccountName", "Instrument"]
        ):
            pnl_data = self._calculate_round_trip_pnl(grp, instrument)
            if pnl_data:
                pnl_data["StrategyName"] = strategy
                pnl_data["AccountName"] = account
                pnl_data["Instrument"] = instrument
                rows.append(pnl_data)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        return df

    def _calculate_round_trip_pnl(self, grp: pd.DataFrame, instrument: str) -> Optional[dict]:
        """
        Match long buys to sells and short sells to covers using FIFO.
        Returns dict of performance metrics.
        """
        point_val = self.get_point_value(instrument)
        grp = grp.sort_values("Time").reset_index(drop=True)

        trades = []
        long_queue = []   # (qty, price)
        short_queue = []  # (qty, price)

        for _, row in grp.iterrows():
            mp = row.get("MarketPosition", 0)
            qty = int(row.get("Quantity", 0))
            price = float(row.get("Price", 0))
            comm = float(row.get("Commission", 0))

            # NT8 MarketPosition: 0=Buy (enters long or covers short),
            # 1=Sell (exits long or enters short)
            # This is approximate; actual NT8 semantics may differ by strategy
            if mp == 0:  # Buy side
                # First check if it covers existing shorts
                while short_queue and qty > 0:
                    sq, sp = short_queue[0]
                    fill = min(sq, qty)
                    pnl = (sp - price) * fill * point_val - comm * (fill / qty)
                    trades.append(pnl)
                    qty -= fill
                    if sq > fill:
                        short_queue[0] = (sq - fill, sp)
                    else:
                        short_queue.pop(0)
                if qty > 0:
                    long_queue.append((qty, price))

            else:  # Sell side
                # First check if it closes existing longs
                while long_queue and qty > 0:
                    lq, lp = long_queue[0]
                    fill = min(lq, qty)
                    pnl = (price - lp) * fill * point_val - comm * (fill / qty)
                    trades.append(pnl)
                    qty -= fill
                    if lq > fill:
                        long_queue[0] = (lq - fill, lp)
                    else:
                        long_queue.pop(0)
                if qty > 0:
                    short_queue.append((qty, price))

        if not trades:
            return None

        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        net_pnl = sum(trades)
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        total_comm = grp["Commission"].sum() if "Commission" in grp else 0

        return {
            "TotalTrades": len(trades),
            "Winners": len(wins),
            "Losers": len(losses),
            "WinRate": round(win_rate, 2),
            "GrossPnL": round(net_pnl + total_comm, 2),
            "NetPnL": round(net_pnl, 2),
            "Commission": round(total_comm, 2),
            "AvgWin": round(avg_win, 2),
            "AvgLoss": round(avg_loss, 2),
            "ProfitFactor": round(profit_factor, 4) if profit_factor != float("inf") else 999.0,
            "GrossProfit": round(gross_profit, 2),
            "GrossLoss": round(-gross_loss, 2),
        }
