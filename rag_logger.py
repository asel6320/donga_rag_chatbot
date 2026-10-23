import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

LOG_ENABLED = True
LOG_FILE = Path("logs/queries.jsonl")

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")      # 9+ digits with separators
LONG_NUM_RE = re.compile(r"\b[A-Za-z]{0,2}\d{6,}\b")  # passport / ID like AB1234567


def mask_pii(text):
    if not isinstance(text, str):
        return text
    text = EMAIL_RE.sub("[email]", text)
    text = PHONE_RE.sub("[phone]", text)
    return LONG_NUM_RE.sub("[number]", text)


def log_event(event: dict) -> None:
    """Append one record. Logging must never break the assistant, so errors are swallowed."""
    if not LOG_ENABLED:
        return
    try:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), **event}
        record["question"] = mask_pii(record.get("question"))
        record["answer"] = mask_pii(record.get("answer"))
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:                      # noqa: BLE001
        print(f"[logger] could not write log: {e}", file=sys.stderr)


def summarize(path: Path = LOG_FILE) -> None:
    if not path.exists():
        print("No log file yet.")
        return
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = len(rows)
    outcomes = Counter(r.get("outcome") for r in rows)
    print(f"Questions logged: {n}")
    for k, v in outcomes.most_common():
        print(f"  {k:<18} {v:>4}  ({v / n:.0%})")
    totals = sorted(r["total_ms"] for r in rows if "total_ms" in r)
    if totals:
        print(f"Latency (ms): median {totals[len(totals) // 2]}, max {totals[-1]}")
    unanswered = [r["question"] for r in rows if str(r.get("outcome", "")).startswith("fallback")]
    if unanswered:
        print("\nQuestions the bot could not answer (candidates for new documents / better chunks):")
        for q in unanswered[-10:]:
            print("  -", q)


if __name__ == "__main__":
    summarize()