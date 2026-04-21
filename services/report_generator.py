# services/report_generator.py

from __future__ import annotations
import logging
import os
from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

log = logging.getLogger(__name__)


def generate_pdf_report(
    symbol: str,
    ttype: str,
    result_text: str,
    df: pd.DataFrame,
    best_strategy: str = None,
    best_strategy_scores: dict = None,
    confidence: float = 40.0,
    verdict: str = "Weak signal due to low volume",
) -> str | None:
    """Generate single‐coin PDF report using ReportLab."""
    try:
        # Filter out log lines (e.g., those starting with date like 2025-05-26)
        lines = [
            line
            for line in result_text.split("\n")
            if not line.strip().startswith("20")
        ]
        data = {"header": []}
        current_section = "header"
        in_multi_line_section = False

        # Parse the text into sections
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("=== "):
                current_section = "header"
                data["header"].append(line)
                in_multi_line_section = False
            elif line.startswith("Options:"):
                break
            else:
                first_word = (
                    line.split(":")[0].split()[
                        0] if ":" in line else line.split()[0]
                )
                if first_word in [
                    "Investment",
                    "Risk",
                    "Data",
                    "Support",
                    "Resistance",
                    "ATR",
                    "Recommendation",
                    "Take-Profit",
                    "Stop-Loss",
                    "R/R",
                    "CI",
                    "Profit",
                    "Loss",
                    "Leverage",
                    "Position",
                    "Liquidation",
                    "Margin",
                ]:
                    current_section = "Trade Summary"
                    if "Trade Summary" not in data:
                        data["Trade Summary"] = []
                    data["Trade Summary"].append(line)
                    in_multi_line_section = False
                elif first_word in [
                    "Indicators",
                    "Categories",
                    "Missing",
                    "Warnings",
                    "Market",
                    "Shorting",
                    "Additional",
                    "Intelligent",
                    "###",
                    "**",
                ]:
                    current_section = line
                    if current_section not in data:
                        data[current_section] = []
                    data[current_section].append(line)
                    in_multi_line_section = True
                elif in_multi_line_section:
                    if current_section not in data:
                        data[current_section] = []
                    data[current_section].append(line)
                else:
                    if "Trade Summary" not in data:
                        data["Trade Summary"] = []
                    data["Trade Summary"].append(line)
                    in_multi_line_section = False

        # Define output path
        output_dir = "reports"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(
            output_dir,
            f"report_{symbol}_{ttype}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        # Create PDF using ReportLab
        doc = SimpleDocTemplate(output_file, pagesize=letter)
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        heading_style = styles["Heading2"]
        body_style = ParagraphStyle(
            name="BodyText", parent=styles["Normal"], spaceAfter=12, fontSize=10
        )

        # Build content
        elements = []

        # Title and Date
        elements.append(
            Paragraph(f"Crypto Predictor Report: {symbol}", title_style))
        elements.append(Spacer(1, 12))
        elements.append(
            Paragraph(
                f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}", body_style)
        )
        elements.append(Spacer(1, 12))

        # Sections
        for section, content in data.items():
            if content:  # Only include sections with content
                elements.append(Paragraph(section, heading_style))
                for line in content:
                    elements.append(Paragraph(line, body_style))
                elements.append(Spacer(1, 12))

        # Build the PDF
        doc.build(elements)

        log.info(f"PDF report generated: {output_file}")
        return output_file

    except Exception as e:
        log.error(f"Failed to generate PDF report: {e}")
        print(f"⚠️ Failed to generate PDF report: {str(e)}")
        return None


def generate_multi_pdf_report(multi_results: list[dict], summaries: list[str]) -> str | None:
    """Generate a PDF that contains a table summarizing all coins plus a Summary section."""

    try:
        # 1) Prepare output path
        output_dir = "reports"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(
            output_dir, f"multi_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        # 2) Build document and styles
        doc = SimpleDocTemplate(output_file, pagesize=letter)
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        normal_style = styles["Normal"]
        # We'll create a slightly smaller/body‐text style for the table cells and summary
        table_header_style = ParagraphStyle(
            name="TableHeader",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.white,
            backColor=colors.darkblue,
            alignment=1,  # center
        )
        table_cell_style = ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontSize=9,
            alignment=1,  # center
        )
        summary_heading_style = ParagraphStyle(
            name="SummaryHeading",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.darkblue,
            spaceAfter=6,
        )
        summary_body_style = ParagraphStyle(
            name="SummaryBody",
            parent=styles["Normal"],
            fontSize=10,
            leftIndent=12,
            spaceAfter=12,
        )

        elements = []

        # 3) Title and date
        elements.append(Paragraph("Multi‐Coin Crypto Analysis", title_style))
        elements.append(Spacer(1, 12))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M %Z")
        elements.append(Paragraph(f"Date: {ts}", normal_style))
        elements.append(Spacer(1, 12))

        # 4) Build the table data (header + one row per coin)
        data = [
            [
                Paragraph("Coin", table_header_style),
                Paragraph("Market", table_header_style),
                Paragraph("Score", table_header_style),
                Paragraph("Conf", table_header_style),
                Paragraph("Price", table_header_style),
                Paragraph("TP", table_header_style),
                Paragraph("SL", table_header_style),
                Paragraph("P(Up)/P(Down)", table_header_style),
            ]
        ]

        for r in multi_results:
            row = [
                Paragraph(r["coin"], table_cell_style),
                Paragraph(r["market"], table_cell_style),
                Paragraph(str(r["score"]), table_cell_style),
                Paragraph(f"{int(r['conf'])}%", table_cell_style),
                Paragraph(f"{r['price']:.2f}", table_cell_style),
                Paragraph(f"{r['tp']:.2f}", table_cell_style),
                Paragraph(f"{r['sl']:.2f}", table_cell_style),
                Paragraph(f"{r['p_up']:.1f}%/{r['p_down']:.1f}%",
                          table_cell_style),
            ]
            data.append(row)

        table = Table(data, colWidths=[50, 100, 40, 40, 60, 60, 60, 80])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 24))

        # 5) Now append a “Multi‐Coin Summary” section header
        elements.append(Paragraph("Multi‐Coin Summary", summary_heading_style))
        elements.append(Spacer(1, 6))

        # 6) For each coin, append its summary text (already generated in run_multi)
        for coin_summary in summaries:
            # We assume coin_summary contains something like “**BTC**\n\n### Summary (…)…”
            # Break on blank lines to get each paragraph
            for paragraph_text in coin_summary.split("\n\n"):
                elements.append(Paragraph(paragraph_text, summary_body_style))
            elements.append(Spacer(1, 12))

        # 7) Build the final PDF
        doc.build(elements)
        log.info(f"Multi-coin PDF report generated: {output_file}")
        return output_file

    except Exception as e:
        log.error(f"Failed to generate multi-coin PDF report: {e}")
        print(f"⚠️ Failed to generate multi-coin PDF report: {str(e)}")
        return None
