#!/usr/bin/env python3
"""Smoke test: Steps A and B (Docling parse + chunk) work in the installed package.

Generates a tiny one-page PDF, then runs the pipeline's own parse and chunk stages on it.
No Ollama, no Qdrant, no LLM. It exists because the CI docker job otherwise only proves the
image builds and the API answers; Docling's native dependencies (e.g. the OpenCV that
rapidocr pulls in, which needs libGL) are first loaded on the first conversion, so a missing
system library only shows up when a user ingests their first PDF.

Run inside the image, from any directory:

    docker compose exec -T reqbot python - < build/smoke_parse_chunk.py

The first run downloads Docling's layout/table models from Hugging Face (about 0.5 GB), so
this needs network access. Exits 0 on success, 1 on failure.
"""
import json
import sys
import tempfile
from pathlib import Path

LINES = [
    (16, "1. Access Control"),
    (11, "The organization shall enforce approved authorizations for logical access to systems."),
    (11, "Users must authenticate before accessing any information system component."),
    (11, "Administrators shall review account privileges at least annually."),
    (16, "2. Audit Logging"),
    (11, "The system shall generate audit records for security-relevant events."),
    (11, "Audit logs must be protected from unauthorized modification or deletion."),
]


def write_minimal_pdf(path: Path) -> None:
    """Write a valid one-page text PDF (hand-built so no PDF library is needed)."""
    ops, y = ["BT"], 740
    for size, text in LINES:
        ops.append(f"/F1 {size} Tf 1 0 0 1 72 {y} Tm ({text}) Tj")
        y -= size + 16
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    path.write_bytes(bytes(out))


def main() -> int:
    from pipeline import chunk_text, section_parser

    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "smoke.pdf"
        write_minimal_pdf(pdf)
        parsed = section_parser.run(str(pdf), tmp)
        chunks_path = chunk_text.run_structure_aware(
            str(Path(tmp) / "smoke_chunks.jsonl"), ancestry_result=parsed, skip_sections=[]
        )
        chunks = [json.loads(line) for line in Path(chunks_path).read_text().splitlines() if line]
    if not chunks:
        print("FAIL: parsing succeeded but produced no chunks", file=sys.stderr)
        return 1
    print(f"OK: Docling parsed the PDF and produced {len(chunks)} chunk(s)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # report any import/native-library failure plainly
        print(f"FAIL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
