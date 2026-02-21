"""
Claude AI Terminal Panel

Embedded chat interface for the Claude agentic assistant.
Supports streaming responses, command shortcuts, and context injection.
"""

from datetime import date
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QSplitter, QToolButton, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QTextCursor, QFont, QColor

from core.claude_agent import ClaudeAgent
from core.strategy_fingerprint import StrategyParams


class StreamWorker(QObject):
    """Worker thread for streaming Claude responses."""
    token = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, agent: ClaudeAgent, message: str, context_date: date,
                 strategy_filter: StrategyParams = None):
        super().__init__()
        self.agent = agent
        self.message = message
        self.context_date = context_date
        self.strategy_filter = strategy_filter

    def run(self):
        try:
            for chunk in self.agent.chat(
                self.message,
                context_date=self.context_date,
                strategy_filter=self.strategy_filter,
                stream=True,
            ):
                self.token.emit(chunk)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class ClaudeTerminalWidget(QWidget):
    """
    Bottom panel: Chat interface for Claude AI analysis.
    """

    def __init__(self, agent: ClaudeAgent, parent=None):
        super().__init__(parent)
        self.agent = agent
        self._active_strategy: StrategyParams = None
        self._thread: QThread = None
        self._worker: StreamWorker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setObjectName("terminalHeader")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 5, 10, 5)

        icon = QLabel("🧠")
        h_layout.addWidget(icon)

        title = QLabel("CLAUDE AI TERMINAL")
        title.setObjectName("terminalTitle")
        h_layout.addWidget(title)
        h_layout.addStretch()

        self.context_label = QLabel("Context: All Strategies")
        self.context_label.setObjectName("contextLabel")
        h_layout.addWidget(self.context_label)

        btn_clear = QToolButton()
        btn_clear.setText("✕ Clear")
        btn_clear.setObjectName("clearButton")
        btn_clear.clicked.connect(self._clear_chat)
        h_layout.addWidget(btn_clear)

        btn_reset = QToolButton()
        btn_reset.setText("⟳ New Chat")
        btn_reset.setObjectName("clearButton")
        btn_reset.clicked.connect(self._reset_conversation)
        h_layout.addWidget(btn_reset)

        layout.addWidget(header)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setObjectName("chatDisplay")
        layout.addWidget(self.chat_display)

        # Quick prompts
        quick_bar = QWidget()
        quick_bar.setObjectName("quickBar")
        qb_layout = QHBoxLayout(quick_bar)
        qb_layout.setContentsMargins(8, 4, 8, 4)
        qb_layout.setSpacing(6)

        quick_label = QLabel("Quick:")
        quick_label.setObjectName("quickLabel")
        qb_layout.addWidget(quick_label)

        quick_prompts = [
            ("Today Summary", "Summarize today's performance across all strategies"),
            ("Best Variant", "Which parameter variant is performing best and why?"),
            ("Compare", "Compare all variants side by side with win rates and P&L"),
            ("Risk Check", "Flag any strategies with concerning loss patterns today"),
        ]
        for label, prompt in quick_prompts:
            btn = QPushButton(label)
            btn.setObjectName("quickPromptBtn")
            btn.setProperty("prompt", prompt)
            btn.clicked.connect(lambda checked, p=prompt: self._send_message(p))
            qb_layout.addWidget(btn)
        qb_layout.addStretch()
        layout.addWidget(quick_bar)

        # Input bar
        input_bar = QWidget()
        input_bar.setObjectName("inputBar")
        i_layout = QHBoxLayout(input_bar)
        i_layout.setContentsMargins(8, 6, 8, 6)
        i_layout.setSpacing(6)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("chatInput")
        self.input_field.setPlaceholderText("Ask Claude about your strategies... (Enter to send)")
        self.input_field.returnPressed.connect(self._on_enter)
        i_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("sendButton")
        self.send_btn.clicked.connect(self._on_enter)
        i_layout.addWidget(self.send_btn)

        layout.addWidget(input_bar)

        # Welcome message
        self._append_system(
            "TraderOS AI Terminal ready. Ask me anything about your strategies.\n"
            "I can analyze performance, compare variants, identify patterns, and more.\n"
            "Tip: Click a strategy in the tree first to set context, then ask questions."
        )

    def set_active_strategy(self, params: StrategyParams):
        """Set which strategy variant provides context for AI responses."""
        self._active_strategy = params
        if params:
            self.context_label.setText(
                f"Context: {params.label} | {params.account} | {params.fingerprint()}"
            )
        else:
            self.context_label.setText("Context: All Strategies")

    def inject_analysis_request(self, params: StrategyParams):
        """Trigger an AI analysis for a specific strategy."""
        self.set_active_strategy(params)
        self._send_message(
            f"Analyze the performance of {params.label} on account {params.account} "
            f"(variant {params.fingerprint()}, params: {params.short_description()}). "
            "Give me a detailed breakdown with P&L, win rate, profit factor, and your assessment."
        )

    def _on_enter(self):
        text = self.input_field.text().strip()
        if text:
            self._send_message(text)
            self.input_field.clear()

    def _send_message(self, message: str):
        if self._thread and self._thread.isRunning():
            return  # Don't allow concurrent requests

        if not self.agent.is_configured():
            self._append_system(
                "⚠  No API key configured. Go to Tools > Settings > API Key."
            )
            return

        self._append_user(message)
        self._append_assistant_start()

        self._worker = StreamWorker(
            self.agent, message, date.today(), self._active_strategy
        )
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.token.connect(self._append_token)
        self._worker.finished.connect(self._on_stream_done)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)

        self.send_btn.setEnabled(False)
        self.input_field.setEnabled(False)
        self._thread.start()

    def _append_user(self, text: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = cursor.charFormat()
        fmt.setForeground(QColor("#64B5F6"))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"\n▶ You: {text}\n")

        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _append_assistant_start(self):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = cursor.charFormat()
        fmt.setForeground(QColor("#A5D6A7"))
        cursor.setCharFormat(fmt)
        cursor.insertText("\n🧠 Claude: ")

        self.chat_display.setTextCursor(cursor)
        self._response_start_pos = cursor.position()

    def _append_token(self, token: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = cursor.charFormat()
        fmt.setForeground(QColor("#E0E0E0"))
        cursor.setCharFormat(fmt)
        cursor.insertText(token)

        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def _append_system(self, text: str):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = cursor.charFormat()
        fmt.setForeground(QColor("#888888"))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"\n[System] {text}\n")

        self.chat_display.setTextCursor(cursor)

    def _on_stream_done(self):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = cursor.charFormat()
        fmt.setForeground(QColor("#E0E0E0"))
        cursor.setCharFormat(fmt)
        cursor.insertText("\n")
        self.chat_display.setTextCursor(cursor)

        self.send_btn.setEnabled(True)
        self.input_field.setEnabled(True)
        self.input_field.setFocus()

    def _on_error(self, error: str):
        self._append_system(f"Error: {error}")

    def _clear_chat(self):
        self.chat_display.clear()
        self._append_system("Chat cleared.")

    def _reset_conversation(self):
        self.agent.reset_conversation()
        self.chat_display.clear()
        self._append_system("New conversation started. Context reset.")
