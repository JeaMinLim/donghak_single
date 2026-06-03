from __future__ import annotations

import re
from pathlib import Path

try:
    import lxml.etree as ET
    _use_lxml = True
except ImportError:
    import xml.etree.ElementTree as ET
    _use_lxml = False


def _sanitize_xml_text(raw: str) -> str:
    text = re.sub(r'&(?!#?[A-Za-z0-9]+;)', '&amp;', raw)
    text = re.sub(r'<(?!(?:[A-Za-z_:/?!]))', '&lt;', text)
    return text


def parse_xml_file(xml_path: Path) -> ET.ElementTree:
    xml_path = xml_path.expanduser()
    if _use_lxml:
        parser = ET.XMLParser(recover=True, encoding='utf-8')
        try:
            return ET.parse(str(xml_path), parser)
        except Exception:
            pass

    raw_text = xml_path.read_text(encoding='utf-8', errors='replace')
    sanitized = _sanitize_xml_text(raw_text)
    root = ET.fromstring(sanitized)
    return ET.ElementTree(root)


def _find_section(tree: ET.ElementTree, title_text: str) -> ET.Element | None:
    root = tree.getroot()
    for section in root.findall('.//SECTION-2'):
        title = section.find('TITLE')
        if title is None:
            continue
        if title.text and title_text in title.text.strip():
            return section
    return None


def _safe_filename(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_\-]+", "_", value).strip("_")


def save_section_xml(section: ET.Element, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if _use_lxml:
        xml_bytes = ET.tostring(section, encoding='utf-8', pretty_print=True, xml_declaration=True)
    else:
        xml_bytes = ET.tostring(section, encoding='utf-8', method='xml')
    out_path.write_bytes(xml_bytes)
    return out_path


def extract_section_by_title(
    xml_path: Path,
    title_text: str,
    out_dir: Path,
    out_name: str | None = None,
) -> Path:
    xml_path = xml_path.expanduser()
    out_dir = out_dir.expanduser()

    print(f"XML 경로: {xml_path.parent}")
    print(f"파일명: {xml_path.name}")

    if not xml_path.exists():
        raise FileNotFoundError(f"XML 파일을 찾을 수 없습니다: {xml_path}")

    tree = parse_xml_file(xml_path)
    section = _find_section(tree, title_text)
    if section is None:
        raise ValueError(f"TITLE='{title_text}'인 SECTION-2를 찾을 수 없습니다.")

    if out_name is None:
        out_name = f"{xml_path.stem}_{_safe_filename(title_text)}.xml"

    return save_section_xml(section, out_dir / out_name)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _element_text(element: ET.Element) -> str:
    return _normalize_whitespace(''.join(element.itertext()))


def _table_to_markdown(table: ET.Element) -> str:
    rows: list[list[str]] = []
    for tr in table.findall('.//TR'):
        cells: list[str] = []
        for cell in tr:
            if cell.tag not in ('TD', 'TH', 'TE'):
                continue
            cell_text = _element_text(cell)
            colspan = int(cell.get('COLSPAN', '1')) if cell.get('COLSPAN', '1').isdigit() else 1
            cells.append(cell_text)
            cells.extend([''] * (colspan - 1))
        if cells:
            rows.append(cells)

    if not rows:
        return ''

    max_cols = max(len(row) for row in rows)
    rows = [row + [''] * (max_cols - len(row)) for row in rows]
    header = rows[0]
    separator = ['---'] * len(header)
    lines = [f"| {' | '.join(header)} |", f"| {' | '.join(separator)} |"]
    for row in rows[1:]:
        lines.append(f"| {' | '.join(row)} |")
    return '\n'.join(lines)


def convert_extracted_xml_to_markdown(xml_path: Path, md_path: Path | None = None) -> Path:
    xml_path = xml_path.expanduser()
    if md_path is None:
        md_path = xml_path.with_suffix('.md')
    md_path = md_path.expanduser()

    if not xml_path.exists():
        raise FileNotFoundError(f"XML 파일을 찾을 수 없습니다: {xml_path}")

    tree = parse_xml_file(xml_path)
    root = tree.getroot()
    md_lines: list[str] = []

    title = root.find('TITLE')
    if title is not None and title.text:
        md_lines.append(f"# {_element_text(title)}")
        md_lines.append('')

    for element in root:
        if element.tag == 'TITLE':
            continue
        if element.tag == 'P':
            text = _element_text(element)
            if text:
                md_lines.append(text)
                md_lines.append('')
        elif element.tag in ('TABLE', 'TABLE-GROUP'):
            table_md = _table_to_markdown(element)
            if table_md:
                md_lines.append(table_md)
                md_lines.append('')
        elif element.tag == 'PGBRK':
            md_lines.append('---')
            md_lines.append('')

    md_text = '\n'.join(line for line in md_lines if line is not None)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_text, encoding='utf-8')
    return md_path
