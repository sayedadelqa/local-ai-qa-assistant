"""Small regex-based syntax highlighter for the languages the assistant produces most."""
from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

PY_KW = ("and as assert async await break class continue def del elif else except finally for from "
         "global if import in is lambda nonlocal not or pass raise return try while with yield "
         "None True False self cls")
PY_BUILTINS = ("print len range open str int float dict list set tuple bool type isinstance super "
               "enumerate zip map filter sorted min max sum any all")
JS_KW = ("const let var function return if else for while do switch case break continue new class "
         "extends import export from default async await try catch finally throw typeof instanceof "
         "in of this null undefined true false")
TS_KW = JS_KW + (" interface type enum implements public private protected readonly as namespace "
                 "declare abstract")
SQL_KW = ("select from where and or not insert into values update set delete create table alter drop "
          "join left right inner outer full on group by order having limit offset as distinct union "
          "all null is in like between exists case when then else end primary key foreign references "
          "index count sum avg min max")
BASH_KW = ("if then else elif fi for while do done case esac in function return exit export echo cd "
           "ls cat grep sed awk pip python pytest npm npx git curl source")
GHERKIN_KW = "Feature Scenario Outline Given When Then And But Background Examples"

ALIASES = {
    "py": "python", "python3": "python", "js": "javascript", "node": "javascript",
    "ts": "typescript", "sh": "bash", "shell": "bash", "zsh": "bash", "powershell": "bash",
    "ps1": "bash", "cmd": "bash", "bat": "bash", "yml": "yaml", "jsonc": "json",
    "feature": "gherkin", "postgresql": "sql", "mysql": "sql",
}

STRING_RE = r"\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*'"
NUMBER_RE = r"\b\d+(?:\.\d+)?\b"


def _words(s: str) -> str:
    return r"\b(?:" + "|".join(s.split()) + r")\b"


def normalize_lang(lang: str) -> str:
    lang = (lang or "").lower()
    return ALIASES.get(lang, lang)


class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document, lang: str, colors: dict[str, str]):
        super().__init__(document)
        self.lang = normalize_lang(lang)
        self.colors = colors
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self.multi: list[tuple[QRegularExpression, QRegularExpression, QTextCharFormat]] = []
        self._build()

    def _fmt(self, key: str, italic: bool = False, bold: bool = False) -> QTextCharFormat:
        f = QTextCharFormat()
        f.setForeground(QColor(self.colors[key]))
        f.setFontItalic(italic)
        if bold:
            f.setFontWeight(QFont.Weight.DemiBold)
        return f

    def _add(self, pattern: str, key: str, ci: bool = False, **kw) -> None:
        rx = QRegularExpression(pattern)
        if ci:
            rx.setPatternOptions(QRegularExpression.PatternOption.CaseInsensitiveOption)
        self.rules.append((rx, self._fmt(key, **kw)))

    def _add_multi(self, start: str, end: str, key: str, italic: bool = False) -> None:
        self.multi.append((QRegularExpression(start), QRegularExpression(end), self._fmt(key, italic=italic)))

    def _build(self) -> None:
        lang = self.lang
        if lang == "python":
            self._add(_words(PY_BUILTINS), "syn_builtin")
            self._add(_words(PY_KW), "syn_keyword")
            self._add(r"\b[A-Za-z_]\w*(?=\()", "syn_func")
            self._add(r"@\w+(?:\.\w+)*", "syn_func")
        elif lang in ("javascript", "typescript"):
            self._add(_words(TS_KW if lang == "typescript" else JS_KW), "syn_keyword")
            self._add(r"\b[A-Za-z_$][\w$]*(?=\()", "syn_func")
        elif lang == "sql":
            self._add(_words(SQL_KW), "syn_keyword", ci=True)
        elif lang == "bash":
            self._add(_words(BASH_KW), "syn_keyword")
            self._add(r"\$\{?\w+\}?", "syn_builtin")
            self._add(r"(?<=\s)--?[A-Za-z][\w-]*", "syn_func")
        elif lang == "yaml":
            self._add(r"^\s*-?\s*[\w.\-\"' ]+(?=:)", "syn_key")
            self._add(r"\b(?:true|false|null|yes|no)\b", "syn_keyword")
        elif lang == "json":
            self._add(r"\"(?:[^\"\\]|\\.)*\"(?=\s*:)", "syn_key")
            self._add(r"\b(?:true|false|null)\b", "syn_keyword")
        elif lang == "gherkin":
            self._add(_words(GHERKIN_KW), "syn_keyword", bold=True)
        # strings / numbers for everything (JSON keys are drawn after strings below)
        self._add(NUMBER_RE, "syn_number")
        self._add(STRING_RE, "syn_string")
        if lang == "json":
            self._add(r"\"(?:[^\"\\]|\\.)*\"(?=\s*:)", "syn_key")
        if lang == "yaml":
            self._add(r"^\s*-?\s*[\w.\-]+(?=:)", "syn_key")
        # comments last so they win
        if lang in ("python", "bash", "yaml", "gherkin", "") or lang not in (
                "javascript", "typescript", "sql", "json"):
            self._add(r"(?:^|\s)#.*$", "syn_comment", italic=True)
        if lang in ("javascript", "typescript"):
            self._add(r"//.*$", "syn_comment", italic=True)
        if lang == "sql":
            self._add(r"--.*$", "syn_comment", italic=True)
        # multi-line constructs
        if lang == "python":
            self._add_multi(r'"""', r'"""', "syn_string")
            self._add_multi(r"'''", r"'''", "syn_string")
        if lang in ("javascript", "typescript"):
            self._add_multi(r"`", r"`", "syn_string")
            self._add_multi(r"/\*", r"\*/", "syn_comment", italic=True)
        if lang == "sql":
            self._add_multi(r"/\*", r"\*/", "syn_comment", italic=True)

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt API)
        for rx, fmt in self.rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
        self._highlight_multiline(text)

    def _highlight_multiline(self, text: str) -> None:
        self.setCurrentBlockState(0)
        prev = self.previousBlockState()
        for idx, (start, end, fmt) in enumerate(self.multi, 1):
            if prev == idx:
                begin, search_from = 0, 0
            else:
                m = start.match(text)
                if not m.hasMatch():
                    continue
                begin = m.capturedStart()
                search_from = begin + m.capturedLength()
            while begin >= 0:
                em = end.match(text, search_from)
                if em.hasMatch():
                    self.setFormat(begin, em.capturedEnd() - begin, fmt)
                    nm = start.match(text, em.capturedEnd())
                    if nm.hasMatch():
                        begin = nm.capturedStart()
                        search_from = begin + nm.capturedLength()
                    else:
                        begin = -1
                else:
                    self.setCurrentBlockState(idx)
                    self.setFormat(begin, len(text) - begin, fmt)
                    begin = -1
