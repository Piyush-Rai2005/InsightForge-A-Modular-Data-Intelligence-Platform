import os
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

from .base_agent import BaseAgent

NAVY = colors.HexColor("#071c3d")
LIGHT_GREY = colors.HexColor("#666666")


class ReportAgent(BaseAgent):
    """Builds a premium InsightSphere PDF report"""

    def __init__(self):
        super().__init__("ReportAgent")

    # -------------------- HEADER --------------------
    def draw_header(self, canvas, doc):
        canvas.saveState()

        # Full-width blue bar
        canvas.setFillColor(NAVY)
        canvas.rect(
            0,
            A4[1] - 80,
            A4[0],
            80,
            fill=1,
            stroke=0,
        )

        # White title text
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawCentredString(
            A4[0] / 2,
            A4[1] - 50,
            "InsightSphere — Data Diagnostics Report",
        )

        canvas.restoreState()

    # -------------------- FOOTER (LAST PAGE ONLY) --------------------
    def footer_canvas(self, canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 9)
        canvas.setFillColor(LIGHT_GREY)
        canvas.drawCentredString(
            A4[0] / 2, 18, "Designed & Automated by Kavya Singh"
        )
        canvas.restoreState()

    # -------------------- MAIN --------------------
    def run(self, context):
        os.makedirs("outputs", exist_ok=True)
        pdf_path = "outputs/InsightSphere_Report.pdf"

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=90,   # space for header
            bottomMargin=50,
        )

        # -------------------- Styles --------------------
        styles = {
            "h2": ParagraphStyle(
                name="Heading2",
                fontName="Helvetica-Bold",
                fontSize=15,
                textColor=NAVY,
                spaceAfter=8,
            ),
            "h3": ParagraphStyle(
                name="Heading2",
                fontName="Helvetica-Bold",
                fontSize=12,
                textColor=NAVY,
                spaceAfter=8,
            ),
            "text": ParagraphStyle(
                name="BodyText",
                fontName="Helvetica",
                fontSize=11,
                leading=14,
                spaceAfter=10,
            ),
            "italic": ParagraphStyle(
                name="Italic",
                fontName="Helvetica-Oblique",
                fontSize=10,
                leading=13,
                spaceAfter=12,
            ),
            "bullet": ParagraphStyle(
                name="Bullet",
                fontName="Helvetica",
                fontSize=11,
                leftIndent=18,
                bulletIndent=6,
                leading=14,
                spaceAfter=6,
            ),
        }

        # -------------------- Context --------------------
        df = context.get("raw_data")
        exec_summary = context.get("exec_summary", "")
        recommendations = context.get("recommendations_text", "")

        scores = context.get("model_scores") or {}
        best_name = context.get("best_model_name", "N/A")
        best_acc = context.get("best_model_accuracy", 0.0)

        story = []

        # -------------------- Executive Summary --------------------
        story.append(Paragraph("Executive Summary", styles["h2"]))
        story.append(Paragraph(exec_summary.replace("\n\n", "<br/>"), styles["text"]))
        story.append(Spacer(1, 16))

        # -------------------- Dataset Overview --------------------
        if df is not None:
            r, c = df.shape
            story.append(Paragraph("Dataset Overview\n", styles["h2"]))
            story.append(
                Paragraph(
                    f"The dataset contains <b>{r}</b> rows and <b>{c}</b> columns.",
                    styles["text"],
                )
            )

            # Describe table
            desc = df.describe().transpose().iloc[:6]
            desc_data = [["Feature"] + list(desc.columns)]
            for idx, row in desc.iterrows():
                desc_data.append([idx] + [f"{v:.2f}" for v in row.values])

            desc_tbl = Table(desc_data, hAlign="LEFT")
            desc_tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(desc_tbl)
            story.append(Spacer(1, 12))

            # Missing values
            missing = df.isna().sum()
            if missing.sum() > 0:
                miss_data = [["Column", "Missing Count"]]
                for col, val in missing[missing > 0].items():
                    miss_data.append([col, int(val)])

                miss_tbl = Table(miss_data, hAlign="LEFT")
                miss_tbl.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                story.append(Paragraph("Missing Values Summary\n", styles["text"]))
                story.append(miss_tbl)
                story.append(Spacer(1, 16))

        # -------------------- Model Comparison --------------------
        if scores:
            story.append(Paragraph("Model Comparison", styles["h2"]))

            table_data = [["Model", "Accuracy"]]
            for name, acc in scores.items():
                table_data.append([name, f"{acc:.2f}"])

            tbl = Table(table_data, hAlign="LEFT")
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ]
                )
            )
            story.append(tbl)
            story.append(Spacer(1, 10))

            bar_path = context.get("model_bar")
            if bar_path and os.path.exists(bar_path):
                story.append(Image(bar_path, width=380, height=500))
                story.append(
                    Paragraph(
                        f"The comparison shows <b>{best_name}</b> achieved the highest performance with an accuracy of {best_acc:.2f}.",
                        styles["italic"],
                    )
                )

        # -------------------- Visual Insights --------------------
        story.append(PageBreak())
        story.append(Paragraph("Visual Insights\n", styles["h2"]))

        visuals = [
            ("Correlation Heatmap", context.get("corr_plot"), context.get("corr_insight")),
            ("Target Distribution", context.get("target_plot"), context.get("target_insight")),
            ("Confusion Matrix", context.get("conf_matrix"), context.get("cm_insight")),
            ("ROC Curve", context.get("roc_curve"), context.get("roc_insight")),
        ]

        for title, img, explanation in visuals:
            if img and os.path.exists(img):
                story.append(Paragraph(title, styles["h3"]))
                story.append(Image(img, width=380, height=220))
                if explanation:
                    story.append(Paragraph(explanation, styles["italic"]))
                story.append(Spacer(1, 12))

        # -------------------- Business Recommendations --------------------
        story.append(PageBreak())
        story.append(Paragraph("Business Recommendations\n", styles["h2"]))

        if recommendations:
            for line in recommendations.split("\n"):
                if line.strip():
                    story.append(Paragraph(f"➤ {line.strip()}", styles["bullet"]))

        # -------------------- Build --------------------
        doc.build(
            story,
            onFirstPage=self.draw_header,
            onLaterPages=self.footer_canvas,
        )

        context["report_path"] = pdf_path
        self.log(f"Report generated at {pdf_path}")
        return context