#!/usr/bin/env python3
"""Terminal annotation tool for the human study of the judge's labels.

The annotator labels the role of every candidate explanation in the model's final answer. After
an item is committed, the tool shows which candidate was the irrelevant cue, the judge's label
and a running agreement count (switch this off with --no-reveal). Only the labels committed
before the reveal are scored.

Each annotator runs one pass:
  .venv/bin/python scripts/human_gold_tui.py --annotator 1
Output: analysis/human_gold/annot_1.ndjson (append-only, one line per item, flushed after every
commit; relaunching skips items already done).

Keys
  Up/Down, PgUp/PgDn   scroll the text pane
  p / r / a            label the highlighted candidate: primary / rejected / absent
  u                    undo the last label of this item
  s                    skip this item (recorded, never scored)
  c                    show/hide the model's reasoning trace (if any)
  h                    help (rubric summary)
  q                    save and quit

Other flags: --no-reveal, --status (progress only), --packet/--key/--out (paths),
--selftest (logic checks without a terminal).
"""
from __future__ import annotations

import argparse
import curses
import json
import os
import sys
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HG = REPO / "analysis/human_gold"
ROLE_KEYS = {"p": "primary", "r": "considered_rejected", "a": "absent"}
ROLE_SHORT = {"primary": "primary", "considered_rejected": "rejected", "absent": "absent"}
RUBRIC_SUMMARY = [
    "Role of each candidate direction ON THE FINAL ANSWER (not the reasoning):",
    "  primary   the final recommendation rests on it (a leading hypothesis / the",
    "            main course of action). Long discussion alone is NOT primary; a",
    "            direction engaged only to be reframed or set aside is NOT primary.",
    "  rejected  explicitly considered, then dismissed, de-prioritised or reframed.",
    "  absent    not engaged at all.",
    "Judge every direction on its own. Ignore which answer you would have given.",
]


# ------------------------------------------------------------------ persistence
def load_packet(path: Path) -> list[dict]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items


def load_done(out_path: Path, expected: dict[str, list[str]]) -> dict[str, dict]:
    """item_id -> record for lines that are complete (all letters labelled) or skipped."""
    done: dict[str, dict] = {}
    if not out_path.exists():
        return done
    for line in out_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            iid = rec["item_id"]
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        if rec.get("skipped"):
            done[iid] = rec
            continue
        got = {lab.get("direction_id"): lab.get("role_in_final_answer") for lab in rec.get("labels", [])}
        need = expected.get(iid, [])
        if need and all(got.get(k) in ROLE_KEYS.values() for k in need):
            done[iid] = rec
    return done


