"""PDF → structured Markdown via pymupdf4llm.

Uses the layout-aware GNN inside pymupdf4llm to produce clean Markdown
that preserves headings, multi-column reading order, and table structure.
Images are intentionally skipped (write_images=False).

Falls back to OCR (via PyMuPDF/Tesseract) for scanned PDFs.
"""

import pymupdf4llm
import pymupdf  # fitz


def parse_pdf(file_path: str) -> list[dict]:
    """Parse a PDF into a list of {page_number, text} dicts.

    Each page's text is structured Markdown produced by pymupdf4llm.
    Empty pages are filtered out.  The returned list is sorted by
    page_number (1-indexed).

    If the PDF is scanned (no selectable text), falls back to OCR.
    """
    # ── Attempt 1: Normal text extraction ──
    try:
        page_chunks = pymupdf4llm.to_markdown(
            file_path,
            page_chunks=True,
            write_images=False,
            use_ocr=False,  # Force disable automatic Tesseract on images
        )
    except Exception as e:
        print(f"[Parser] pymupdf4llm.to_markdown failed for {file_path}: {e}")
        page_chunks = []

    pages = []
    for chunk in page_chunks:
        md_text = chunk.get("text", "").strip()
        if not md_text:
            continue
        page_num = chunk.get("metadata", {}).get("page", 0) + 1
        pages.append({"page_number": page_num, "text": md_text})

    # ── Attempt 2: OCR fallback for scanned PDFs ──
    if not pages:
        print(f"[Parser] No text found via pymupdf4llm. Trying OCR fallback...")
        try:
            doc = pymupdf.open(file_path)
            for i, page in enumerate(doc):
                # get_text("text") extracts embedded text; for scanned pages this is empty
                text = page.get_text("text").strip()
                if not text:
                    # OCR the page — requires Tesseract installed
                    try:
                        tp = page.get_textpage_ocr(language="eng", dpi=300, full=True)
                        text = page.get_text("text", textpage=tp).strip()
                    except Exception as ocr_err:
                        print(f"[Parser] OCR failed on page {i+1}: {ocr_err}")
                        continue
                if text:
                    pages.append({"page_number": i + 1, "text": text})
            doc.close()
            print(f"[Parser] OCR extracted text from {len(pages)} pages.")
        except Exception as e:
            print(f"[Parser] OCR fallback failed: {e}")

    pages.sort(key=lambda p: p["page_number"])
    return pages
