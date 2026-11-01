from datetime import datetime

from history import History, HistoryEntry


class TestHistory:
    def test_newest_first_and_bounded(self):
        h = History(max_items=3)
        for i in range(5):
            h.add(f"A{i}", "p", "t", f"r{i}", "gemini")

        assert len(h) == 3
        assert [e.result for e in h.entries()] == ["r4", "r3", "r2"]

    def test_clear(self):
        h = History()
        h.add("A", "p", "t", "r", "gemini")
        h.clear()
        assert h.entries() == []

    def test_entries_returns_copy(self):
        h = History()
        h.add("A", "p", "t", "r", "gemini")
        h.entries().clear()
        assert len(h) == 1


class TestMenuTitle:
    def test_strips_icon_and_truncates(self):
        e = HistoryEntry("≡  Resumir", "p", "t", "uno  dos\ntres " * 20, "gemini",
                         timestamp=datetime(2026, 1, 1, 9, 5))
        title = e.menu_title(width=20)
        assert title.startswith("09:05 · Resumir · uno dos tres")
        assert title.endswith("…")
        assert len(title.split(" · ")[-1]) == 20


class TestOnChange:
    def test_called_on_add_and_clear(self):
        calls = []
        h = History(on_change=lambda: calls.append(1))
        h.add("A", "p", "t", "r", "gemini")
        h.clear()
        assert len(calls) == 2

    def test_listener_errors_are_ignored(self):
        def boom():
            raise RuntimeError("x")

        h = History(on_change=boom)
        h.add("A", "p", "t", "r", "gemini")
        assert len(h) == 1