def append_record(out_path: Path, rec: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def tally(done: dict[str, dict], key: dict) -> tuple[int, int]:
    """(agreements, scored) on the distractor role over committed items."""
    agree = scored = 0
    for iid, rec in done.items():
        if rec.get("skipped"):
            continue
        e = key.get(iid)
        if not e or not e.get("distractor_letter") or not e.get("deepseek_distractor_role"):
            continue
        mine = {lab["direction_id"]: lab["role_in_final_answer"] for lab in rec["labels"]}.get(e["distractor_letter"])
        if mine is None:
            continue
        scored += 1
        agree += int(mine == e["deepseek_distractor_role"])
    return agree, scored


# ------------------------------------------------------------------ rendering
def wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    for para in text.split("\n"):
        if not para.strip():
            out.append("")
            continue
        out.extend(textwrap.wrap(para, width=width, replace_whitespace=False) or [""])
    return out


def render_lines(item: dict, show_cot: bool, width: int) -> list[tuple[str, int]]:
    """Return (text, attr) lines for the scrollable pane."""
    L: list[tuple[str, int]] = []
    bold = curses.A_BOLD if "curses" in sys.modules and hasattr(curses, "A_BOLD") else 0
    L.append(("SCENARIO", bold))
    L += [(t, 0) for t in wrap(item["scenario"], width)]
    L.append(("", 0))
    if item.get("cot"):
        if show_cot:
            L.append(("MODEL REASONING TRACE  (c to hide)", bold))
            L += [(t, 0) for t in wrap(item["cot"], width)]
            L.append(("", 0))
        else:
            L.append(("[model reasoning trace hidden; press c to show]", 0))
            L.append(("", 0))
    L.append(("MODEL FINAL ANSWER", bold))
    L += [(t, 0) for t in wrap(item["final_answer"], width)]
    L.append(("", 0))
    L.append(("CANDIDATE DIRECTIONS", bold))
    L += [(t, 0) for t in wrap(item["directions_block"], width)]
    return L


# ------------------------------------------------------------------ the app
class App:
    def __init__(self, items, key, out_path, annotator, reveal=True):
        self.items = items
        self.key = key
        self.out_path = out_path
        self.annotator = annotator
        self.reveal = reveal
        self.expected = {it["item_id"]: it["expected_letters"] for it in items}
        self.done = load_done(out_path, self.expected)
        self.queue = [it for it in items if it["item_id"] not in self.done]
        self.pos = 0

    # -- per-item state
    def start_item(self):
        self.labels: dict[str, str] = {}
        self.scroll = 0
        self.show_cot = False
        self.t0 = time.time()

    def current(self):
        return self.queue[self.pos] if self.pos < len(self.queue) else None

    def next_letter(self, item):
        for k in item["expected_letters"]:
            if k not in self.labels:
                return k
        return None

    def commit(self, item):
        rec = {
            "item_id": item["item_id"],
            "annotator": self.annotator,
            "labels": [{"direction_id": k, "role_in_final_answer": self.labels[k]} for k in item["expected_letters"]],
            "seconds": round(time.time() - self.t0, 1),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        append_record(self.out_path, rec)
        self.done[item["item_id"]] = rec
        return rec

    def skip(self, item):
        rec = {"item_id": item["item_id"], "annotator": self.annotator, "skipped": True,
               "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        append_record(self.out_path, rec)
        self.done[item["item_id"]] = rec

    def reveal_text(self, item, rec) -> list[str]:
        e = self.key.get(item["item_id"], {})
        mine = {lab["direction_id"]: lab["role_in_final_answer"] for lab in rec["labels"]}
        lines = []
        dl, fl = e.get("distractor_letter"), e.get("focal_letter")
        if dl:
            j = e.get("deepseek_distractor_role")
            m = mine.get(dl)
            mark = "agree" if j == m else "DIFFER"
            lines.append(f"Direction {dl} was the low-relevance cue.  judge: {ROLE_SHORT.get(j, j)}   you: {ROLE_SHORT.get(m, m)}   -> {mark}")
        if fl:
            j = e.get("deepseek_focal_role")
            m = mine.get(fl)
            lines.append(f"Direction {fl} was the decisive evidence.   judge: {ROLE_SHORT.get(j, j)}   you: {ROLE_SHORT.get(m, m)}")
        a, n = tally(self.done, self.key)
        if n:
            lines.append(f"Agreement with the judge on the low-relevance cue so far: {a}/{n} ({100*a/n:.1f}%)")
        lines.append("")
        lines.append("n / Enter: next item     q: save and quit")
        return lines

    # -- curses loop
    def run(self, stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        while True:
            item = self.current()
            if item is None:
                self._msg(stdscr, ["All items in this packet are done for annotator "
                                   f"{self.annotator}. Output: {self.out_path}", "", "press any key"])
                stdscr.getch()
                return
            self.start_item()
            state = self._annotate(stdscr, item)
            if state == "quit":
                return
            if state == "skipped":
                self.pos += 1
                continue
            rec = self.commit(item)
            if self.reveal:
                if self._show_reveal(stdscr, item, rec) == "quit":
                    return
            self.pos += 1

    def _msg(self, stdscr, lines):
        stdscr.erase()
        for i, t in enumerate(lines):
            stdscr.addnstr(i, 0, t, curses.COLS - 1)
        stdscr.refresh()

    def _annotate(self, stdscr, item):
        while True:
            self._draw(stdscr, item)
            ch = stdscr.getch()
            h = curses.LINES
            if ch in (curses.KEY_UP,):
                self.scroll = max(0, self.scroll - 1)
            elif ch in (curses.KEY_DOWN,):
                self.scroll += 1
            elif ch == curses.KEY_PPAGE:
                self.scroll = max(0, self.scroll - (h - 8))
            elif ch == curses.KEY_NPAGE:
                self.scroll += (h - 8)
            elif ch in (ord("c"), ord("C")):
                self.show_cot = not self.show_cot
                self.scroll = 0
            elif ch in (ord("h"), ord("H")):
                self._msg(stdscr, RUBRIC_SUMMARY + ["", "press any key"])
                stdscr.getch()
            elif ch in (ord("u"), ord("U")):
                if self.labels:
                    last = [k for k in item["expected_letters"] if k in self.labels][-1]
                    del self.labels[last]
            elif ch in (ord("s"), ord("S")):
                self.skip(item)
                return "skipped"
            elif ch in (ord("q"), ord("Q")):
                return "quit"
            elif chr(ch) in ROLE_KEYS if 0 <= ch < 256 else False:
                k = self.next_letter(item)
                if k is not None:
                    self.labels[k] = ROLE_KEYS[chr(ch)]
                    if self.next_letter(item) is None:
                        return "done"

    def _show_reveal(self, stdscr, item, rec):
        lines = self.reveal_text(item, rec)
        while True:
            self._msg(stdscr, [f"item {item['item_id']} committed."] + [""] + lines)
            ch = stdscr.getch()
            if ch in (ord("n"), ord("N"), 10, 13, curses.KEY_ENTER):
                return "next"
            if ch in (ord("q"), ord("Q")):
                return "quit"

    def _draw(self, stdscr, item):
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        width = max(20, w - 2)
        idx = len(self.done) + 1
        total = len(self.items)
        head = f" item {idx}/{total}   id {item['item_id']}   annotator {self.annotator}   (h help, q quit)"
        stdscr.addnstr(0, 0, head, w - 1, curses.A_REVERSE)
        pane_h = h - 6
        lines = render_lines(item, self.show_cot, width)
        max_scroll = max(0, len(lines) - pane_h)
        self.scroll = min(self.scroll, max_scroll)
        for i, (t, attr) in enumerate(lines[self.scroll:self.scroll + pane_h]):
            stdscr.addnstr(1 + i, 0, t, w - 1, attr)
        more = f"  [{self.scroll + pane_h}/{len(lines)} lines; scroll with arrows]" if max_scroll else ""
        sep = "-" * (w - 1)
        stdscr.addnstr(h - 5, 0, sep, w - 1)
        chosen = "  ".join(f"{k}:{ROLE_SHORT[self.labels[k]]}" for k in item["expected_letters"] if k in self.labels)
        nxt = self.next_letter(item)
        stdscr.addnstr(h - 4, 0, ("labelled so far: " + chosen) if chosen else "labelled so far: (none)", w - 1)
        if nxt:
            stdscr.addnstr(h - 3, 0, f"Role of direction {nxt} on the FINAL ANSWER:  (p)rimary  (r)ejected  (a)bsent", w - 1, curses.A_BOLD)
        stdscr.addnstr(h - 2, 0, "u undo   s skip item   c reasoning trace   h rubric   q save+quit" + more, w - 1)
        stdscr.refresh()


# ------------------------------------------------------------------ status / selftest
def print_status(items, out_dir: Path):
    expected = {it["item_id"]: it["expected_letters"] for it in items}
    files = sorted(out_dir.glob("annot_*.ndjson"))
    if not files:
        print("no annotator files yet")
    for f in files:
        done = load_done(f, expected)
        skipped = sum(1 for r in done.values() if r.get("skipped"))
        print(f"{f.name}: {len(done) - skipped} labelled, {skipped} skipped, {len(items) - len(done)} remaining")


def selftest():
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    items = [{"item_id": "hg-0000", "scenario": "s", "final_answer": "f", "cot": "",
              "directions_block": "A: x\nB: y", "expected_letters": ["A", "B"]},
             {"item_id": "hg-0001", "scenario": "s", "final_answer": "f", "cot": "trace",
              "directions_block": "A: x\nB: y\nC: z", "expected_letters": ["A", "B", "C"]}]
    key = {"hg-0000": {"distractor_letter": "B", "focal_letter": "A",
                       "deepseek_distractor_role": "primary", "deepseek_focal_role": "absent"},
           "hg-0001": {"distractor_letter": "C", "focal_letter": "A",
                       "deepseek_distractor_role": "considered_rejected", "deepseek_focal_role": "primary"}}
    out = tmp / "annot_T.ndjson"
    app = App(items, key, out, "T")
    assert len(app.queue) == 2
    app.start_item(); app.labels = {"A": "absent", "B": "primary"}
    rec = app.commit(items[0])
    assert "agree" in app.reveal_text(items[0], rec)[0]
    # partial (malformed) line must not count as done
    with out.open("a") as fh:
        fh.write(json.dumps({"item_id": "hg-0001", "labels": [{"direction_id": "A", "role_in_final_answer": "primary"}]}) + "\n")
    app2 = App(items, key, out, "T")
    assert [it["item_id"] for it in app2.queue] == ["hg-0001"], app2.queue
    app2.start_item(); app2.skip(items[1])
    app3 = App(items, key, out, "T")
    assert app3.queue == []
    assert tally(app3.done, key) == (1, 1)
    lines = render_lines(items[1], False, 40)
    assert any("hidden" in t for t, _ in lines)
    print("selftest ok:", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator", help="annotator id, e.g. 1, 2, 3")
    ap.add_argument("--packet", default=str(HG / "packet.jsonl"))
    ap.add_argument("--key", default=str(HG / "key.json"))
    ap.add_argument("--out", help="output ndjson (default analysis/human_gold/annot_<annotator>.ndjson)")
    ap.add_argument("--no-reveal", action="store_true", help="never show the judge's label")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    packet = Path(args.packet)
    if not packet.exists():
        sys.exit(f"{packet} not found; run scripts/human_gold_sample.py first")
    items = load_packet(packet)
    if args.status:
        print_status(items, Path(args.out).parent if args.out else HG)
        return
    if not args.annotator:
        sys.exit("--annotator is required (e.g. --annotator 1)")
    key = json.loads(Path(args.key).read_text(encoding="utf-8")) if Path(args.key).exists() else {}
    out = Path(args.out) if args.out else HG / f"annot_{args.annotator}.ndjson"
    app = App(items, key, out, args.annotator, reveal=not args.no_reveal)
    print(f"{len(app.done)} done, {len(app.queue)} to go -> {out}")
    curses.wrapper(app.run)
    print_status(items, out.parent)


if __name__ == "__main__":
    main()
