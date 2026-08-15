import io
import logging
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

logger = logging.getLogger(__name__)

class PDFService:

    def generate_person_profile_pdf(self, data: dict) -> bytes:
        """Generate a beautiful PDF for a person profile with structured sections."""
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, 
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=72)
        
        # External image fetching is enabled by default in ReportLab
        # To use external images, use: Image(url, width=X, height=Y)
        # Example: story.append(Image('https://example.com/image.jpg', width=2*inch, height=2*inch))
        
        story = []
        
        styles = getSampleStyleSheet()
        
        title_font = 'Helvetica-Bold'
        
        # Colorful color scheme
        primary_color = colors.HexColor("#2563eb")  # Blue
        primary_color_hex = "#2563eb"
        secondary_color = colors.HexColor("#1e40af")  # Darker blue
        secondary_color_hex = "#1e40af"
        accent_color = colors.HexColor("#3b82f6")  # Light blue
        purple_color = colors.HexColor("#9333ea")  # Purple
        purple_color_hex = "#9333ea"
        green_color = colors.HexColor("#10b981")  # Green
        green_color_hex = "#10b981"
        orange_color = colors.HexColor("#f59e0b")  # Orange
        orange_color_hex = "#f59e0b"
        pink_color = colors.HexColor("#ec4899")  # Pink
        pink_color_hex = "#ec4899"
        red_color = colors.HexColor("#ef4444")  # Red
        red_color_hex = "#ef4444"
        text_dark = colors.HexColor("#1f2937")  # Dark gray
        text_light = colors.HexColor("#6b7280")  # Light gray
        bg_light = colors.HexColor("#f3f4f6")  # Light gray background
        bg_purple = colors.HexColor("#faf5ff")  # Light purple background
        bg_green = colors.HexColor("#f0fdf4")  # Light green background
        bg_orange = colors.HexColor("#fffbeb")  # Light orange background
        
        # Define styles with Cinzel font for titles - Professional and elegant
        title_page_style = ParagraphStyle(
            'TitlePageStyle',
            parent=styles['Title'],
            alignment=TA_CENTER,
            fontSize=36,
            spaceAfter=12,
            textColor=secondary_color,  # Darker blue for more professional look
            fontName=title_font,
            leading=42
        )
        
        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            fontSize=13,
            spaceAfter=24,
            textColor=text_light,
            fontName='Helvetica'
        )
        
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=24,
            spaceAfter=15,
            spaceBefore=20,
            textColor=primary_color,
            fontName=title_font,
        )
        
        subsection_style = ParagraphStyle(
            'SubsectionStyle',
            parent=styles['Heading3'],
            fontSize=16,
            spaceAfter=10,
            spaceBefore=12,
            textColor=secondary_color,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['BodyText'],
            fontSize=11,
            leading=16,
            spaceAfter=8,
            textColor=text_dark,
            alignment=TA_JUSTIFY,
            fontName='Helvetica'
        )
        
        detail_label_style = ParagraphStyle(
            'DetailLabelStyle',
            parent=normal_style,
            fontSize=11,
            textColor=secondary_color,
            fontName='Helvetica-Bold',
            spaceAfter=4
        )
        
        detail_value_style = ParagraphStyle(
            'DetailValueStyle',
            parent=normal_style,
            fontSize=11,
            textColor=text_dark,
            fontName='Helvetica',
            leftIndent=10
        )
        
        # Function to get colorful shapes for bullet points
        def get_colored_bullet(index: int) -> str:
            """Get colorful bullet shapes that rotate through colors."""
            shapes = ['●', '◆', '▲', '■', '★', '♦', '►', '◉']
            colors_list = [
                primary_color_hex,    # Blue
                purple_color_hex,     # Purple
                green_color_hex,      # Green
                orange_color_hex,      # Orange
                pink_color_hex,        # Pink
                red_color_hex,         # Red
                secondary_color_hex,   # Dark Blue
                "#3b82f6",            # Light Blue
            ]
            shape = shapes[index % len(shapes)]
            color = colors_list[index % len(colors_list)]
            return f'<font color="{color}" size="12">{shape}</font>'
        
        # ============================================================
        # TITLE PAGE
        # ============================================================
        name = data.get('name', 'Unknown Person')
        name_upper = name.upper()  # Convert to uppercase
        
        # Collect sources for citations and references
        sources = data.get('sources', [])
        field_citations = data.get('field_citations', {})  # Map of field names to source URLs
        logger.info(f"📄 PDF Generation: Received {len(sources)} sources for citations")
        logger.info(f"📄 Field citations: {field_citations}")
        
        # Ensure Wikipedia is included if it exists in field_citations
        wikipedia_urls_in_sources = [s for s in sources if s and 'wikipedia.org' in str(s).lower()]
        if not wikipedia_urls_in_sources:
            # Check if Wikipedia should be added based on field_citations
            for field, url in field_citations.items():
                if url and 'wikipedia.org' in str(url).lower():
                    if url not in sources:
                        sources.insert(0, url)  # Add Wikipedia as first source
                        logger.info(f"✅ Added Wikipedia URL to sources: {url}")
                        break
        
        if not sources or len(sources) == 0:
            logger.warning("⚠️  No sources found in data! Citations will not be displayed.")
        else:
            logger.info(f"✅ Sources available: {sources[:3]}...")
            # Log Wikipedia specifically
            wiki_sources = [s for s in sources if s and 'wikipedia.org' in str(s).lower()]
            if wiki_sources:
                logger.info(f"✅ Wikipedia found in sources: {wiki_sources[0]}")
            else:
                logger.warning("⚠️  Wikipedia not found in sources!")
        
        # Map sources to citation numbers (1-indexed)
        source_to_citation = {}
        citation_counter = 1
        for source in sources:
            if source and source not in source_to_citation:
                source_to_citation[source] = citation_counter
                citation_counter += 1
        
        logger.info(f"📄 PDF Generation: Mapped {len(source_to_citation)} sources to citation numbers")
        logger.info(f"📄 Source mapping: {dict(list(source_to_citation.items())[:5])}")
        
        # Helper function to normalize URLs for matching
        def normalize_url(url: str) -> str:
            """Normalize URL for comparison."""
            if not url:
                return ""
            url = str(url).lower().strip()
            # Remove trailing slashes and protocol variations
            url = url.rstrip('/')
            url = url.replace('http://', '').replace('https://', '')
            return url
        
        # Helper function to find citation number for a source URL
        def find_citation_number(source_url: str) -> int:
            """Find citation number for a source URL, return 0 if not found."""
            if not source_url:
                return 0
            # Try exact match first
            if source_url in source_to_citation:
                return source_to_citation[source_url]
            # Try normalized match
            normalized_url = normalize_url(source_url)
            for stored_url, citation_num in source_to_citation.items():
                if normalize_url(stored_url) == normalized_url:
                    return citation_num
            return 0
        
        # Helper function to get source name from URL for APA citation
        def get_source_name_for_apa(url: str) -> str:
            """Extract source name from URL for APA citation."""
            try:
                from urllib.parse import urlparse
                parsed = urlparse(str(url))
                domain = parsed.netloc.replace('www.', '').lower()
                if 'wikipedia.org' in domain:
                    return "Wikipedia"
                elif 'twitter.com' in domain or 'x.com' in domain:
                    return "Twitter"
                elif 'instagram.com' in domain:
                    return "Instagram"
                elif 'linkedin.com' in domain:
                    return "LinkedIn"
                elif 'facebook.com' in domain:
                    return "Facebook"
                elif 'youtube.com' in domain:
                    return "YouTube"
                elif any(news_domain in domain for news_domain in ['bbc.com', 'cnn.com', 'reuters.com', 'nytimes.com', 'theguardian.com', 'forbes.com', 'bloomberg.com']):
                    return domain.split('.')[0].title()
                else:
                    return domain.split('.')[0].title() if '.' in domain else "Web Source"
            except:
                return "Source"
        
        # Helper function to get APA-style citation (Author, Year) format
        def get_apa_citation(source_url: str) -> str:
            """Get APA-style citation: (Source Name, Year)."""
            if not source_url:
                return ""
            source_name = get_source_name_for_apa(source_url)
            current_year = datetime.now().year
            # APA format: (Source Name, Year)
            return f' <font color="{primary_color_hex}" size="10"><i>({source_name}, {current_year})</i></font>'
        
        # Helper function to get citation HTML for a source URL (APA style)
        def get_citation(source_url: str) -> str:
            """Get APA-style citation for a source URL."""
            return get_apa_citation(source_url)
        
        # Helper function to get citation for a specific field (APA style)
        def get_field_citation(field_name: str) -> str:
            """Get APA-style citation for a specific field based on field_citations mapping."""
            if field_name in field_citations:
                source_url = field_citations[field_name]
                return get_apa_citation(source_url)
            return ""
        
        # Helper function to get Wikipedia citation (APA style)
        def get_wikipedia_citation() -> str:
            """Get APA-style citation for Wikipedia if available."""
            # Check field_citations first
            wiki_citation = get_field_citation('education') or get_field_citation('family') or get_field_citation('net_worth') or get_field_citation('personal_info_detail')
            if wiki_citation:
                return wiki_citation
            # Check if any Wikipedia URL exists in sources
            for source in sources:
                if source and 'wikipedia.org' in str(source).lower():
                    return get_apa_citation(source)
            # Try constructing Wikipedia URL and check if it matches any source
            wikipedia_urls = [
                f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
                f"https://en.wikipedia.org/wiki/{name}",
                f"http://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
            ]
            for wiki_url in wikipedia_urls:
                # Check exact match
                if wiki_url in sources:
                    return get_apa_citation(wiki_url)
                # Check normalized match
                normalized_wiki = normalize_url(wiki_url)
                for source in sources:
                    if source and normalize_url(source) == normalized_wiki:
                        return get_apa_citation(source)
            # If no Wikipedia found, return empty (don't fallback to other sources)
            return ""
        
        # Helper function to get first available citation (APA style)
        def get_first_citation() -> str:
            """Get APA-style citation for the first source if sources exist."""
            if sources and len(sources) > 0:
                # Prioritize Wikipedia if available
                for source in sources:
                    if source and 'wikipedia.org' in str(source).lower():
                        return get_apa_citation(source)
                # Otherwise use first source
                return get_apa_citation(sources[0])
            return ""
        
        # Main title - clean and simple (above the line)
        title = Paragraph(f"{name_upper}", title_page_style)
        story.append(title)
        
        # Subtitle
        subtitle = Paragraph("Profile Report", subtitle_style)
        story.append(subtitle)
        story.append(Spacer(1, 0.3 * inch))
        
        # Decorative top border (after title and subtitle)
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#e5e7eb"), spaceAfter=20))

        # ── Person Photo ──────────────────────────────────────────────
        # Fetch photo from Wikipedia API (free, no key needed)
        _photo_tmp_path = None
        try:
            import urllib.request as _urlreq
            import json as _json
            import tempfile, os as _os
            wiki_api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{name.replace(' ', '_')}"
            req = _urlreq.Request(wiki_api, headers={'User-Agent': 'Mozilla/5.0'})
            with _urlreq.urlopen(req, timeout=8) as resp:
                wiki_data = _json.loads(resp.read())
            photo_url = wiki_data.get('thumbnail', {}).get('source', '')
            if photo_url:
                req2 = _urlreq.Request(photo_url, headers={'User-Agent': 'Mozilla/5.0'})
                with _urlreq.urlopen(req2, timeout=8) as resp2:
                    img_data = resp2.read()
                suffix = '.png' if 'png' in photo_url.lower() else '.jpg'
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.write(img_data)
                tmp.close()
                _photo_tmp_path = tmp.name  # deleted after doc.build()
                img = Image(_photo_tmp_path, width=2*inch, height=2*inch)
                img.hAlign = 'CENTER'
                story.append(img)
                story.append(Spacer(1, 0.15 * inch))
                logger.info(f"✅ Person photo added to PDF from Wikipedia")
            else:
                logger.warning(f"⚠️  No photo found on Wikipedia for: {name}")
        except Exception as img_err:
            logger.warning(f"⚠️  Could not embed person photo: {img_err}")
        # ─────────────────────────────────────────────────────────────

        story.append(Spacer(1, 0.3 * inch))
        
        # Get citations for title page fields
        nationality_citation = get_field_citation('nationality') or get_wikipedia_citation() or get_first_citation()
        current_job_citation = get_field_citation('current_job') or get_wikipedia_citation() or get_first_citation()
        city_citation = get_field_citation('city') or get_wikipedia_citation() or get_first_citation()
        dob_citation = get_field_citation('date_of_birth') or get_wikipedia_citation() or get_first_citation()
        
        # Helper function to format value with citation
        def format_with_citation(value: str, citation: str) -> str:
            """Format a value with its citation."""
            if value and value != "N/A":
                return f"{value}{citation}" if citation else value
            return value
        
        # Title page details: name, nationality, current job, city, date of birth
        # Professional design with clean labels
        title_page_details = [
            ['Name', name_upper],
            ['Nationality', format_with_citation(data.get('nationality', 'N/A'), nationality_citation)],
            ['Current Position', format_with_citation(data.get('current_job', 'N/A'), current_job_citation)],
            ['Location', format_with_citation(data.get('city', 'N/A'), city_citation)],
            ['Date of Birth', format_with_citation(data.get('date_of_birth', 'N/A'), dob_citation)],
        ]
        
        # Convert to Paragraphs for better formatting
        table_data = []
        for row in title_page_details:
            label_para = Paragraph(row[0], ParagraphStyle(
                'TitlePageLabel',
                parent=styles['Normal'],
                fontSize=11,
                fontName='Helvetica-Bold',
                textColor=secondary_color,
                leading=14
            ))
            value_text = str(row[1]) if row[1] != 'N/A' else 'N/A'
            value_para = Paragraph(value_text, ParagraphStyle(
                'TitlePageValue',
                parent=styles['Normal'],
                fontSize=11,
                fontName='Helvetica',
                textColor=text_dark,
                leading=14
            ))
            table_data.append([label_para, value_para])
        
        title_page_table = Table(table_data, colWidths=[2.2*inch, 4.3*inch])
        title_page_table.setStyle(TableStyle([
            # Professional subtle background for labels
            ('BACKGROUND', (0, 0), (0, -1), bg_light),  # Light gray background for all labels
            ('BACKGROUND', (1, 0), (1, -1), colors.white),  # White background for values
            # Text colors
            ('TEXTCOLOR', (0, 0), (0, -1), secondary_color),  # Dark blue for labels
            ('TEXTCOLOR', (1, 0), (1, -1), text_dark),  # Dark gray for values
            # Alignment
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Padding for professional spacing
            ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 14),
            ('LEFTPADDING', (0, 0), (0, -1), 16),  # More padding for labels
            ('RIGHTPADDING', (0, 0), (0, -1), 16),
            ('LEFTPADDING', (1, 0), (1, -1), 14),  # Padding for values
            ('RIGHTPADDING', (1, 0), (1, -1), 14),
            # Professional borders
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),  # Subtle gray line below each row
            ('LINEABOVE', (0, 0), (-1, 0), 0.5, colors.HexColor("#e5e7eb")),  # Top border
            # Left border accent for labels
            ('LINEBEFORE', (0, 0), (0, -1), 3, primary_color),  # Blue accent line on left
        ]))
        story.append(title_page_table)
        story.append(Spacer(1, 0.5 * inch))
        
        # Professional bottom border
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#e5e7eb"), spaceAfter=20))
        story.append(Spacer(1, 0.3 * inch))
        
        # ============================================================
        # PERSONAL INFORMATION
        # ============================================================
        # Main section header for Personal Information
        personal_info_detail = data.get('personal_info_detail', '')
        net_worth = data.get('net_worth', '')
        
        # Always show Personal Information section if we have any data
        has_personal_info = personal_info_detail and personal_info_detail != "N/A"
        has_net_worth = net_worth and net_worth != "N/A" and net_worth.strip()
        
        if has_personal_info or has_net_worth:
            section_header = Paragraph(
                f'<font color="{purple_color_hex}" size="24">◉ Personal Information</font>',
                section_style
            )
            story.append(section_header)
            story.append(Spacer(1, 0.25 * inch))
            
            # Get citations for personal information fields
            # Personal info comes from Wikipedia, so only cite Wikipedia (not Twitter/social media)
            personal_info_citation = get_field_citation('personal_info_detail') or get_wikipedia_citation()
            net_worth_citation = get_field_citation('net_worth') or get_wikipedia_citation()
            
            # Split into sentences and add bullet points from personal_info_detail
            bullet_counter = 0
            if personal_info_detail and personal_info_detail != "N/A":
                sentences = [s.strip() for s in personal_info_detail.split('.') if s.strip()]
                for idx, sentence in enumerate(sentences[:8]):  # Limit to 8 bullet points
                    bullet = get_colored_bullet(bullet_counter)
                    # Add citation to every sentence if available
                    citation_text = personal_info_citation if personal_info_citation else ""
                    story.append(Paragraph(f"{bullet} {sentence}.{citation_text}", normal_style))
                    bullet_counter += 1
            
            # Always add net worth as a bullet point if available
            if net_worth and net_worth != "N/A" and net_worth.strip():
                net_worth_str = str(net_worth).strip()
                bullet = get_colored_bullet(bullet_counter)
                citation_text = net_worth_citation if net_worth_citation else ""
                story.append(Paragraph(f"{bullet} Net Worth: {net_worth_str}.{citation_text}", normal_style))
            
            story.append(Spacer(1, 0.4 * inch))
        
        # ============================================================
        # SOCIAL MEDIA PRESENCE
        # ============================================================
        # Section header with space-themed symbol (planet-like)
        section_header = Paragraph(
            f'<font color="{green_color_hex}" size="24">◈ Social Media Presence</font>',
            section_style
        )
        story.append(section_header)
        story.append(Spacer(1, 0.25 * inch))
        
        # Social media links
        social_media = data.get('social_media', {})
        story.append(Paragraph("◆ Platforms", subsection_style))
        
        if social_media and isinstance(social_media, dict) and any(url and url != "N/A" for url in social_media.values()):
            social_data = []
            platform_icons = {
                'twitter': '◆', 'x': '◆', 'instagram': '◆', 'facebook': '◆', 
                'linkedin': '◆', 'youtube': '◆', 'tiktok': '◆',
                'snapchat': '◆', 'pinterest': '◆', 'reddit': '◆',
                'threads': '◆', 'mastodon': '◆', 'medium': '◆', 'github': '◆',
                'discord': '◆', 'telegram': '◆', 'clubhouse': '◆', 'twitch': '◆',
                'patreon': '◆', 'substack': '◆', 'bluesky': '◆', 'truth social': '◆',
                'tumblr': '◆', 'vimeo': '◆', 'soundcloud': '◆', 'spotify': '◆',
                'apple music': '◆', 'onlyfans': '◆', 'cameo': '◆'
            }
            # Get citations for each platform - ensure LinkedIn is included
            for platform, url in social_media.items():
                if url and url != "N/A":
                    icon = platform_icons.get(platform.lower(), '◆')
                    # Get citation for this specific platform URL
                    platform_citation = get_citation(url) if url.startswith("http") else ""
                    # Format URL with citation as HTML
                    if platform_citation:
                        url_with_citation = Paragraph(f'<font color="{primary_color_hex}">{url}</font>{platform_citation}', ParagraphStyle(
                            'SocialMediaURL',
                            parent=styles['Normal'],
                            fontSize=10,
                            textColor=primary_color,
                            fontName='Helvetica',
                        ))
                    else:
                        url_with_citation = Paragraph(f'<font color="{primary_color_hex}">{url}</font>', ParagraphStyle(
                            'SocialMediaURL',
                            parent=styles['Normal'],
                            fontSize=10,
                            textColor=primary_color,
                            fontName='Helvetica',
                        ))
                    # Format platform name nicely (handle special cases like "twitter/x", "truth social", etc.)
                    platform_display = platform.replace('_', ' ').replace('-', ' ')
                    # Capitalize each word
                    platform_display = ' '.join(word.capitalize() for word in platform_display.split())
                    # Handle special cases
                    if 'x' in platform.lower() and 'twitter' not in platform.lower():
                        platform_display = 'X (Twitter)'
                    elif 'twitter' in platform.lower():
                        platform_display = 'Twitter/X'
                    social_data.append([f'{icon} {platform_display}', url_with_citation])
            
            if social_data:
                # Color each row differently
                colors_list = [green_color, accent_color, orange_color, pink_color, purple_color]
                table_style = [
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  # Bold labels
                    ('FONTSIZE', (0, 0), (0, -1), 11),  # Larger font for labels
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]
                for i in range(len(social_data)):
                    table_style.append(('BACKGROUND', (0, i), (0, i), colors_list[i % len(colors_list)]))
                    table_style.append(('TEXTCOLOR', (0, i), (0, i), colors.white))
                
                social_table = Table(social_data, colWidths=[1.8*inch, 4.7*inch])
                social_table.setStyle(TableStyle(table_style))
                story.append(social_table)
                story.append(Spacer(1, 0.15 * inch))
                
                # Add citation explanation note
                story.append(Spacer(1, 0.2 * inch))
        else:
            story.append(Paragraph("No social media links available.", normal_style))
            story.append(Spacer(1, 0.2 * inch))
        
        # Detailed social media information with bullet points
        story.append(Paragraph("◆ Social Media Overview", subsection_style))
        social_detail = data.get('social_media_detail', '')
        bullet_counter = 0
        # Get citation for social media - check if we have LinkedIn or other social media URLs
        social_media_urls = []
        social_media_dict = data.get('social_media', {})
        if isinstance(social_media_dict, dict):
            for platform, url in social_media_dict.items():
                if url and url != "N/A" and isinstance(url, str) and url.startswith("http"):
                    social_media_urls.append(url)
        
        # Social media detail comes from OpenAI, but we cite the actual social media platform URLs
        # Only cite actual social media URLs, not other sources
        linkedin_citation = ""
        if 'linkedin' in social_media_dict and social_media_dict.get('linkedin'):
            linkedin_citation = get_citation(social_media_dict['linkedin'])
        
        # Only use social media URLs for citation, don't fallback to Wikipedia/news
        social_citation = linkedin_citation or (get_citation(social_media_urls[0]) if social_media_urls else "")
        
        if social_detail and social_detail != "N/A":
            # Split into sentences and add bullet points with colorful shapes
            sentences = [s.strip() for s in social_detail.split('.') if s.strip()]
            for idx, sentence in enumerate(sentences):
                bullet = get_colored_bullet(bullet_counter)
                # Add citation to every sentence if available
                citation_text = social_citation if social_citation else ""
                story.append(Paragraph(f"{bullet} {sentence}.{citation_text}", normal_style))
                bullet_counter += 1
        else:
            # Fallback: use Instagram posts if available
            insta_posts = data.get('instagram_posts', [])
            if insta_posts:
                bullet = get_colored_bullet(bullet_counter)
                story.append(Paragraph(f"{bullet} Active on social media with {len(insta_posts)} recent posts.", normal_style))
                bullet_counter += 1
                bullet = get_colored_bullet(bullet_counter)
                story.append(Paragraph(f"{bullet} Engages with followers through various platforms.", normal_style))
            else:
                bullet = get_colored_bullet(bullet_counter)
                story.append(Paragraph(f"{bullet} <i>No social media overview available.</i>", normal_style))
        
        story.append(Spacer(1, 0.4 * inch))
        
        # ============================================================
        # CAREER
        # ============================================================
        # Section header with space-themed symbol (rocket-like)
        section_header = Paragraph(
            f'<font color="{orange_color_hex}" size="24">▲ Career</font>',
            section_style
        )
        story.append(section_header)
        story.append(Spacer(1, 0.25 * inch))
        
        career = data.get('career', 'N/A')
        bullet_counter = 0
        # Get citation for career section - Career comes from OpenAI/Wikipedia, NOT from Twitter
        # Only cite Wikipedia or news articles, never social media for career info
        career_citation = get_field_citation('career') or get_wikipedia_citation()
        # Only use news articles if Wikipedia not available (career info doesn't come from Twitter)
        if not career_citation:
            news_items = data.get('news', [])
            if news_items and isinstance(news_items[0], dict) and news_items[0].get('url'):
                career_citation = get_citation(news_items[0]['url'])
        
        if career and career != "N/A":
            # Split into sentences and add bullet points with colorful shapes
            sentences = [s.strip() for s in career.split('.') if s.strip()]
            for idx, sentence in enumerate(sentences):
                bullet = get_colored_bullet(bullet_counter)
                # Add citation to every sentence if available
                citation_text = career_citation if career_citation else ""
                story.append(Paragraph(f"{bullet} {sentence}.{citation_text}", normal_style))
                bullet_counter += 1
        else:
            # Fallback: extract career info from bio
            # Bio comes from OpenAI, cite Wikipedia if available (bio doesn't come from Twitter)
            bio = data.get('bio', '')
            bio_citation = get_field_citation('bio') or get_wikipedia_citation()
            if bio and bio != "N/A":
                sentences = [s.strip() for s in bio.split('.') if s.strip()]
                for idx, sentence in enumerate(sentences[:4]):  # Limit to 4 bullet points
                    bullet = get_colored_bullet(bullet_counter)
                    # Add citation to every sentence if available
                    citation_text = bio_citation if bio_citation else ""
                    story.append(Paragraph(f"{bullet} {sentence}.{citation_text}", normal_style))
                    bullet_counter += 1
            else:
                bullet = get_colored_bullet(bullet_counter)
                story.append(Paragraph(f"{bullet} <i>No detailed career information available.</i>", normal_style))
        story.append(Spacer(1, 0.4 * inch))
        
        # ============================================================
        # NOTABLE WORK
        # ============================================================
        # Section header with space-themed symbol (star)
        section_header = Paragraph(
            f'<font color="{red_color_hex}" size="24">★ Notable Work</font>',
            section_style
        )
        story.append(section_header)
        story.append(Spacer(1, 0.25 * inch))
        
        notable_work = data.get('notable_work', 'N/A')
        bullet_counter = 0
        # Get citation for notable work - Notable work comes from OpenAI/Wikipedia, NOT from Twitter
        # Only cite Wikipedia or news articles, never social media for notable work
        notable_work_citation = get_field_citation('notable_work') or get_wikipedia_citation()
        # Only use news articles if Wikipedia not available (notable work doesn't come from Twitter)
        if not notable_work_citation:
            news_items = data.get('news', [])
            if news_items and isinstance(news_items[0], dict) and news_items[0].get('url'):
                notable_work_citation = get_citation(news_items[0]['url'])
        
        if notable_work and notable_work != "N/A":
            # Split into sentences and add bullet points with colorful shapes
            sentences = [s.strip() for s in notable_work.split('.') if s.strip()]
            for idx, sentence in enumerate(sentences):
                bullet = get_colored_bullet(bullet_counter)
                # Add citation to every sentence if available
                citation_text = notable_work_citation if notable_work_citation else ""
                story.append(Paragraph(f"{bullet} {sentence}.{citation_text}", normal_style))
                bullet_counter += 1
        else:
            # Fallback: use news items as notable work
            news_items = data.get('news', [])
            if news_items:
                story.append(Paragraph("★ Recent Notable Achievements", subsection_style))
                for idx, item in enumerate(news_items[:5]):  # Show up to 5 items
                    if isinstance(item, dict):
                        title = item.get('title', 'Untitled')
                        news_url = item.get('url', '')
                        # Use actual news article citation (news comes from NewsAPI, not Twitter)
                        citation_text = get_citation(news_url) if news_url else ""
                        bullet = get_colored_bullet(bullet_counter)
                        story.append(Paragraph(f"{bullet} {title}{citation_text}", normal_style))
                        story.append(Spacer(1, 0.08 * inch))
                        bullet_counter += 1
            else:
                bullet = get_colored_bullet(bullet_counter)
                citation_text = notable_work_citation if notable_work_citation else ""
                story.append(Paragraph(f"{bullet} <i>No detailed notable work information available.</i>{citation_text}", normal_style))
        
        # ============================================================
        # REFERENCES SECTION
        # ============================================================
        story.append(Spacer(1, 0.4 * inch))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#e5e7eb"), spaceAfter=15))
        
        # References section header
        references_style = ParagraphStyle(
            'ReferencesStyle',
            parent=styles['Heading2'],
            fontSize=22,
            spaceAfter=12,
            spaceBefore=10,
            textColor=secondary_color,
            fontName='Helvetica-Bold',
        )
        story.append(Paragraph("References", references_style))
        story.append(Spacer(1, 0.15 * inch))
        
        # Introductory text explaining references
        intro_text_style = ParagraphStyle(
            'IntroTextStyle',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=15,
            textColor=text_dark,
            fontName='Helvetica',
            alignment=TA_JUSTIFY,
        )
        intro_text = Paragraph(
            "The following sources were used to compile this profile, with corresponding bracketed numbers used for citation throughout the text.",
            intro_text_style
        )
        story.append(intro_text)
        story.append(Spacer(1, 0.2 * inch))
        
        # Helper function to extract source title from URL
        def extract_source_title(url: str, name: str) -> str:
            """Extract a descriptive title from URL."""
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '').lower()
                path = parsed.path.strip('/').replace('_', ' ').replace('-', ' ')
                
                # Wikipedia
                if 'wikipedia.org' in domain:
                    page_name = path.split('/')[-1] if '/' in path else path
                    if page_name:
                        page_name = page_name.replace('_', ' ').title()
                        return f"{page_name} - Wikipedia"
                    return f"{name} - Wikipedia"
                
                # News sites
                elif any(news_domain in domain for news_domain in ['bbc.com', 'cnn.com', 'reuters.com', 'nytimes.com', 'theguardian.com', 'forbes.com', 'bloomberg.com', 'cnbc.com']):
                    # Try to extract title from path
                    if path:
                        title_parts = [p.replace('-', ' ').title() for p in path.split('/') if p and p not in ['article', 'news', 'story']]
                        if title_parts:
                            return f"{' '.join(title_parts[:3])} - {domain.split('.')[0].title()}"
                    return f"{name} - {domain.split('.')[0].title()} News"
                
                # Social media
                elif 'instagram.com' in domain:
                    return f"{name} - Instagram Profile"
                elif 'twitter.com' in domain or 'x.com' in domain:
                    return f"{name} - Twitter/X Profile"
                elif 'linkedin.com' in domain:
                    return f"{name} - LinkedIn Profile"
                elif 'facebook.com' in domain:
                    return f"{name} - Facebook Profile"
                elif 'youtube.com' in domain:
                    return f"{name} - YouTube"
                
                # Research/PDF sites
                elif 'researchgate.net' in domain:
                    return f"{name}: Bibliography and Research - ResearchGate"
                elif 'scribd.com' in domain:
                    return f"{name} | PDF - Scribd"
                elif 'slideshare.net' in domain:
                    return f"{name}: Bibliography | PPTX - Slideshare"
                
                # Generic - use domain name
                else:
                    domain_name = domain.split('.')[0].title() if '.' in domain else domain.title()
                    return f"{name} - {domain_name}"
            except:
                # Fallback
                return f"{name} - Web Source"
        
        # Helper function to format APA reference
        def format_apa_reference(url: str, title: str, name: str) -> str:
            """Format a reference in APA style."""
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '').lower()
                current_year = datetime.now().year
                
                # Wikipedia format: Article title. (Year, Month Day). In Wikipedia. URL
                if 'wikipedia.org' in domain:
                    page_name = title.replace(' - Wikipedia', '') if ' - Wikipedia' in title else name
                    return f"{page_name}. ({current_year}). In <i>Wikipedia</i>. {url}"
                
                # News articles format: Article title. (Year). Source Name. URL
                elif any(news_domain in domain for news_domain in ['bbc.com', 'cnn.com', 'reuters.com', 'nytimes.com', 'theguardian.com', 'forbes.com', 'bloomberg.com']):
                    source_name = domain.split('.')[0].title()
                    article_title = title.replace(f' - {source_name} News', '') if f' - {source_name} News' in title else title
                    return f"{article_title}. ({current_year}). <i>{source_name}</i>. {url}"
                
                # Social media format: Name. (Year). [Profile]. Platform. URL
                elif 'twitter.com' in domain or 'x.com' in domain:
                    return f"{name}. ({current_year}). [Profile]. <i>Twitter</i>. {url}"
                elif 'instagram.com' in domain:
                    return f"{name}. ({current_year}). [Profile]. <i>Instagram</i>. {url}"
                elif 'linkedin.com' in domain:
                    return f"{name}. ({current_year}). [Profile]. <i>LinkedIn</i>. {url}"
                elif 'facebook.com' in domain:
                    return f"{name}. ({current_year}). [Profile]. <i>Facebook</i>. {url}"
                elif 'youtube.com' in domain:
                    return f"{name}. ({current_year}). [Channel]. <i>YouTube</i>. {url}"
                
                # Generic web source format: Title. (Year). Source Name. URL
                else:
                    source_name = domain.split('.')[0].title() if '.' in domain else "Web Source"
                    return f"{title}. ({current_year}). <i>{source_name}</i>. {url}"
            except:
                return f"{title}. ({datetime.now().year}). {url}"
        
        # Create APA-style references list
        if sources:
            # Helper function to filter out only truly unreliable sources
            def is_useful_source(url: str) -> bool:
                """Filter out only unreliable sources, keep all legitimate ones."""
                if not url:
                    return False
                
                url_lower = str(url).lower()
                
                # Remove only truly unreliable sources
                unreliable_patterns = [
                    'serpapi.com', 'google.com/search', 'bing.com/search',
                    'duckduckgo.com', 'search?', 'image?', 'photo?',
                    'googleusercontent.com', 'gstatic.com'
                ]
                if any(pattern in url_lower for pattern in unreliable_patterns):
                    return False
                
                # Keep ALL sources that have a proper domain structure
                # This includes Wikipedia, news, social media, official sites, etc.
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    if parsed.netloc and '.' in parsed.netloc:
                        # Has a proper domain, keep it
                        return True
                except:
                    pass
                
                return False
            
            # Filter sources - only remove truly unreliable ones
            filtered_sources = [s for s in sources if is_useful_source(s)]
            
            # Remove duplicates while preserving order
            seen = set()
            unique_sources = []
            for source in filtered_sources:
                if source and source not in seen:
                    seen.add(source)
                    unique_sources.append(source)
            
            # Get news items for better titles FIRST (before sorting)
            news_items = data.get('news', [])
            news_url_to_title = {}
            for item in news_items:
                if isinstance(item, dict) and item.get('url') and item.get('title'):
                    news_url_to_title[item['url']] = item['title']
                elif hasattr(item, 'url') and hasattr(item, 'title'):
                    # Handle NewsItem Pydantic model
                    news_url_to_title[getattr(item, 'url')] = getattr(item, 'title', '')
            
            # Include ALL sources - no artificial limit
            # Prioritize: Wikipedia first, then news, then others (for sorting only)
            wikipedia_sources = [s for s in unique_sources if s and 'wikipedia.org' in str(s).lower()]
            
            # Include ALL news sources - check if URL is in news_url_to_title (most reliable)
            # Also check for common news domain patterns
            news_sources = []
            other_sources = []
            for s in unique_sources:
                if s not in wikipedia_sources:
                    # Check if it's a news article (in our news_url_to_title dict) - MOST RELIABLE
                    if s in news_url_to_title:
                        news_sources.append(s)
                    # Or check for news domain patterns
                    elif any(pattern in str(s).lower() for pattern in [
                        'bbc.com', 'cnn.com', 'reuters.com', 'nytimes.com', 'theguardian.com', 
                        'forbes.com', 'bloomberg.com', 'wsj.com', 'economist.com', 'time.com', 
                        'newsweek.com', 'ap.org', 'npr.org', 'abcnews', 'cbsnews', 'nbcnews', 
                        'usatoday.com', 'latimes.com', 'washingtonpost.com', 'techcrunch.com',
                        'theverge.com', 'wired.com', 'businessinsider.com', 'cnbc.com',
                        '/news/', '/article', '.com/news', '.org/news', '.net/news', 'news.'
                    ]):
                        news_sources.append(s)
                    else:
                        other_sources.append(s)
            
            # Sort: Wikipedia first, then news, then others (but include ALL)
            sorted_sources = wikipedia_sources + news_sources + other_sources
            
            logger.info(f"📄 References included: Wikipedia: {len(wikipedia_sources)}, News: {len(news_sources)}, Other: {len(other_sources)} (Total: {len(sorted_sources)} from {len(sources)} collected)")
            
            # APA style references - formatted list with hanging indent
            ref_item_style = ParagraphStyle(
                'RefItemStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                spaceAfter=8,
                textColor=text_dark,
                fontName='Helvetica',
                leftIndent=0.5 * inch,
                hangingIndent=-0.3 * inch,
            )
            
            if sorted_sources:
                # Format references as: [1] Source Name. Title
                ref_numbered_style = ParagraphStyle(
                    'RefNumberedStyle',
                    parent=styles['Normal'],
                    fontSize=11,
                    leading=16,
                    spaceAfter=10,
                    textColor=text_dark,
                    fontName='Helvetica',
                    leftIndent=0,
                )
                
                for idx, source_url in enumerate(sorted_sources, start=1):
                    # Use news title if available, otherwise extract from URL
                    if source_url in news_url_to_title:
                        source_title = news_url_to_title[source_url]
                    else:
                        source_title = extract_source_title(source_url, name)
                    
                    # Extract source name (organization/domain name)
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(source_url)
                        domain = parsed.netloc.replace('www.', '').lower()
                        
                        # Get source name based on domain
                        if 'wikipedia.org' in domain:
                            source_name = "Wikipedia"
                        elif 'tesla.com' in domain:
                            source_name = "Tesla Inc."
                        elif 'spacex.com' in domain or 'spacex' in domain:
                            source_name = "Space Exploration Technologies Corp."
                        elif 'nytimes.com' in domain:
                            source_name = "New York Times"
                        elif 'wsj.com' in domain or 'wallstreetjournal' in domain:
                            source_name = "Wall Street Journal"
                        elif 'bbc.com' in domain:
                            source_name = "BBC"
                        elif 'cnn.com' in domain:
                            source_name = "CNN"
                        elif 'reuters.com' in domain:
                            source_name = "Reuters"
                        elif 'forbes.com' in domain:
                            source_name = "Forbes"
                        elif 'bloomberg.com' in domain:
                            source_name = "Bloomberg"
                        elif 'theguardian.com' in domain:
                            source_name = "The Guardian"
                        elif 'linkedin.com' in domain:
                            source_name = "LinkedIn"
                        elif 'twitter.com' in domain or 'x.com' in domain:
                            source_name = "Twitter/X"
                        elif 'instagram.com' in domain:
                            source_name = "Instagram"
                        elif 'facebook.com' in domain:
                            source_name = "Facebook"
                        elif 'youtube.com' in domain:
                            source_name = "YouTube"
                        else:
                            # Extract domain name and format it nicely
                            domain_parts = domain.split('.')
                            if len(domain_parts) >= 2:
                                # Use the main domain name (e.g., "tesla" from "tesla.com")
                                main_domain = domain_parts[-2] if domain_parts[-2] not in ['com', 'org', 'net', 'edu', 'gov'] else domain_parts[0]
                                source_name = main_domain.replace('-', ' ').replace('_', ' ').title()
                                # Add "Inc." or "Corp." for business domains if appropriate
                                if any(word in main_domain for word in ['tech', 'corp', 'company', 'business']):
                                    if 'corp' not in main_domain.lower() and 'inc' not in main_domain.lower():
                                        source_name += " Corp."
                            else:
                                source_name = domain.title()
                    except:
                        source_name = "Source"
                    
                    # Format title (remove source name from title if it's redundant)
                    title_text = source_title
                    if source_name.lower() in title_text.lower():
                        # Remove source name from title to avoid redundancy
                        title_text = title_text.replace(f" - {source_name}", "").replace(f"{source_name} - ", "").strip()
                    
                    # If title is too generic, use a more descriptive one
                    if not title_text or title_text == f"{name} - Web Source" or title_text == f"{name} - {source_name}":
                        # Create a descriptive title based on source type
                        if 'wikipedia.org' in str(source_url).lower():
                            title_text = f"{name}"
                        elif any(news_domain in str(source_url).lower() for news_domain in ['bbc.com', 'cnn.com', 'reuters.com', 'nytimes.com', 'theguardian.com', 'forbes.com', 'bloomberg.com']):
                            title_text = f"{name}'s Latest"
                        elif 'linkedin.com' in str(source_url).lower():
                            title_text = "Professional Profile"
                        elif 'twitter.com' in str(source_url).lower() or 'x.com' in str(source_url).lower():
                            title_text = "Profile"
                        else:
                            title_text = f"{name} Profile"
                    
                    # Format as: [1] Source Name. Title (number plain, source bold, title italic)
                    reference_text = f'[{idx}] <b>{source_name}</b>. <i>{title_text}</i>'
                    story.append(Paragraph(reference_text, ref_numbered_style))
            else:
                # No useful sources after filtering
                no_sources_style = ParagraphStyle(
                    'NoSourcesStyle',
                    parent=styles['Normal'],
                    fontSize=10,
                    leading=14,
                    textColor=text_light,
                    fontName='Helvetica-Oblique',
                )
                story.append(Paragraph("<i>No reliable sources available.</i>", no_sources_style))
        else:
            no_sources_style = ParagraphStyle(
                'NoSourcesStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=14,
                textColor=text_light,
                fontName='Helvetica-Oblique',
            )
            story.append(Paragraph("<i>No sources available.</i>", no_sources_style))
        
        story.append(Spacer(1, 0.3 * inch))
        
        # Footer decoration
        story.append(HRFlowable(width="100%", thickness=4, color=primary_color, spaceAfter=10))
        
        # Simple footer
        footer_text = Paragraph(
            f'<para alignment="center"><font color="{primary_color_hex}" size="11"><b>Generated with AI Technology</b></font></para>',
            normal_style
        )
        story.append(footer_text)
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)

        # Clean up photo temp file after build
        if _photo_tmp_path:
            try:
                import os as _os
                _os.unlink(_photo_tmp_path)
            except Exception:
                pass

        return buffer.getvalue()


