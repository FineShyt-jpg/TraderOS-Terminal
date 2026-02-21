"""
File Organizer

Manages the output folder hierarchy and file naming for strategy performance data.

Structure:
  output/
  └── {Label}/
      └── {Account}/
          └── {ParamFolder}/          <- ADX29_PS100_LF-75_SF75_ABCD1234
              ├── description.txt     <- Human-readable parameter description
              ├── 2026-02-21.csv      <- Individual day file
              ├── 2026-02-20.csv
              └── composite.csv       <- All days combined
"""

import csv
import json
import re
from pathlib import Path
from datetime import date, datetime
from typing import Optional
import pandas as pd

from core.strategy_fingerprint import StrategyParams


class FileOrganizer:
    """
    Creates and manages the strategy performance file hierarchy.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_strategy_dir(self, params: StrategyParams) -> Path:
        """Return the folder path for a given strategy variant."""
        safe_label = self._safe_name(params.label)
        safe_account = self._safe_name(params.account)
        param_folder = params.folder_name()
        return self.output_dir / safe_label / safe_account / param_folder

    def ensure_strategy_dir(self, params: StrategyParams) -> Path:
        """Create and initialize the folder if it doesn't exist."""
        d = self.get_strategy_dir(params)
        d.mkdir(parents=True, exist_ok=True)
        desc_file = d / "description.txt"
        if not desc_file.exists():
            desc_file.write_text(params.full_description(), encoding="utf-8")
        return d

    def update_description(self, params: StrategyParams):
        """Overwrite description.txt with latest param values."""
        d = self.get_strategy_dir(params)
        if d.exists():
            (d / "description.txt").write_text(params.full_description(), encoding="utf-8")

    def save_day_file(
        self,
        params: StrategyParams,
        target_date: date,
        performance_df: pd.DataFrame,
        executions_df: pd.DataFrame,
    ) -> Path:
        """
        Save a day's performance to {date}.csv in the strategy folder.
        Also updates the composite file.
        """
        d = self.ensure_strategy_dir(params)
        filename = target_date.strftime("%Y-%m-%d") + ".csv"
        day_path = d / filename

        # Build the day report
        report = self._build_day_report(target_date, params, performance_df, executions_df)
        report.to_csv(day_path, index=False)

        # Update composite
        self._update_composite(d, target_date, report)

        return day_path

    def _build_day_report(
        self,
        target_date: date,
        params: StrategyParams,
        perf_df: pd.DataFrame,
        exec_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Build a standardized day report DataFrame.
        Columns: Date, Label, Account, Instrument, TotalTrades, Winners, Losers,
                 WinRate, GrossPnL, NetPnL, Commission, AvgWin, AvgLoss,
                 ProfitFactor, ADX, ProtectiveStop, LongFailed, ShortFailed,
                 Overbought, Oversold, LongExitAt, ShortExitAt, Fingerprint
        """
        if perf_df.empty:
            # Return empty skeleton
            row = {
                "Date": target_date.isoformat(),
                "Label": params.label,
                "Account": params.account,
                "Instrument": "",
                "TotalTrades": 0,
                "Winners": 0,
                "Losers": 0,
                "WinRate": 0.0,
                "GrossPnL": 0.0,
                "NetPnL": 0.0,
                "Commission": 0.0,
                "AvgWin": 0.0,
                "AvgLoss": 0.0,
                "ProfitFactor": 0.0,
                "GrossProfit": 0.0,
                "GrossLoss": 0.0,
                **self._param_cols(params),
            }
            return pd.DataFrame([row])

        rows = []
        for _, perf_row in perf_df.iterrows():
            row = {
                "Date": target_date.isoformat(),
                "Label": params.label,
                "Account": params.account,
                "Instrument": perf_row.get("Instrument", ""),
                "TotalTrades": perf_row.get("TotalTrades", 0),
                "Winners": perf_row.get("Winners", 0),
                "Losers": perf_row.get("Losers", 0),
                "WinRate": perf_row.get("WinRate", 0.0),
                "GrossPnL": perf_row.get("GrossPnL", 0.0),
                "NetPnL": perf_row.get("NetPnL", 0.0),
                "Commission": perf_row.get("Commission", 0.0),
                "AvgWin": perf_row.get("AvgWin", 0.0),
                "AvgLoss": perf_row.get("AvgLoss", 0.0),
                "ProfitFactor": perf_row.get("ProfitFactor", 0.0),
                "GrossProfit": perf_row.get("GrossProfit", 0.0),
                "GrossLoss": perf_row.get("GrossLoss", 0.0),
                **self._param_cols(params),
            }
            rows.append(row)

        return pd.DataFrame(rows)

    def _param_cols(self, params: StrategyParams) -> dict:
        return {
            "ADX": params.adx_period if params.adx_period is not None else "N/A",
            "ProtectiveStop": params.protective_stop_ticks if params.protective_stop_ticks is not None else "N/A",
            "LongFailed": params.long_failed_exit if params.long_failed_exit is not None else "N/A",
            "ShortFailed": params.short_failed_exit if params.short_failed_exit is not None else "N/A",
            "Overbought": params.overbought if params.overbought is not None else "N/A",
            "Oversold": params.oversold if params.oversold is not None else "N/A",
            "LongExitAt": params.long_exit_at if params.long_exit_at is not None else "N/A",
            "ShortExitAt": params.short_exit_at if params.short_exit_at is not None else "N/A",
            "Fingerprint": params.fingerprint(),
        }

    def _update_composite(self, strategy_dir: Path, new_date: date, new_report: pd.DataFrame):
        """
        Rebuild composite.csv by merging existing data with the new day's report.
        The composite contains one row per instrument per day.
        """
        composite_path = strategy_dir / "composite.csv"

        if composite_path.exists():
            try:
                existing = pd.read_csv(composite_path)
                # Remove any existing rows for this date to avoid duplicates
                if "Date" in existing.columns:
                    existing = existing[existing["Date"] != new_date.isoformat()]
                composite = pd.concat([existing, new_report], ignore_index=True)
            except Exception:
                composite = new_report.copy()
        else:
            composite = new_report.copy()

        # Sort by date descending
        if "Date" in composite.columns:
            composite["Date"] = pd.to_datetime(composite["Date"])
            composite = composite.sort_values("Date", ascending=False)
            composite["Date"] = composite["Date"].dt.strftime("%Y-%m-%d")

        composite.to_csv(composite_path, index=False)

    def rebuild_composite(self, params: StrategyParams):
        """Rebuild composite from all existing day files (for repair/re-index)."""
        d = self.get_strategy_dir(params)
        if not d.exists():
            return

        all_days = []
        for day_file in sorted(d.glob("????-??-??.csv")):
            try:
                df = pd.read_csv(day_file)
                all_days.append(df)
            except Exception:
                continue

        if not all_days:
            return

        composite = pd.concat(all_days, ignore_index=True)
        if "Date" in composite.columns:
            composite["Date"] = pd.to_datetime(composite["Date"])
            composite = composite.sort_values("Date", ascending=False)
            composite["Date"] = composite["Date"].dt.strftime("%Y-%m-%d")

        composite.to_csv(d / "composite.csv", index=False)

    def get_composite(self, params: StrategyParams) -> pd.DataFrame:
        """Load the composite file for a strategy variant."""
        d = self.get_strategy_dir(params)
        composite_path = d / "composite.csv"
        if composite_path.exists():
            try:
                return pd.read_csv(composite_path)
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

    def get_day_file(self, params: StrategyParams, target_date: date) -> pd.DataFrame:
        """Load a specific day file."""
        d = self.get_strategy_dir(params)
        day_path = d / (target_date.strftime("%Y-%m-%d") + ".csv")
        if day_path.exists():
            try:
                return pd.read_csv(day_path)
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

    def list_day_files(self, params: StrategyParams) -> list[date]:
        """List all available day files for a strategy variant, sorted newest first."""
        d = self.get_strategy_dir(params)
        if not d.exists():
            return []
        dates = []
        for f in d.glob("????-??-??.csv"):
            try:
                dates.append(date.fromisoformat(f.stem))
            except ValueError:
                continue
        return sorted(dates, reverse=True)

    def scan_output_structure(self) -> dict:
        """
        Scan the output directory and return a nested dict:
        {label: {account: [folder_path, ...]}}
        """
        structure = {}
        if not self.output_dir.exists():
            return structure

        for label_dir in sorted(self.output_dir.iterdir()):
            if not label_dir.is_dir():
                continue
            label = label_dir.name
            structure[label] = {}
            for account_dir in sorted(label_dir.iterdir()):
                if not account_dir.is_dir():
                    continue
                account = account_dir.name
                structure[label][account] = []
                for param_dir in sorted(account_dir.iterdir()):
                    if param_dir.is_dir():
                        structure[label][account].append(param_dir)

        return structure

    @staticmethod
    def _safe_name(name: str) -> str:
        """Convert a string to a filesystem-safe folder name."""
        safe = re.sub(r'[<>:"/\\|?*\s]', "_", name)
        return safe.strip("._")
