"""PDF report generation using ReportLab with table wrapping and unicode support."""

import os
import json
from datetime import datetime, timezone


def generate_pdf_report(analysis_id, contract_name, timestamp, findings, policies, reports_folder, warnings=None):
    """Generate a PDF report for the analysis."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib import colors
    
    font_registered = False
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        font_paths = [
            'C:/Windows/Fonts/arial.ttf',
            'C:/Windows/Fonts/calibri.ttf',
            'C:/Windows/Fonts/segoeui.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont('UniFont', fp))
                font_registered = True
                break
    except Exception:
        font_registered = False
    
    base_font = 'UniFont' if font_registered else 'Helvetica'
    
    pdf_path = os.path.join(reports_folder, f'clauselens-{analysis_id}.pdf')
    
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm,
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontName=base_font,
        fontSize=18,
        spaceAfter=8,
        textColor=HexColor('#1e293b'),
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=base_font,
        fontSize=13,
        spaceAfter=6,
        spaceBefore=14,
        textColor=HexColor('#0f172a'),
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontName=base_font,
        fontSize=10,
        spaceAfter=4,
        spaceBefore=6,
        textColor=HexColor('#1e3a8a'),
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName=base_font,
        fontSize=8.5,
        spaceAfter=3,
        alignment=TA_JUSTIFY,
    )
    
    quote_style = ParagraphStyle(
        'CustomQuote',
        parent=styles['Normal'],
        fontName=base_font,
        fontSize=8,
        spaceAfter=4,
        leftIndent=10,
        rightIndent=10,
        textColor=HexColor('#334155'),
        backColor=HexColor('#f1f5f9'),
        borderPadding=4,
    )
    
    small_style = ParagraphStyle(
        'Small',
        parent=styles['Normal'],
        fontName=base_font,
        fontSize=7.5,
        spaceAfter=2,
        textColor=HexColor('#64748b'),
    )
    
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontName=base_font,
        fontSize=7,
        spaceAfter=4,
        textColor=HexColor('#94a3b8'),
        alignment=TA_CENTER,
    )
    
    elements = []
    
    # Title
    elements.append(Paragraph('ClauseLens Trust — Contract Risk Review', title_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=HexColor('#2563eb')))
    elements.append(Spacer(1, 6))
    
    # Meta info
    gen_time = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f'<b>Contract:</b> {_escape(contract_name)} | <b>Analysis ID:</b> {analysis_id} | <b>Generated:</b> {gen_time}', small_style))
    elements.append(Spacer(1, 10))
    
    # Summary Table
    total = len(findings)
    conflicts = sum(1 for f in findings if _get(f, 'result_type') == 'conflict')
    matches = sum(1 for f in findings if _get(f, 'result_type') == 'match')
    uncertain = sum(1 for f in findings if _get(f, 'result_type') == 'uncertain')
    not_found = sum(1 for f in findings if _get(f, 'result_type') == 'not_found')
    high = sum(1 for f in findings if _get(f, 'severity') == 'high')
    medium = sum(1 for f in findings if _get(f, 'severity') == 'medium')
    low = sum(1 for f in findings if _get(f, 'severity') == 'low')
    
    elements.append(Paragraph('Executive Summary', heading_style))
    summary_data = [
        ['Total Findings', str(total), 'High Severity', str(high)],
        ['Policy Conflicts', str(conflicts), 'Medium Severity', str(medium)],
        ['Policy Matches', str(matches), 'Low Severity', str(low)],
        ['Uncertain / Ambiguous', str(uncertain), 'Terms Not Found', str(not_found)],
    ]
    summary_table = Table(summary_data, colWidths=[120, 60, 120, 60])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), base_font),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 0), (0, -1), HexColor('#f8fafc')),
        ('BACKGROUND', (2, 0), (2, -1), HexColor('#f8fafc')),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 10))
    
    # Policies applied
    elements.append(Paragraph('Policies Applied', heading_style))
    for p in policies:
        config_dict = p.get('config', {})
        config_desc = ', '.join(f'{k}: {v}' for k, v in config_dict.items())
        elements.append(Paragraph(f'• <b>{_escape(p.get("name", p.get("category", "Policy")))}</b>: {_escape(config_desc)}', body_style))
    elements.append(Spacer(1, 10))

    # OCR / Image quality notices if any
    if warnings:
        elements.append(Paragraph('Document Quality &amp; OCR Notices', heading_style))
        for w in warnings:
            elements.append(Paragraph(f'• <font color="#d97706">▲</font> {_escape(w)}', small_style))
        elements.append(Spacer(1, 10))
    
    # Detailed Findings
    elements.append(Paragraph('Detailed Findings', heading_style))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#94a3b8')))
    
    priority = {'conflict': 0, 'uncertain': 1, 'not_found': 2, 'match': 3}
    sorted_findings = sorted(findings, key=lambda f: priority.get(_get(f, 'result_type'), 4))
    
    for i, f in enumerate(sorted_findings):
        severity = (_get(f, 'severity') or 'N/A').upper()
        result_type = _get(f, 'result_type', '').replace('_', ' ').title()
        risk_id = _get(f, 'risk_id', f'RISK-{i+1:03d}')
        cat = _get(f, 'category', '').title()
        
        color_hex = '#ef4444' if severity == 'HIGH' else ('#f59e0b' if severity == 'MEDIUM' else '#10b981')
        
        severity_clean = _escape(severity)
        result_type_clean = _escape(result_type)
        cat_clean = _escape(cat)
        risk_id_clean = _escape(risk_id)
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f'<font color="{color_hex}">■</font> <b>{risk_id_clean} — {cat_clean}</b> [{severity_clean} / {result_type_clean}]', subheading_style))
        
        if _get(f, 'clause_title'):
            elements.append(Paragraph(f'<b>Clause Reference:</b> {_escape(_get(f, "clause_title"))}', body_style))
            
        elements.append(Paragraph(f'<b>Policy Expected:</b> {_escape(_get(f, "policy_expected"))}', body_style))
        elements.append(Paragraph(f'<b>Condition Detected:</b> {_escape(_get(f, "condition_detected"))}', body_style))
        
        quote = _get(f, 'evidence_quote')
        if quote:
            elements.append(Paragraph(f'<b>Exact Evidence Quote:</b>', body_style))
            elements.append(Paragraph(f'"{_escape(quote)}"', quote_style))
            
        locs = []
        para_ref = str(_get(f, 'paragraph_reference', '') or '').strip()
        page_val = _get(f, 'page_number')
        line_val = str(_get(f, 'line_reference', '') or '').strip()

        if page_val:
            locs.append(f"Page {page_val}")
        if para_ref and para_ref != 'None':
            locs.append(_escape(para_ref))
        if line_val and line_val != 'None':
            locs.append(_escape(line_val))
        if not locs:
            locs.append("Location: not available")
            
        elements.append(Paragraph(f'<b>Location:</b> {", ".join(locs)} | <b>Verification:</b> {_escape((_get(f, "verification_status") or "N/A").replace("_", " ").title())}', small_style))
        elements.append(Paragraph(f'<b>Explanation:</b> {_escape(_get(f, "explanation"))}', body_style))
        
        if _get(f, 'potential_impact'):
            elements.append(Paragraph(f'<b>Potential Impact:</b> {_escape(_get(f, "potential_impact"))}', body_style))
        if _get(f, 'suggested_action'):
            elements.append(Paragraph(f'<b>Suggested Next Action:</b> {_escape(_get(f, "suggested_action"))}', body_style))
            
        review_stat = _get(f, 'review_status', 'not_reviewed')
        if review_stat != 'not_reviewed':
            note = _get(f, 'review_note')
            note_str = f" — Note: {_escape(note)}" if note else ""
            elements.append(Paragraph(f'<b>Review Status:</b> {_escape(review_stat.replace("_", " ").title())}{note_str}', small_style))
            
        elements.append(HRFlowable(width="100%", thickness=0.25, color=HexColor('#e2e8f0')))
    
    # Disclaimer
    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#94a3b8')))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        'DISCLAIMER: This report is generated by ClauseLens Trust for informational purposes only and does not constitute legal advice. '
        'Severity scores indicate review priority, not legal culpability. Consult a licensed legal practitioner for formal guidance.',
        disclaimer_style
    ))
    
    doc.build(elements)
    return pdf_path


def _escape(text):
    if not text:
        return ''
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def _get(d, key, default=''):
    try:
        val = d[key]
        return val if val is not None else default
    except (KeyError, IndexError, TypeError):
        return default
