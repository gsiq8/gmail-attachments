from pathlib import Path
import csv
import io
import os

INPUT_DIR = "./shiphero_attachments_20260313"
OUTPUT_DIR = "./fixed_csvs"


def detect_delimiter(header: str) -> str:
    candidates = [",", ";", "\t"]
    return max(candidates, key=lambda d: header.count(d))


def parse_csv_line(line: str, delimiter: str) -> list[str]:
    return next(csv.reader([line], delimiter=delimiter))


def row_to_csv_line(row: list[str], delimiter: str) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter, lineterminator="")
    writer.writerow(row)
    return buf.getvalue()


def find_text_column(header_row: list[str]) -> int:
    keys = ("description", "details", "note", "notes", "message", "subject")
    for i, col in enumerate(header_row):
        name = (col or "").strip().lower()
        if any(k in name for k in keys):
            return i
    return 5 if len(header_row) > 5 else 0


def fix_row_with_extra_cols(
    parsed: list[str], expected_cols: int, text_col_idx: int, delimiter: str
) -> list[str]:
    if len(parsed) <= expected_cols:
        return parsed

    right_count = expected_cols - text_col_idx - 1
    if right_count < 0:
        return parsed[:expected_cols]

    left = parsed[:text_col_idx]
    right = parsed[-right_count:] if right_count > 0 else []
    mid_end = len(parsed) - right_count if right_count > 0 else len(parsed)
    middle = parsed[text_col_idx:mid_end]

    merged_text = delimiter.join(middle)
    fixed = left + [merged_text] + right

    if len(fixed) < expected_cols:
        fixed += [""] * (expected_cols - len(fixed))
    elif len(fixed) > expected_cols:
        fixed = fixed[:expected_cols]
    return fixed


def fix_csv_content(content: str) -> tuple[str, dict]:
    lines = content.splitlines()
    if not lines:
        return content, {"merged_multiline": 0, "repaired_overflow": 0, "suspicious": 0}

    delimiter = detect_delimiter(lines[0])
    header_raw = lines[0]
    header_row = parse_csv_line(header_raw, delimiter)
    expected_cols = len(header_row)
    text_col_idx = find_text_column(header_row)

    out_lines = [header_raw]  # preserve header exactly
    stats = {"merged_multiline": 0, "repaired_overflow": 0, "suspicious": 0}

    i = 1
    while i < len(lines):
        raw = lines[i]
        parsed = parse_csv_line(raw, delimiter)

        if len(parsed) == expected_cols:
            out_lines.append(raw)  # preserve exact line/value formatting
            i += 1
            continue

        if len(parsed) < expected_cols:
            combined = raw
            joins = 0
            # hard limit avoids swallowing many rows
            while len(parsed) < expected_cols and (i + 1) < len(lines) and joins < 2:
                i += 1
                joins += 1
                combined = combined + " " + lines[i].lstrip()
                parsed = parse_csv_line(combined, delimiter)

            if joins > 0:
                stats["merged_multiline"] += 1

        if len(parsed) > expected_cols:
            parsed = fix_row_with_extra_cols(parsed, expected_cols, text_col_idx, delimiter)
            stats["repaired_overflow"] += 1

        if len(parsed) != expected_cols:
            stats["suspicious"] += 1
            if len(parsed) < expected_cols:
                parsed += [""] * (expected_cols - len(parsed))
            else:
                parsed = parsed[:expected_cols]

        out_lines.append(row_to_csv_line(parsed, delimiter))
        i += 1

    return "\n".join(out_lines), stats


def process_csvs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    csv_files = sorted(Path(INPUT_DIR).glob("*.csv"))
    print(f"Found {len(csv_files)} CSV file(s) in {INPUT_DIR}\n")

    for filepath in csv_files:
        print(f"Processing: {filepath.name}")
        content = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                content = filepath.read_text(encoding=enc)
                break
            except UnicodeDecodeError:
                pass

        if content is None:
            print("  ✗ decode failed")
            continue

        fixed, stats = fix_csv_content(content)
        out = Path(OUTPUT_DIR) / filepath.name
        out.write_text(fixed, encoding="utf-8")

        print(f"  ✓ saved: {out}")
        print(
            f"    merged_multiline={stats['merged_multiline']}, repaired_overflow={stats['repaired_overflow']}, suspicious={stats['suspicious']}\n")


if __name__ == "__main__":
    process_csvs()