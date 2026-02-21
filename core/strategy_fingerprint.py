"""
Strategy Fingerprinting System

Identifies unique strategy variants by their parameter combination.
Parameters that distinguish variants:
  - ADX Period (e.g. 14, 29, or N/A if smoothness filter off)
  - Protective Stop Ticks (e.g. 100, 200, or N/A)
  - Long Failed Exit SMI (e.g. -75, or N/A)
  - Short Failed Exit SMI (e.g. 75, or N/A)
  - Overbought (e.g. 70)
  - Oversold (e.g. -70)
  - Long Exit At (e.g. 30)
  - Short Exit At (e.g. -30)
"""

import json
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict, field


@dataclass
class StrategyParams:
    """
    Complete parameter fingerprint for a single strategy variant.
    None means the feature is disabled / N/A.
    """
    label: str                          # NT8 strategy label e.g. "MuddyWaterV4"
    account: str                        # Trading account e.g. "SimHouse 3"
    adx_period: Optional[int] = None    # ADX smoothness filter period, None = off
    protective_stop_ticks: Optional[int] = None   # Ticks, None = off
    long_failed_exit: Optional[float] = None      # e.g. -75.0, None = off
    short_failed_exit: Optional[float] = None     # e.g. 75.0, None = off
    overbought: Optional[float] = None            # e.g. 70.0
    oversold: Optional[float] = None              # e.g. -70.0
    long_exit_at: Optional[float] = None          # e.g. 30.0
    short_exit_at: Optional[float] = None         # e.g. -30.0
    notes: str = ""                               # User notes

    def fingerprint(self) -> str:
        """
        Return a stable short hash uniquely identifying this parameter set.
        Used as a folder name component.
        """
        key = (
            self.label,
            self.account,
            self.adx_period,
            self.protective_stop_ticks,
            self.long_failed_exit,
            self.short_failed_exit,
            self.overbought,
            self.oversold,
            self.long_exit_at,
            self.short_exit_at,
        )
        raw = json.dumps(key, default=str)
        return hashlib.sha1(raw.encode()).hexdigest()[:8].upper()

    def short_description(self) -> str:
        """
        Human-readable one-liner that distinguishes this variant from others
        with the same label+account. Shows only the differentiating params.
        """
        parts = []
        parts.append(f"ADX:{self.adx_period if self.adx_period is not None else 'N/A'}")
        parts.append(f"PS:{self.protective_stop_ticks if self.protective_stop_ticks is not None else 'N/A'}")

        if self.long_failed_exit is not None or self.short_failed_exit is not None:
            lf = self.long_failed_exit if self.long_failed_exit is not None else "N/A"
            sf = self.short_failed_exit if self.short_failed_exit is not None else "N/A"
            parts.append(f"FS:{lf}/{sf}")
        else:
            parts.append("FS:N/A")

        if self.overbought is not None:
            parts.append(f"OB:{self.overbought}")
        if self.oversold is not None:
            parts.append(f"OS:{self.oversold}")
        if self.long_exit_at is not None:
            parts.append(f"LE:{self.long_exit_at}")
        if self.short_exit_at is not None:
            parts.append(f"SE:{self.short_exit_at}")

        return "  |  ".join(parts)

    def full_description(self) -> str:
        """Multi-line description for display in the UI."""
        lines = [
            f"Label:           {self.label}",
            f"Account:         {self.account}",
            f"ADX Period:      {self.adx_period if self.adx_period is not None else 'N/A (off)'}",
            f"Protective Stop: {self.protective_stop_ticks if self.protective_stop_ticks is not None else 'N/A (off)'} ticks",
            f"Failed Exit:     Long {self.long_failed_exit if self.long_failed_exit is not None else 'N/A'}  /  Short {self.short_failed_exit if self.short_failed_exit is not None else 'N/A'}",
            f"Overbought:      {self.overbought if self.overbought is not None else 'N/A'}",
            f"Oversold:        {self.oversold if self.oversold is not None else 'N/A'}",
            f"Long Exit At:    {self.long_exit_at if self.long_exit_at is not None else 'N/A'}",
            f"Short Exit At:   {self.short_exit_at if self.short_exit_at is not None else 'N/A'}",
        ]
        if self.notes:
            lines.append(f"Notes:           {self.notes}")
        lines.append(f"Fingerprint:     {self.fingerprint()}")
        return "\n".join(lines)

    def folder_name(self) -> str:
        """
        Safe folder name for this parameter set.
        Format: ADX{val}_PS{val}_FS{lf}_{sf}_{fp}
        """
        adx = f"ADX{self.adx_period}" if self.adx_period is not None else "ADXNA"
        ps = f"PS{self.protective_stop_ticks}" if self.protective_stop_ticks is not None else "PSNA"
        lf = f"LF{int(self.long_failed_exit)}" if self.long_failed_exit is not None else "LFNA"
        sf = f"SF{int(self.short_failed_exit)}" if self.short_failed_exit is not None else "SFNA"
        return f"{adx}_{ps}_{lf}_{sf}_{self.fingerprint()}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyParams":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def matches_nt8_config(self, config: dict) -> bool:
        """
        Check if an NT8 workspace config dict matches this strategy's params.
        Used to auto-identify which parameter set a strategy execution belongs to.
        """
        if self.label and config.get("label"):
            if self.label.lower() not in config["label"].lower():
                return False
        if self.account and config.get("account"):
            if self.account.lower() not in config["account"].lower():
                return False
        return True


