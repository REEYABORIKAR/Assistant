import io
import pypdf
import docx
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and render 'Page X of Y' footers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header line & text on page 2+
        if self._pageNumber > 1:
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(36, 756, 576, 756)
            self.drawString(36, 762, "REFYNE AI Enterprise Requirement Suite — Official Specification")
            
        # Footer line & text on all pages
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 45, 576, 45)
        
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 32, page_text)
        self.drawString(36, 32, "CONFIDENTIAL & PROPRIETARY — REFYNE WORKSPACE GOVERNANCE")
        self.restoreState()

def extract_text_from_file(content_bytes: bytes, filename: str, mime_type: str) -> str:
    """Extract plain text from PDF, DOCX, or text files."""
    fname_lower = filename.lower()
    
    # 1. Handle PDF files using PyPDF
    if fname_lower.endswith(".pdf") or "pdf" in mime_type.lower():
        try:
            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            text_pages = []
            for idx, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_pages.append(f"--- Page {idx + 1} ---\n{page_text.strip()}")
            if text_pages:
                return "\n\n".join(text_pages)
        except Exception as exc:
            print(f"Error parsing PDF with pypdf: {exc}")
            
    # 2. Handle DOCX files using python-docx
    if fname_lower.endswith(".docx") or "word" in mime_type.lower():
        try:
            doc = docx.Document(io.BytesIO(content_bytes))
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            if paragraphs:
                return "\n".join(paragraphs)
        except Exception as exc:
            print(f"Error parsing DOCX: {exc}")
            
    # 3. Fallback for TXT, JSON, MD, CSV or raw text
    try:
        decoded = content_bytes.decode("utf-8", errors="ignore").strip()
        if decoded.startswith("%PDF") and "--- Page" not in decoded:
            return "Unable to extract plain text from PDF."
        return decoded
    except Exception:
        return f"Binary file attachment: {filename}"


async def generate_document_content(
    doc_type: str,
    title: str,
    doc_context: str | None = None,
    audit_json: dict | None = None,
    domain_profile: dict | None = None,
    revision_feedback: str | None = None,
    previous_sections: str | None = None,
    previous_doc: dict | None = None,
    api_key: str | None = None,
    tenant_id: str | None = None,
) -> dict:
    """Generate structured section & table content tailored specifically to BRD, SRS, RTM, USER_STORIES, or ACCEPTANCE_CRITERIA using LLM and verified audit ground truth."""
    from refyne.llm_service import generate_document_ai, detect_domain
    
    if not domain_profile:
        domain_profile = detect_domain(doc_context or title)

    return await generate_document_ai(
        doc_type=doc_type,
        title=title,
        audit_json=audit_json or {},
        domain_profile=domain_profile,
        doc_excerpt=doc_context or "",
        revision_feedback=revision_feedback,
        previous_sections=previous_sections,
        previous_doc=previous_doc,
        api_key=api_key,
        tenant_id=tenant_id
    )


def generate_document_content_sync(
    doc_type: str,
    title: str,
    doc_context: str | None = None,
    audit_json: dict | None = None,
    domain_profile: dict | None = None,
    revision_feedback: str | None = None
) -> dict:
    """Synchronous fallback generator grounded in audit findings and domain profile."""
    from refyne.llm_service import _build_grounded_fallback_document, detect_domain
    
    if not domain_profile:
        domain_profile = detect_domain(doc_context or title)
        
    doc = _build_grounded_fallback_document(
        doc_type=doc_type,
        title=title,
        audit_json=audit_json or {},
        domain_profile=domain_profile,
        doc_excerpt=doc_context or "",
        revision_feedback=revision_feedback
    )
    doc["_source_audit"] = audit_json or {}
    doc["_domain_profile"] = domain_profile
    doc["_doc_excerpt"] = (doc_context or "")[:4000]
    return doc


def build_pdf_document(
    title: str,
    doc_type: str,
    sections: list[dict],
    tenant_name: str = "REFYNE Enterprise Workspace",
    version: str = "v1.0"
) -> bytes:
    """Compile structured document JSON into a high-quality, multi-page vector PDF document using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    
    # Custom REFYNE Enterprise Styling
    doc_badge_style = ParagraphStyle(
        'DocBadge',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0284c7'),
        spaceAfter=4,
    )
    
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=6,
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#475569'),
        spaceAfter=10,
    )
    
    h2_style = ParagraphStyle(
        'SectionHeader',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=14,
        spaceAfter=6,
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=6,
    )
    
    table_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )
    
    table_body_style = ParagraphStyle(
        'TableBody',
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0f172a'),
    )

    elements = []

    # Document Header Banner
    elements.append(Paragraph(f"REFYNE AI REQUIREMENT SUITE — {doc_type.upper()}", doc_badge_style))
    elements.append(Paragraph(f"{title}", title_style))
    elements.append(Paragraph(f"<b>Workspace:</b> {tenant_name} &nbsp;|&nbsp; <b>Version:</b> {version} &nbsp;|&nbsp; <b>Status:</b> APPROVED", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284c7'), spaceAfter=10))

    # Add Sections
    for sec in sections:
        sec_title = sec.get("title", "Section")
        sec_body = sec.get("body", "")
        sec_table = sec.get("table", None)
        
        elements.append(Paragraph(sec_title, h2_style))
        
        if sec_body:
            for p_text in sec_body.split("\n\n"):
                if p_text.strip():
                    formatted_p = p_text.replace("\n", "<br/>").replace("• ", "&bull; ")
                    elements.append(Paragraph(formatted_p, body_style))
                    
        if sec_table and isinstance(sec_table, list) and len(sec_table) > 0:
            table_data = []
            
            # Header Row
            headers = [Paragraph(f"<b>{str(h)}</b>", table_header_style) for h in sec_table[0]]
            table_data.append(headers)
            
            # Data Rows
            for row in sec_table[1:]:
                row_cells = []
                for cell in row:
                    cell_text = str(cell).replace("\n", "<br/>")
                    if cell_text in ("APPROVED", "VERIFIED", "VALIDATED", "COMPLIANT", "SYNCHRONIZED", "PASSED", "MITIGATED", "ACTIVE"):
                        cell_text = f"<font color='#0284c7'><b>{cell_text}</b></font>"
                    row_cells.append(Paragraph(cell_text, table_body_style))
                table_data.append(row_cells)
                
            num_cols = len(sec_table[0])
            if num_cols == 6:  # User Stories Matrix: Story ID, Epic, Persona, Statement, Business Value, Priority
                col_widths = [0.7*inch, 1.2*inch, 1.0*inch, 2.5*inch, 1.3*inch, 0.7*inch]
            elif num_cols == 5:  # BRD Matrix / RTM: 5 columns
                col_widths = [0.8*inch, 1.4*inch, 2.5*inch, 0.9*inch, 1.8*inch]
            elif num_cols == 7:  # RTM or Threat Matrix: 7 columns
                col_widths = [0.7*inch, 1.2*inch, 0.7*inch, 1.8*inch, 0.8*inch, 0.8*inch, 1.4*inch]
            else:
                col_widths = [1.0*inch, 1.5*inch, 3.5*inch, 1.4*inch]
                
            t = Table(table_data, colWidths=col_widths)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 8))
            
        elements.append(Spacer(1, 4))

    doc.build(elements, canvasmaker=NumberedCanvas)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
