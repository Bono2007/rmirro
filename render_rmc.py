#!/usr/bin/python3

# Renderer using rmc (rm -> SVG) + cairosvg (SVG -> PDF).
# Handles multi-page documents by merging individual PDFs.

import sys
import os
import os.path
import subprocess
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(SCRIPT_DIR, ".venv", "bin", "python")
RMC_BIN = os.path.join(SCRIPT_DIR, ".venv", "bin", "rmc")

# Ensure cairosvg can find the cairo library (macOS homebrew)
BREW_PREFIX = subprocess.run(
    ["brew", "--prefix", "cairo"], capture_output=True, text=True
).stdout.strip()
if BREW_PREFIX:
    os.environ["DYLD_LIBRARY_PATH"] = os.path.join(BREW_PREFIX, "lib")


def rm_to_pdf(rm_path, pdf_path):
    """Convert a single .rm file to PDF via SVG intermediate."""
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
        svg_path = tmp.name

    try:
        proc = subprocess.run(
            [RMC_BIN, rm_path, "-t", "svg", "-o", svg_path],
            capture_output=True, text=True
        )
        if proc.returncode != 0 or not os.path.exists(svg_path) or os.path.getsize(svg_path) == 0:
            return False

        # Use cairosvg via venv python to convert SVG -> PDF
        proc = subprocess.run(
            [VENV_PYTHON, "-c",
             f"import cairosvg; cairosvg.svg2pdf(url={svg_path!r}, write_to={pdf_path!r})"],
            capture_output=True, text=True,
            env={**os.environ}
        )
        return proc.returncode == 0 and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
    finally:
        if os.path.exists(svg_path):
            os.unlink(svg_path)


if __name__ == "__main__":
    args = sys.argv[1:]
    assert len(args) == 2, "usage: render_rmc.py infile outfile"

    infile = args[0]   # backup stem path (UUID directory)
    outfile = args[1]  # output PDF path

    # Ensure output directory exists (handles names with / in them)
    os.makedirs(os.path.dirname(outfile), exist_ok=True)

    # Check if it's a PDF/EPUB already (imported document, not handwritten)
    for ext in (".pdf", ".epub"):
        source = infile + ext
        if os.path.exists(source):
            import shutil
            shutil.copy2(source, outfile)
            exit(0)

    # Find .rm files in the document directory
    rm_files = []
    if os.path.isdir(infile):
        for root, dirs, files in os.walk(infile):
            for f in files:
                if f.endswith(".rm"):
                    rm_files.append(os.path.join(root, f))
        rm_files.sort()

    if not rm_files:
        print(f"No .rm files found in {infile}", file=sys.stderr)
        exit(1)

    if len(rm_files) == 1:
        if rm_to_pdf(rm_files[0], outfile):
            exit(0)
        else:
            print("Failed to render page", file=sys.stderr)
            exit(1)

    # Multi-page: render each, then merge
    temp_pdfs = []
    try:
        for rm_file in rm_files:
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp.close()
            if rm_to_pdf(rm_file, tmp.name):
                temp_pdfs.append(tmp.name)
            else:
                os.unlink(tmp.name)

        if not temp_pdfs:
            print("Failed to render any pages", file=sys.stderr)
            exit(1)

        if len(temp_pdfs) == 1:
            os.rename(temp_pdfs[0], outfile)
            temp_pdfs = []
        else:
            # Merge PDFs using venv Python (which has pypdf)
            pdf_list = repr(temp_pdfs)
            merge_code = f"""
from pypdf import PdfWriter, PdfReader
writer = PdfWriter()
for pdf in {pdf_list}:
    reader = PdfReader(pdf)
    for page in reader.pages:
        writer.add_page(page)
writer.write({outfile!r})
"""
            proc = subprocess.run(
                [VENV_PYTHON, "-c", merge_code],
                capture_output=True, text=True
            )
            if proc.returncode != 0:
                print(proc.stderr, end="", file=sys.stderr)
                exit(1)
    finally:
        for pdf in temp_pdfs:
            if os.path.exists(pdf):
                os.unlink(pdf)

    exit(0)
