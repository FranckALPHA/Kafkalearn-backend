from typing import List, Dict
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.pagesizes import A4
import io
import logging

logger = logging.getLogger(__name__)

class PDFGenerator:
    """
    Générateur PDF avec charte graphique éducative camerounaise.
    """
    
    # Charte graphique
    PRIMARY_COLOR = colors.HexColor('#1e3a5f')  # Bleu officiel
    SECONDARY_COLOR = colors.HexColor('#3ddc84')  # Vert accent
    TEXT_COLOR = colors.HexColor('#1a1a1a')
    
    def __init__(self, font_path: str = None):
        self.font_name = "Helvetica"  # Utiliser Helvetica par défaut
    
    def generate_fiche_pdf(self, titre: str, metadata: dict, contenu_markdown: str) -> bytes:
        """
        Génère une fiche de révision PDF structurée.
        
        Args:
            titre: Titre principal de la fiche
            metadata: {matiere, niveau, serie, date_generation, notions_couvertes}
            contenu_markdown: Contenu formaté en Markdown simple
            
        Returns:
            Bytes du fichier PDF
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=50, leftMargin=50,
            topMargin=80, bottomMargin=50
        )
        
        story = []
        
        # ─── Header officiel ─────────────────────────────────────
        story.extend(self._build_header(titre, metadata))
        story.append(Spacer(1, 20))
        
        # ─── Table des matières si long ──────────────────────────
        sections = self._parse_markdown_sections(contenu_markdown)
        if len(sections) >= 3:
            story.extend(self._build_toc(sections))
            story.append(PageBreak())
        
        # ─── Contenu principal ───────────────────────────────────
        story.extend(self._build_content(sections))
        
        # ─── Footer avec métadonnées ─────────────────────────────
        story.append(Spacer(1, 30))
        story.extend(self._build_footer(metadata))
        
        # Génération
        doc.build(story)
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def _build_header(self, titre: str, metadata: dict) -> list:
        """Construit l'en-tête officiel avec logo et métadonnées."""
        elements = []
        
        # Logo + titre République (simulé)
        header_table = Table([
            [f"RÉPUBLIQUE DU CAMEROUN\nPaix - Travail - Patrie"],
            [f"************\n{metadata.get('matiere', '').upper()} - {metadata.get('niveau', '')}"],
            [f"📚 {titre}"]
        ], colWidths=[400])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,-1), self.font_name),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('FONTSIZE', (0,2), (-1,2), 14),
            ('TEXTCOLOR', (0,2), (-1,2), self.PRIMARY_COLOR),
            ('BOTTOMPADDING', (0,2), (-1,2), 15),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 10))
        
        # Barre décorative
        elements.append(Table([['']], colWidths=[400], rowHeights=[3]).setStyle(
            TableStyle([('BACKGROUND', (0,0), (-1,-1), self.PRIMARY_COLOR)])
        ))
        
        return elements
    
    def _parse_markdown_sections(self, markdown: str) -> List[Dict]:
        """Parse Markdown simple en sections structurées."""
        # Implémentation basique : split par ##, ###, etc.
        # Pour une vraie implémentation : utiliser mistune ou markdown2
        sections = []
        current_section = {"title": "Introduction", "content": [], "level": 1}
        
        for line in markdown.split('\n'):
            if line.startswith('## '):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"title": line[3:], "content": [], "level": 2}
            elif line.startswith('### '):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"title": line[4:], "content": [], "level": 3}
            elif line.strip():
                current_section["content"].append(line)
        
        if current_section["content"]:
            sections.append(current_section)
        
        return sections

    def _build_toc(self, sections: List[Dict]) -> list:
        """Construit la table des matières."""
        elements = []
        elements.append(Paragraph("Table des matières", style=self._get_heading_style()))
        elements.append(Spacer(1, 10))

        toc_data = [[s["title"], ""] for s in sections]
        toc_table = Table(toc_data, colWidths=[350, 50])
        toc_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), self.font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(toc_table)
        return elements

    def _build_content(self, sections: List[Dict]) -> list:
        """Construit le contenu principal."""
        elements = []
        for section in sections:
            elements.append(Paragraph(section["title"], style=self._get_heading_style()))
            elements.append(Spacer(1, 8))
            for line in section["content"]:
                elements.append(Paragraph(line, style=self._get_body_style()))
                elements.append(Spacer(1, 4))
            elements.append(Spacer(1, 12))
        return elements

    def _build_footer(self, metadata: dict) -> list:
        """Construit le footer avec métadonnées."""
        elements = []
        elements.append(Table([['']], colWidths=[400], rowHeights=[2]).setStyle(
            TableStyle([("BACKGROUND", (0, 0), (-1, -1), self.PRIMARY_COLOR)])
        ))
        elements.append(Spacer(1, 10))
        elements.append(
            Paragraph(
                f"Fiche générée le {metadata.get('date_generation', '')} — {metadata.get('matiere', '')} {metadata.get('niveau', '')}",
                style=self._get_footer_style(),
            )
        )
        return elements

    def _get_heading_style(self):
        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        style = styles["Heading2"]
        style.textColor = self.PRIMARY_COLOR
        style.fontName = self.font_name
        return style

    def _get_body_style(self):
        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        style = styles["Normal"]
        style.fontName = self.font_name
        style.fontSize = 10
        style.leading = 14
        return style

    def _get_footer_style(self):
        from reportlab.lib.styles import getSampleStyleSheet
        styles = getSampleStyleSheet()
        style = styles["Normal"]
        style.fontName = self.font_name
        style.fontSize = 8
        style.textColor = colors.grey
        return style