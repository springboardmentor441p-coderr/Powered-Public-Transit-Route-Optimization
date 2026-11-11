"""Render the public technical report and prepare presentation input from real results."""
import html
import json
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'handoff/final'


def render_report():
    OUT.mkdir(parents=True,exist_ok=True)
    text=(ROOT/'documentation/TECHNICAL_REPORT.md').read_text(encoding='utf-8')
    text=text.replace('–','-').replace('—','-').replace('’',"'")
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReportBody',fontName='Helvetica',fontSize=10.2,leading=15,spaceAfter=9))
    styles['Title'].fontName='Helvetica-Bold';styles['Title'].fontSize=25;styles['Title'].leading=30
    styles['Title'].textColor=colors.HexColor('#183b56');styles['Title'].alignment=TA_LEFT
    styles['Heading1'].fontName='Helvetica-Bold';styles['Heading1'].fontSize=16;styles['Heading1'].leading=21
    styles['Heading1'].textColor=colors.HexColor('#087f8c');styles['Heading1'].spaceBefore=17
    story=[]
    for paragraph in re.split(r'\n\s*\n',text):
        if paragraph.startswith('# '):
            story.extend([Paragraph(html.escape(paragraph[2:].strip()),styles['Title']),Spacer(1,15)])
        elif paragraph.startswith('## '):
            story.append(Paragraph(html.escape(paragraph[3:].strip()),styles['Heading1']))
        else:
            story.append(Paragraph(html.escape(' '.join(paragraph.splitlines())),styles['ReportBody']))
    def footer(canvas, doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#52697d'))
        canvas.drawString(42,25,'RouteRanker | Technical report | 8 November 2026')
        canvas.drawRightString(A4[0]-42,25,f'{doc.page}')
    SimpleDocTemplate(str(OUT/'RouteRanker_Technical_Report.pdf'),pagesize=A4,
                      leftMargin=45,rightMargin=45,topMargin=42,bottomMargin=45,
                      title='RouteRanker technical report',author='RouteRanker').build(story,onFirstPage=footer,onLaterPages=footer)
    payload={'allocation':json.loads((ROOT/'reports/completion/allocation_summary.json').read_text()),
             'import':json.loads((ROOT/'reports/completion/real_gtfs_import_audit.json').read_text()),
             'profile':json.loads((ROOT/'data/processed/new_york/october_validation/experimental_profile.json').read_text())}
    (OUT/'presentation_inputs.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')
    print(OUT/'RouteRanker_Technical_Report.pdf')


if __name__=='__main__':render_report()
