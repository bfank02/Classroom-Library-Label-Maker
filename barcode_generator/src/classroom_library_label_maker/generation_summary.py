"""Shared human-readable generation completion summaries.

Qt-free helpers used by the GUI controller and CLI. Warning *collection*
stays in
:class:`~classroom_library_label_maker.services.workbook_generation_service.WorkbookGenerationService`;
these helpers only format
:class:`~classroom_library_label_maker.models.WorkbookGenerationResult`.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.models import (
    EnrichmentSummary,
    GenerationCompletionState,
    WorkbookGenerationResult,
)

# Cap detailed CLI warning lines so huge inventories stay readable.
_CLI_WARNING_DETAIL_LIMIT = 20
# Max review items shown in GUI / CLI enrichment detail.
_REVIEW_ITEM_DISPLAY_LIMIT = 5


def gui_completion_status(
    result: WorkbookGenerationResult,
    *,
    updated_inventory_path: Path | None = None,
) -> str:
    """Return a concise status-line message for a completed generation run.

    When enrichment produced review items, appends an ISBN Lookup Summary
    (found count, needs-review count, up to five book titles). When an
    updated inventory workbook was written after review, appends a short
    Generation Complete block with both saved paths.
    """
    counts = _label_page_phrase(result)
    output = result.output_path if result.output_path is not None else "(unknown)"
    pdf = result.pdf_output_path

    if result.completion_state is GenerationCompletionState.SUCCESS_WITH_WARNINGS:
        warning_word = "warning" if result.warning_count == 1 else "warnings"
        base = (
            f"Saved with {result.warning_count} {warning_word} — "
            f"review before printing. {counts}. Workbook: {output}."
        )
        if pdf is not None:
            base = f"{base} Print from PDF: {pdf}."
    elif pdf is not None:
        base = (
            f"Done — {counts}. Print the PDF for sharp barcodes: {pdf}. "
            f"Workbook also saved: {output}."
        )
    else:
        base = f"Done — {counts}. Saved to {output}. Ready to print."

    parts = [base]
    enrichment_block = _isbn_lookup_summary_lines(result.enrichment)
    if enrichment_block:
        parts.append("\n".join(enrichment_block))
    inventory_block = _saved_files_summary(
        label_workbook=result.output_path,
        updated_inventory=updated_inventory_path,
    )
    if inventory_block:
        parts.append("\n".join(inventory_block))
    return "\n\n".join(parts)


def cli_completion_lines(
    result: WorkbookGenerationResult,
    *,
    updated_inventory_path: Path | None = None,
) -> tuple[str, ...]:
    """Return stdout lines for a completed generation run (including warnings)."""
    lines: list[str] = []
    if result.completion_state is GenerationCompletionState.SUCCESS_WITH_WARNINGS:
        warning_word = "warning" if result.warning_count == 1 else "warnings"
        lines.append(
            f"Generation complete with {result.warning_count} {warning_word}"
        )
        lines.append("Review the workbook before printing.")
    else:
        lines.append("Generation complete")
        lines.append("Ready to print.")

    lines.append("")
    lines.append(f"Books imported: {result.books_imported}")
    lines.append(f"Books processed: {result.books_processed}")
    lines.append(f"Labels created: {result.labels_created}")
    lines.append(f"Pages created: {result.pages_created}")
    lines.append(f"Barcodes generated: {result.barcodes_generated}")
    lines.append(f"Barcodes reused: {result.barcodes_reused}")
    if result.enrichment is not None and result.enrichment.enabled:
        enrichment = result.enrichment
        lines.append("")
        lines.append("ISBN enrichment:")
        lines.append(f"  Books with ISBN: {enrichment.books_with_isbn}")
        lines.append(f"  Books looked up: {enrichment.books_looked_up}")
        lines.append(f"  ISBNs found: {enrichment.isbns_found}")
        lines.append(f"  Ambiguous matches: {enrichment.ambiguous_matches}")
        lines.append(f"  Not found: {enrichment.not_found}")
        lines.append(f"  Lookup errors: {enrichment.lookup_errors}")
        lines.append(f"  Cache hits: {enrichment.cache_hits}")
        lines.append(f"  Cache misses: {enrichment.cache_misses}")
        lines.extend(_isbn_lookup_summary_lines(enrichment, indent="  "))
    lines.append("")
    lines.append(f"Label workbook: {result.output_path}")
    if result.pdf_output_path is not None:
        lines.append(f"Print-ready PDF: {result.pdf_output_path}")
        lines.append("Print the PDF (not Excel) for scannable barcodes.")
    if updated_inventory_path is not None:
        lines.append(f"Updated inventory workbook: {updated_inventory_path}")
    lines.append("")
    lines.append(f"Elapsed time: {result.elapsed_seconds:.3f}s")

    if result.has_warnings:
        lines.append("")
        lines.append(f"Warnings ({result.warning_count}):")
        shown = result.warnings[:_CLI_WARNING_DETAIL_LIMIT]
        for warning in shown:
            lines.append(f"  - {warning.message}")
        remaining = result.warning_count - len(shown)
        if remaining > 0:
            lines.append(f"  … and {remaining} more")

    return tuple(lines)


def _saved_files_summary(
    *,
    label_workbook: Path | None,
    updated_inventory: Path | None,
) -> list[str]:
    """Teacher-facing block when an updated inventory workbook was written."""
    if updated_inventory is None:
        return []
    label_name = (
        label_workbook.name if label_workbook is not None else "(label workbook)"
    )
    return [
        "Generation Complete",
        "✓ Label workbook created",
        "✓ Inventory workbook updated",
        "",
        "Saved:",
        f"• {label_name}",
        f"• {updated_inventory.name}",
    ]


def _isbn_lookup_summary_lines(
    enrichment: EnrichmentSummary | None,
    *,
    indent: str = "",
) -> list[str]:
    """Format the teacher-facing ISBN lookup review block.

    Returns an empty list when enrichment did not run or there is nothing
    useful to show (no finds and no review items).
    """
    if enrichment is None or not enrichment.enabled:
        return []
    needs = enrichment.needs_review_count
    if needs == 0:
        return []

    lines = [
        f"{indent}ISBN Lookup Summary",
        f"{indent}✓ Found automatically: {enrichment.isbns_found}",
        f"{indent}⚠ Needs Review: {needs}",
    ]
    shown = enrichment.review_items[:_REVIEW_ITEM_DISPLAY_LIMIT]
    for item in shown:
        lines.append(f"{indent}{item.title} — {item.message}")
    remaining = needs - len(shown)
    if remaining > 0:
        lines.append(f"{indent}...and {remaining} more.")
    return lines


def _label_page_phrase(result: WorkbookGenerationResult) -> str:
    labels = result.labels_created
    pages = result.pages_created
    label_word = "label" if labels == 1 else "labels"
    page_word = "page" if pages == 1 else "pages"
    return f"{labels} {label_word} on {pages} {page_word}"
