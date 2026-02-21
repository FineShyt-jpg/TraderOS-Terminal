"""
Claude AI Agent Integration

Provides agentic analysis of strategy performance data.
Supports both one-shot analysis and multi-turn conversation.
"""

import os
import json
from datetime import date
from pathlib import Path
from typing import Optional, Generator
import anthropic
import pandas as pd

from core.strategy_fingerprint import StrategyParams, StrategyRegistry
from core.file_organizer import FileOrganizer


SYSTEM_PROMPT = """You are TraderOS, an expert trading performance analyst embedded in a
NinjaTrader strategy monitoring terminal.

You have direct access to real-time and historical strategy performance data for all
registered trading strategies. Each strategy is identified by its parameter fingerprint:
  - ADX Period (smoothness filter, or N/A if off)
  - Protective Stop Ticks (or N/A if off)
  - Long/Short Failed Signal Exit values (or N/A if off)
  - Overbought, Oversold, Long Exit At, Short Exit At threshold values

Your role:
1. Analyze daily and composite performance across strategy variants
2. Identify which parameter sets are performing best/worst
3. Spot patterns in win rates, profit factors, drawdown
4. Answer specific questions about individual strategies or across all strategies
5. Help the user organize, review, and understand their trading data
6. Proactively flag anomalies or notable performance events

Be direct, data-driven, and specific. Always cite the strategy fingerprint or
parameter values when referring to a specific variant. Use dollar values and
percentages precisely from the data provided.

When the user asks you to perform an action (save files, pull data, organize),
describe what you would do and ask for confirmation if needed.
"""


class ClaudeAgent:
    """
    Manages conversation with Claude for trading analysis.
    Supports streaming responses and context injection from strategy data.
    """

    def __init__(
        self,
        registry: StrategyRegistry,
        organizer: FileOrganizer,
        api_key: Optional[str] = None,
    ):
        self.registry = registry
        self.organizer = organizer
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.conversation_history: list[dict] = []
        self.model = "claude-sonnet-4-5"

    def is_configured(self) -> bool:
        return self.client is not None

    def set_api_key(self, key: str):
        self.client = anthropic.Anthropic(api_key=key)

    def reset_conversation(self):
        self.conversation_history = []

    def build_context_block(
        self,
        target_date: Optional[date] = None,
        strategy_filter: Optional[StrategyParams] = None,
    ) -> str:
        """
        Build a context string with current strategy data to inject into Claude.
        """
        lines = ["=== CURRENT STRATEGY DATA ===\n"]
        lines.append(f"Date: {target_date or date.today()}\n")

        strategies = (
            [strategy_filter] if strategy_filter else self.registry.all_strategies()
        )

        if not strategies:
            lines.append("No strategies registered yet.\n")
            return "\n".join(lines)

        for params in strategies:
            lines.append(f"\n--- {params.label} | {params.account} | FP:{params.fingerprint()} ---")
            lines.append(params.short_description())

            if target_date:
                day_df = self.organizer.get_day_file(params, target_date)
                if not day_df.empty:
                    lines.append(f"\nToday ({target_date}):")
                    lines.append(day_df.to_string(index=False))
                else:
                    lines.append(f"\nNo data for {target_date}")

            composite = self.organizer.get_composite(params)
            if not composite.empty:
                # Show summary stats from composite
                if "NetPnL" in composite.columns:
                    total_pnl = composite["NetPnL"].sum()
                    avg_pnl = composite["NetPnL"].mean()
                    lines.append(f"\nComposite Summary ({len(composite)} days):")
                    lines.append(f"  Total Net P&L: ${total_pnl:,.2f}")
                    lines.append(f"  Avg Daily P&L: ${avg_pnl:,.2f}")
                if "WinRate" in composite.columns:
                    avg_wr = composite["WinRate"].mean()
                    lines.append(f"  Avg Win Rate: {avg_wr:.1f}%")
                if "TotalTrades" in composite.columns:
                    total_trades = composite["TotalTrades"].sum()
                    lines.append(f"  Total Trades (all days): {int(total_trades)}")

        return "\n".join(lines)

    def chat(
        self,
        user_message: str,
        context_date: Optional[date] = None,
        strategy_filter: Optional[StrategyParams] = None,
        stream: bool = True,
    ) -> Generator[str, None, None]:
        """
        Send a message to Claude and yield response chunks (streaming).
        Automatically injects relevant strategy context.
        """
        if not self.client:
            yield "[ERROR] No API key configured. Go to Tools > Settings > API Key to add your Anthropic API key."
            return

        # Inject context into the first message of a new conversation or on request
        context_prefix = ""
        if not self.conversation_history or "data:" in user_message.lower():
            context_prefix = self.build_context_block(context_date, strategy_filter) + "\n\n"

        full_user_msg = context_prefix + user_message if context_prefix else user_message

        self.conversation_history.append({
            "role": "user",
            "content": full_user_msg,
        })

        try:
            if stream:
                full_response = ""
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=self.conversation_history,
                ) as stream_obj:
                    for text in stream_obj.text_stream:
                        full_response += text
                        yield text

                self.conversation_history.append({
                    "role": "assistant",
                    "content": full_response,
                })
            else:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=self.conversation_history,
                )
                text = response.content[0].text
                self.conversation_history.append({
                    "role": "assistant",
                    "content": text,
                })
                yield text

        except anthropic.AuthenticationError:
            yield "[ERROR] Invalid API key. Please check your Anthropic API key in Settings."
        except anthropic.RateLimitError:
            yield "[ERROR] Rate limit hit. Please wait a moment and try again."
        except Exception as e:
            yield f"[ERROR] {str(e)}"

    def quick_analysis(
        self,
        params: StrategyParams,
        target_date: Optional[date] = None,
    ) -> str:
        """
        Generate a quick performance analysis for a single strategy variant.
        Returns full text (non-streaming).
        """
        ctx = self.build_context_block(target_date, params)
        prompt = (
            f"{ctx}\n\nProvide a concise performance summary for this strategy variant. "
            "Focus on: net P&L, win rate, profit factor, and any notable patterns. "
            "Be specific with numbers."
        )

        if not self.client:
            return "Configure your Anthropic API key in Settings to enable AI analysis."

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            return f"Analysis error: {e}"

    def compare_variants(self, label: str, target_date: Optional[date] = None) -> str:
        """
        Compare all variants of a strategy label against each other.
        """
        variants = self.registry.get_by_label(label)
        if not variants:
            return f"No variants registered for {label}."

        ctx = self.build_context_block(target_date)
        prompt = (
            f"{ctx}\n\nCompare all variants of the '{label}' strategy. "
            "Rank them by performance. Identify which parameter combination is working best and why. "
            "Be specific about which ADX, protective stop, failed exit values correlate with better results."
        )

        if not self.client:
            return "Configure your Anthropic API key in Settings to enable AI analysis."

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            return f"Comparison error: {e}"
