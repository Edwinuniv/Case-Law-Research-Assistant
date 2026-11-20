"""An answer as a PDF research note (Edwin, SPEC 11, 2026-11-20, from CedarPay's printable receipts).
Made from the answer exactly as it was shown (query_log.details.shown): no model call, no new search, nothing kept.
The question, the status, each verified sentence with its citation, then the sources: for each citation the case,
the opinion it comes from and the exact words quoted. Built with ReportLab, like app/exports.py."""
import io
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app import config

LOGO = Path(__file__).parent / "assets" / "logo.png"
INK, GOLD, DIM, SOFT = (colors.HexColor(c) for c in ("#1c1917", "#b45309", "#57534e", "#f7f5f0"))
TITLE = ParagraphStyle("t", fontName="Times-Bold", fontSize=19, leading=23, textColor=INK)
QUESTION = ParagraphStyle("q", fontName="Times-Italic", fontSize=13, leading=17, textColor=INK, spaceAfter=4)
H2 = ParagraphStyle("h", fontName="Times-Bold", fontSize=13, leading=16, textColor=GOLD, spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle("b", fontName="Helvetica", fontSize=10.5, leading=15, textColor=INK, spaceAfter=3)
CITE = ParagraphStyle("c", fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=GOLD, spaceAfter=9)
QUOTE = ParagraphStyle("qu", fontName="Times-Roman", fontSize=10.5, leading=14.5, textColor=INK, leftIndent=10)
SMALL = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=DIM)

STATUS = {"ANSWERED": ("Verified answer", "Every sentence below was checked against the passage it cites."),
          "LOW_CONFIDENCE": ("Low confidence", "The support for this answer is partial: check the sources before relying on it."),
          "NOT_SUPPORTED": ("Not supported by the retrieved opinions",
                            "The opinions searched do not answer this question, so Verdicta did not guess.")}


def para(text, style):
    return Paragraph(escape(str(text)), style)


def build(row):
    """The PDF (bytes) of one saved answer: row has id, question, status, created_at, shown."""
    shown = row["shown"] or {}
    width = A4[0] - 3.4 * cm
    title, meaning = STATUS.get(row["status"], (row["status"], ""))
    head = Table([[Image(str(LOGO), width=1.5 * cm, height=1.3 * cm),
                   [para("Research note", TITLE),
                    para(f"Verdicta · asked {row['created_at']:%Y-%m-%d %H:%M} UTC · answer {row['id']}", SMALL)]]],
                 colWidths=[1.9 * cm, width - 1.9 * cm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, GOLD),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story = [head, Spacer(1, 12), para("Question", H2), para(row["question"], QUESTION),
             para("Answer", H2), para(f"{title}. {meaning}", SMALL), Spacer(1, 6)]
    sources = []                                         # each citation once, in the order of the answer
    for s in shown.get("sentences", []):
        story.append(para(s["text"], BODY))
        labels = []
        for c in s["citations"]:
            if c["pid"] not in [x["pid"] for x in sources]:
                sources.append(c)
            labels.append(f"{c['label']} [{c['pid']}]")
        story.append(para(" · ".join(labels), CITE))
    if sources:
        passages = {p["pid"]: p for p in shown.get("passages", [])}
        story.append(para("Sources: the exact words each sentence relies on", H2))
        for c in sources:
            p = passages.get(c["pid"], {})
            where = " · ".join(x for x in (p.get("opinion_label"), p.get("section")) if x)
            box = Table([[[para(f"[{c['pid']}] {c['label']}", CITE), para(f"“{c['quote']}”", QUOTE),
                           para(where, SMALL)]]], colWidths=[width])
            box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT), ("LINEBEFORE", (0, 0), (0, -1), 2.5, GOLD),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
            story += [box, Spacer(1, 6)]
    story += [Spacer(1, 14), para(f"Coverage: {config.COVERAGE}.", SMALL),
              para("Verdicta is a research aid, not legal advice. Every citation and quote above was checked against "
                   "the opinion itself before it was shown; read the full opinion before relying on it.", SMALL)]
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, title=f"Verdicta research note {row['id']}", author="Verdicta")

    def footer(canvas, d):
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#78716c"))
        canvas.drawString(1.7 * cm, 0.8 * cm, "Verdicta · a research aid, not legal advice")
        canvas.drawRightString(A4[0] - 1.7 * cm, 0.8 * cm, f"Page {d.page}")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
