import os
import csv
from pathlib import Path

INPUT_DIR = './shiphero_attachments_20260313'
OUTPUT_DIR = './fixed_csvs'

def fix_csv_content(content: str) -> str:
    """Fix rows that were incorrectly split due to commas inside cell values."""
    lines = content.splitlines()
    if not lines:
        return content

    # Detect delimiter
    header = lines[0]
    delimiter = ',' if header.count(',') > header.count(';') else ';'
    expected_cols = len(list(csv.reader([header], delimiter=delimiter))[0])

    fixed_lines = []
    i = 0
    merged = 0

    while i < len(lines):
        line = lines[i]
        parsed = list(csv.reader([line], delimiter=delimiter))[0]

        # If this line has fewer columns than expected, it may be a continuation
        if len(parsed) < expected_cols and i > 0 and fixed_lines:
            # Merge with the previous line
            prev = fixed_lines.pop()
            merged_line = prev + ' ' + line.strip()
            fixed_lines.append(merged_line)
            merged += 1
        else:
            fixed_lines.append(line)
        i += 1

    print(f"  → Merged {merged} broken line(s)")
    return '\n'.join(fixed_lines)

def process_csvs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    csv_files = sorted(Path(INPUT_DIR).glob('*.csv'))
    print(f"Found {len(csv_files)} CSV file(s) in {INPUT_DIR}\n")

    for filepath in csv_files:
        filename = filepath.name
        print(f"Processing: {filename}")

        # Try common encodings
        for encoding in ['utf-8-sig', 'utf-8', 'latin-1']:
            try:
                content = filepath.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue

        fixed_content = fix_csv_content(content)
        out_path = os.path.join(OUTPUT_DIR, filename)
        with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(fixed_content)
        print(f"  ✓ Saved: {filename}\n")

    print(f"Done. Fixed CSVs saved to: {os.path.abspath(OUTPUT_DIR)}")

process_csvs()