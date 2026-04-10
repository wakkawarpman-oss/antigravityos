"""
tui.widgets — Custom Textual widgets for the HANNA interface.
"""
from __future__ import annotations

import shlex
from typing import List, Optional, Iterable

from textual import on
from textual.message import Message
from textual.widgets import Input, Static
from textual.suggester import Suggester

from tui.history import CommandHistory

COMMANDS = ["run", "view", "toggle", "export", "help", "clear", "exit"]
ARGUMENTS = {
    "run": ["--mode", "--target", "--modules", "--phones", "--usernames", "--proxy"],
    "view": ["overview", "pipeline", "readiness", "activity"],
    "mode": ["manual", "aggregate", "chain", "full-spectrum"],
    "export": ["stix", "zip", "pdf", "json"],
}

class HannaSuggester(Suggester):
    """Context-aware command suggester for the HANNA terminal."""
    
    async def get_suggestion(self, value: str) -> str | None:
        if not value:
            return None
        
        try:
            tokens = shlex.split(value)
        except ValueError:
            return None
        
        if not tokens:
            return None
        
        # 1. Primary command suggestion
        if len(tokens) == 1 and not value.endswith(" "):
            head = tokens[0].lower()
            for cmd in COMMANDS:
                if cmd.startswith(head) and cmd != head:
                    return cmd
        
        # 2. Argument suggestion
        last_token = tokens[-1]
        is_space_at_end = value.endswith(" ")
        
        if is_space_at_end:
            # Suggest common arguments for the current command
            cmd = tokens[0].lower()
            if cmd in ARGUMENTS:
                return ARGUMENTS[cmd][0]
        else:
            # Complete the current partial argument
            cmd = tokens[0].lower()
            if cmd in ARGUMENTS:
                for arg in ARGUMENTS[cmd]:
                    if arg.startswith(last_token) and arg != last_token:
                        return arg
        
        return None

class HannaCommandBar(Input):
    """
    Advanced command bar with history, context-aware suggestions, 
    and cyberpunk micro-animations.
    """
    
    class CommandSubmitted(Message):
        """Sent when a command is submitted."""
        def __init__(self, command: str) -> None:
            self.command = command
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__(
            placeholder='Type "help" for a list of commands...',
            suggester=HannaSuggester(use_cache=False),
            **kwargs
        )
        self.history_manager = CommandHistory()
        self.history: List[str] = []
        self._history_index: int = -1

    def on_mount(self) -> None:
        """Load history from DB on mount."""
        self.history = self.history_manager.get_all()

    @on(Input.Submitted)
    def handle_submit(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd:
            self.history_manager.append(cmd)
            # Refresh local buffer
            if not self.history or self.history[-1] != cmd:
                self.history.append(cmd)
            self._history_index = -1
        self.post_message(self.CommandSubmitted(cmd))
        self.value = ""

    def action_history_up(self) -> None:
        """Browse history upwards."""
        if not self.history:
            return
        if self._history_index == -1:
            self._history_index = len(self.history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        self.value = self.history[self._history_index]

    def action_history_down(self) -> None:
        """Browse history downwards."""
        if self._history_index == -1:
            return
        self._history_index += 1
        if self._history_index >= len(self.history):
            self._history_index = -1
            self.value = ""
        else:
            self.value = self.history[self._history_index]

    BINDINGS = [
        ("up", "history_up", "Prev Command"),
        ("down", "history_down", "Next Command"),
    ]
