"""Dark / light themes as a Qt style sheet plus syntax-highlight colours."""
from __future__ import annotations

from string import Template

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0f1115", "panel": "#141720", "surface": "#1b1f2a", "surface2": "#232837",
        "border": "#2a2f3d", "text": "#e6e8ee", "muted": "#8b93a7", "accent": "#4f8cff",
        "accent_hover": "#6a9fff", "user_bubble": "#223456", "ai_bubble": "#161a24",
        "code_bg": "#0b0d12", "code_header": "#171b26", "danger": "#ff6b6b", "success": "#3ecf8e",
        "warn": "#f5b94c", "selection": "#2f4f8f",
        "syn_keyword": "#c792ea", "syn_string": "#a5d6a7", "syn_comment": "#6b7489",
        "syn_number": "#f9a870", "syn_func": "#82aaff", "syn_builtin": "#4dd0e1",
        "syn_key": "#82aaff",
    },
    "light": {
        "bg": "#f5f6f9", "panel": "#ffffff", "surface": "#eef0f5", "surface2": "#e3e6ee",
        "border": "#d4d8e2", "text": "#1c2030", "muted": "#677086", "accent": "#2f6df0",
        "accent_hover": "#1f5bd8", "user_bubble": "#dbe7ff", "ai_bubble": "#ffffff",
        "code_bg": "#f1f3f8", "code_header": "#e6e9f1", "danger": "#d64545", "success": "#1e9e68",
        "warn": "#b9770e", "selection": "#bcd0fb",
        "syn_keyword": "#8e44ad", "syn_string": "#2e7d32", "syn_comment": "#8a93a6",
        "syn_number": "#d35400", "syn_func": "#1f5bd8", "syn_builtin": "#00838f",
        "syn_key": "#1f5bd8",
    },
}

QSS = Template("""
* { font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif; font-size: 10pt; }
QMainWindow, QDialog, #root { background: $bg; }
QWidget { color: $text; }
QToolTip { background: $surface2; color: $text; border: 1px solid $border; padding: 4px; }

#sidebar { background: $panel; border-right: 1px solid $border; }
#appTitle { font-size: 11.5pt; font-weight: 600; }
#localBadge { color: $success; font-size: 9pt; }
#mutedLabel { color: $muted; font-size: 9pt; }
#sectionLabel { color: $muted; font-size: 8.5pt; font-weight: 600; }

QPushButton { background: $surface; border: 1px solid $border; border-radius: 8px; padding: 7px 12px; }
QPushButton:hover { background: $surface2; }
QPushButton:disabled { color: $muted; background: $surface; }
QPushButton#primaryBtn { background: $accent; border-color: $accent; color: white; font-weight: 600; }
QPushButton#primaryBtn:hover { background: $accent_hover; }
QPushButton#dangerBtn { background: $danger; border-color: $danger; color: white; font-weight: 600; }
QPushButton#ghostBtn { background: transparent; border: 1px solid transparent; color: $muted; padding: 4px 8px; }
QPushButton#ghostBtn:hover { background: $surface2; color: $text; }
QPushButton#copyBtn { background: transparent; border: 1px solid $border; border-radius: 6px;
                      padding: 3px 10px; font-size: 9pt; color: $muted; }
QPushButton#copyBtn:hover { color: $text; background: $surface2; }
QPushButton#suggestion { text-align: left; padding: 14px 16px; background: $surface;
                         border: 1px solid $border; border-radius: 12px; }
QPushButton#suggestion:hover { border-color: $accent; background: $surface2; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: $surface; border: 1px solid $border;
    border-radius: 8px; padding: 6px 8px; selection-background-color: $selection; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: $accent; }
QComboBox QAbstractItemView { background: $surface; border: 1px solid $border; selection-background-color: $selection; }
QCheckBox { spacing: 8px; }

QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 9px 10px; border-radius: 8px; margin: 1px 0; }
QListWidget::item:hover { background: $surface; }
QListWidget::item:selected { background: $surface2; color: $text; }

QScrollArea { border: none; background: transparent; }
#chatContainer { background: $bg; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

#bubbleUser { background: $user_bubble; border-radius: 14px; }
#bubbleAI { background: $ai_bubble; border: 1px solid $border; border-radius: 14px; }
#bubbleError { background: $ai_bubble; border: 1px solid $danger; border-radius: 14px; }
#roleLabel { font-weight: 600; font-size: 9.5pt; }
#timeLabel, #statsLabel { color: $muted; font-size: 8.5pt; }
#thinkingLabel { color: $muted; font-style: italic; }
#noticeLabel { color: $warn; font-size: 9pt; padding: 2px 6px; }
QTextBrowser { background: transparent; border: none; selection-background-color: $selection; }

#codeFrame { background: $code_bg; border: 1px solid $border; border-radius: 10px; }
#codeHeader { background: $code_header; border-top-left-radius: 10px; border-top-right-radius: 10px;
              border-bottom: 1px solid $border; }
#codeLang { color: $muted; font-size: 8.5pt; font-weight: 600; }
QPlainTextEdit#codeEdit { background: transparent; border: none; color: $text;
                          selection-background-color: $selection; }

#composer { background: $panel; border-top: 1px solid $border; }
#composerBox { background: $surface; border: 1px solid $border; border-radius: 14px; }
QPlainTextEdit#composerEdit { background: transparent; border: none; padding: 4px; font-size: 10.5pt;
                              selection-background-color: $selection; }
#banner { background: $surface; border-bottom: 1px solid $warn; }
#bannerText { color: $text; }
#welcomeTitle { font-size: 22pt; font-weight: 700; }
#welcomeSub { color: $muted; font-size: 11pt; }
QMenu { background: $surface; border: 1px solid $border; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background: $surface2; }
""")


def tokens(theme: str) -> dict[str, str]:
    return THEMES.get(theme, THEMES["dark"])


def stylesheet(theme: str) -> str:
    return QSS.substitute(tokens(theme))
