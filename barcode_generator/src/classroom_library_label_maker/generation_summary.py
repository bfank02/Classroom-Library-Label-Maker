"""Shared human-readable generation completion summaries.

Qt-free helpers used by the GUI controller and CLI. Warning *collection*
stays in :class:`~classroom_library_label_maker.services.workbook_generation_service.WorkbookGenerationService`;
these helpers only format :class:`~classroom_library_label_maker.models.WorkbookGenerationResult`.
"""

from __future__ import annotations

from classroom_library_label_maker.models import (
    GenerationCompletionState,
    WorkbookGenerationResult,
)

# Cap detailed CLI warning lines so huge inventories stay readable.
_CLI_WARNING_DETAIL_LIMIT = 20


def gui_completion_status(result: WorkbookGenerationResult) -> str:
    """Return a concise status-line message for a completed generation run.

    Does not list individual warnings — only a count and clear review guidance.
    """
    counts = _label_page_phrase(result)
    output = result.output_path if result.output_path is not None else "(unknown)"

    if result.completion_state is GenerationCompletionState.SUCCESS_WITH_WARNINGS:
        warning_word = "warning" if result.warning_count == 1 else "warnings"
        return (
            f"Saved with {result.warning_count} {warning_word} — "
            f"review before printing. {counts}. Saved to {output}."
        )

    return f"Done — {counts}. Saved to {output}. Ready to print."


def cli_completion_lines(result: WorkbookGenerationResult) -> tuple[str, ...]:
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
    lines.append("")
    lines.append(f"Output workbook: {result.output_path}")
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


def _label_page_phrase(result: WorkbookGenerationResult) -> str:
    labels = result.labels_created
    pages = result.pages_created
    label_word = "label" if labels == 1 else "labels"
    page_word = "page" if pages == 1 else "pages"
    return f"{labels} {label_word} on {pages} {page_word}"