class StrategyRegistry:
    """
    Persistent registry of known strategy variants.
    Stored as JSON in the app data directory.
    Maps strategy execution names to StrategyParams fingerprints.
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.registry_file = data_dir / "strategy_registry.json"
        self._strategies: dict[str, StrategyParams] = {}   # fingerprint -> params
        self._name_map: dict[str, str] = {}                # nt8_exec_name -> fingerprint
        self._load()

    def _load(self):
        if self.registry_file.exists():
            try:
                with open(self.registry_file) as f:
                    data = json.load(f)
                for fp, d in data.get("strategies", {}).items():
                    self._strategies[fp] = StrategyParams.from_dict(d)
                self._name_map = data.get("name_map", {})
            except Exception:
                pass

    def save(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "strategies": {fp: s.to_dict() for fp, s in self._strategies.items()},
            "name_map": self._name_map,
        }
        with open(self.registry_file, "w") as f:
            json.dump(data, f, indent=2)

    def register(self, params: StrategyParams) -> str:
        """Add or update a strategy variant. Returns fingerprint."""
        fp = params.fingerprint()
        self._strategies[fp] = params
        self.save()
        return fp

    def unregister(self, fingerprint: str):
        """Remove a strategy variant by fingerprint."""
        self._strategies.pop(fingerprint, None)
        # Remove from name map too
        self._name_map = {k: v for k, v in self._name_map.items() if v != fingerprint}
        self.save()

    def map_nt8_name(self, nt8_name: str, fingerprint: str):
        """Associate an NT8 execution strategy name with a fingerprint."""
        self._name_map[nt8_name] = fingerprint
        self.save()

    def get_by_fingerprint(self, fp: str) -> Optional[StrategyParams]:
        return self._strategies.get(fp)

    def get_by_nt8_name(self, nt8_name: str) -> Optional[StrategyParams]:
        fp = self._name_map.get(nt8_name)
        if fp:
            return self._strategies.get(fp)
        # Try fuzzy match by label
        name_lower = nt8_name.lower()
        for fp, params in self._strategies.items():
            if params.label and params.label.lower() in name_lower:
                return params
        return None

    def get_by_label(self, label: str) -> list[StrategyParams]:
        """Get all variants for a given strategy label."""
        return [p for p in self._strategies.values()
                if p.label and p.label.lower() == label.lower()]

    def get_by_account(self, account: str) -> list[StrategyParams]:
        return [p for p in self._strategies.values()
                if p.account and p.account.lower() == account.lower()]

    def all_strategies(self) -> list[StrategyParams]:
        return list(self._strategies.values())

    def all_labels(self) -> list[str]:
        return sorted(set(p.label for p in self._strategies.values() if p.label))

    def get_label_account_map(self) -> dict[str, list[str]]:
        """Returns {label: [account1, account2, ...]} for tree display."""
        result: dict[str, list[str]] = {}
        for p in self._strategies.values():
            if p.label not in result:
                result[p.label] = []
            if p.account not in result[p.label]:
                result[p.label].append(p.account)
        return result

    def get_variants_for_label_account(self, label: str, account: str) -> list[StrategyParams]:
        """Get all parameter variants for a specific label+account pair."""
        return [
            p for p in self._strategies.values()
            if p.label == label and p.account == account
        ]

    def find_best_match(self, label: str, account: str, exec_name: str) -> Optional[StrategyParams]:
        """
        Given a strategy execution's label, account, and NT8 name,
        find the best matching registered StrategyParams.
        """
        # 1) Direct name map
        sp = self.get_by_nt8_name(exec_name)
        if sp and sp.label == label and sp.account == account:
            return sp

        # 2) If only one variant exists for this label+account, return it
        variants = self.get_variants_for_label_account(label, account)
        if len(variants) == 1:
            return variants[0]

        # 3) Ambiguous - return None, caller must resolve
        return None
