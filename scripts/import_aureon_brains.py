#!/usr/bin/env python3
"""Import Aureon brain corpus from Downloads into brains/aureon/."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUREON_OUT = PROJECT_ROOT / "brains" / "aureon"
EXTRACTED_OUT = AUREON_OUT / "extracted"

sys.path.insert(0, str(PROJECT_ROOT))

from axrlen.ai.aureon_manifest import AUREON_PDF_SOURCES, DEFAULT_AUREON_SOURCE  # noqa: E402

MAX_PDF_CHARS = 80_000


def copy_text_brains(source: Path) -> int:
    count = 0
    for path in source.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".txt", ".md"):
            continue
        dest = AUREON_OUT / path.name
        shutil.copy2(path, dest)
        count += 1
    return count


def extract_pdfs(source: Path) -> int:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("Install pypdf: pip install pypdf")
        return 0

    EXTRACTED_OUT.mkdir(parents=True, exist_ok=True)
    count = 0

    for pdf_name in AUREON_PDF_SOURCES:
        pdf_path = source / pdf_name
        if not pdf_path.is_file():
            continue

        out_name = pdf_path.stem + ".txt"
        out_path = EXTRACTED_OUT / out_name

        try:
            reader = PdfReader(str(pdf_path))
            pages: list[str] = []
            total = 0
            for page in reader.pages:
                text = (page.extract_text() or "").strip()
                if not text:
                    continue
                if total + len(text) > MAX_PDF_CHARS:
                    pages.append(text[: MAX_PDF_CHARS - total])
                    pages.append("\n...[PDF truncated for import]")
                    break
                pages.append(text)
                total += len(text)

            body = "\n\n".join(pages).strip()
            if body:
                header = f"# Extracted from: {pdf_name}\n\n"
                out_path.write_text(header + body, encoding="utf-8")
                count += 1
                print(f"  extracted: {pdf_name} -> {out_path.name} ({len(body)} chars)")
        except Exception as exc:
            print(f"  failed: {pdf_name}: {exc}")

    return count


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_AUREON_SOURCE
    if not source.is_dir():
        print(f"Source not found: {source}")
        sys.exit(1)

    AUREON_OUT.mkdir(parents=True, exist_ok=True)
    print(f"Importing Aureon brains from: {source}")

    txt_count = copy_text_brains(source)
    print(f"Copied {txt_count} .txt/.md brain files to {AUREON_OUT}")

    print("Extracting PDF brains...")
    pdf_count = extract_pdfs(source)
    print(f"Extracted {pdf_count} PDFs to {EXTRACTED_OUT}")

    manifest_src = Path(r"C:\Users\kille\.cursor\skills\aureon\BRAIN_MANIFEST.md")
    if manifest_src.is_file():
        shutil.copy2(manifest_src, PROJECT_ROOT / "brains" / "BRAIN_MANIFEST.md")
        print("Copied BRAIN_MANIFEST.md")

    print("Done.")


if __name__ == "__main__":
    main()
