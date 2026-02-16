"""
PDF report generation for tap tone analysis.

Note: PDF generation requires additional dependencies.
For basic PDF, we generate HTML and use browser print-to-PDF,
or optionally use weasyprint if installed.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

from analyzer.reports.html_report import generate_html_report


def generate_pdf_report(
    session_meta: Dict[str, Any],
    spectrum_data: Dict[str, Any],
    peaks: List[Dict[str, float]],
    wood_properties: Optional[Dict[str, Any]] = None,
    coherence_stats: Optional[Dict[str, Any]] = None,
    output_path: str = "report.pdf"
) -> str:
    """
    Generate a PDF report for tap tone analysis.

    This function first generates an HTML report, then converts it to PDF.
    If weasyprint is not installed, it saves the HTML and instructs the user
    to print to PDF from their browser.

    Args:
        session_meta: Session metadata
        spectrum_data: Spectrum data
        peaks: List of detected peaks
        wood_properties: Estimated wood properties
        coherence_stats: Coherence quality statistics
        output_path: Path for the output PDF

    Returns:
        Path to the generated file
    """
    # Generate HTML first
    html_content = generate_html_report(
        session_meta=session_meta,
        spectrum_data=spectrum_data,
        peaks=peaks,
        wood_properties=wood_properties,
        coherence_stats=coherence_stats
    )

    output_path = Path(output_path)

    # Try to use weasyprint if available
    try:
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(str(output_path))
        return str(output_path)
    except ImportError:
        pass

    # Fallback: save HTML and let user print to PDF
    html_path = output_path.with_suffix('.html')
    html_path.write_text(html_content, encoding='utf-8')

    print(f"PDF generation requires 'weasyprint' package.")
    print(f"HTML report saved to: {html_path}")
    print(f"Open in browser and use Print > Save as PDF")

    return str(html_path)


def check_pdf_support() -> bool:
    """Check if PDF generation is supported."""
    try:
        import weasyprint
        return True
    except ImportError:
        return False
