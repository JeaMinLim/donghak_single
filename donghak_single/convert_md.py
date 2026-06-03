from __future__ import annotations

import argparse
import re
from datetime import datetime
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


def _parse_xml(xml_path: Path) -> ET.Element:
    raw_text = xml_path.read_text(encoding='utf-8', errors='replace')
    if _use_lxml:
        parser = ET.XMLParser(recover=True, encoding='utf-8')
        try:
            return ET.fromstring(raw_text.encode('utf-8'), parser)
        except Exception:
            pass

    sanitized = _sanitize_xml_text(raw_text)
    return ET.fromstring(sanitized)


def _normalize_text(text: str | None) -> str:
    if not text:
        return ''
    return ' '.join(text.split())


def _element_text(elem: ET.Element) -> str:
    return _normalize_text(''.join(elem.itertext()))


def _render_paragraph(elem: ET.Element) -> str:
    text = _element_text(elem)
    if not text:
        return ''
    if elem.attrib.get('USERMARK', '').endswith('B'):
        text = f'**{text}**'
    return f'{text}\n\n'


def _render_title(elem: ET.Element) -> str:
    title = _element_text(elem)
    if not title:
        return ''
    return f'## {title}\n\n'


def _render_table(elem: ET.Element) -> str:
    rows: list[list[str]] = []
    has_th = False
    for tr in elem.findall('.//TR'):
        cells: list[str] = []
        for child in tr:
            tag = child.tag.upper()
            if tag in {'TH', 'TD', 'TE'}:
                cells.append(_element_text(child))
        if cells:
            rows.append(cells)
            if any(child.tag.upper() == 'TH' for child in tr):
                has_th = True

    if not rows:
        return ''

    markdown_lines: list[str] = []
    if has_th:
        header = rows[0]
        separator = ['---'] * len(header)
        markdown_lines.append('| ' + ' | '.join(header) + ' |')
        markdown_lines.append('| ' + ' | '.join(separator) + ' |')
        for row in rows[1:]:
            markdown_lines.append('| ' + ' | '.join(row) + ' |')
    else:
        header = rows[0]
        separator = ['---'] * len(header)
        markdown_lines.append('| ' + ' | '.join(header) + ' |')
        markdown_lines.append('| ' + ' | '.join(separator) + ' |')
        for row in rows[1:]:
            markdown_lines.append('| ' + ' | '.join(row) + ' |')

    return '\n'.join(markdown_lines) + '\n\n'


def convert_xml_to_markdown(xml_path: Path) -> str:
    root = _parse_xml(xml_path)
    if root.tag != 'SECTION-2':
        section = root.find('.//SECTION-2')
        if section is None:
            section = root
    else:
        section = root

    markdown_parts: list[str] = []
    for child in section:
        tag = child.tag.upper()
        if tag == 'TITLE':
            markdown_parts.append(_render_title(child))
        elif tag == 'P':
            paragraph = _render_paragraph(child)
            if paragraph:
                markdown_parts.append(paragraph)
        elif tag in {'TABLE', 'TABLE-GROUP'}:
            table_md = _render_table(child)
            if table_md:
                markdown_parts.append(table_md)
        elif tag == 'PGBRK':
            markdown_parts.append('\n')
        elif tag == 'SPAN':
            text = _element_text(child)
            if text:
                markdown_parts.append(text + '\n\n')
        else:
            text = _element_text(child)
            if text:
                markdown_parts.append(text + '\n\n')

    return ''.join(markdown_parts).strip() + '\n'


def _render_markdown_header(metadata: dict[str, str] | None) -> str:
    if not metadata:
        return ''

    lines: list[str] = []
    for label, value in metadata.items():
        if value is not None:
            clean_value = _normalize_text(value)
            lines.append(f'{label}: {clean_value}')

    if not lines:
        return ''

    return '\n'.join(lines).strip() + '\n\n---\n\n'


def save_markdown_from_xml(
    xml_path: Path,
    output_path: Path,
    metadata: dict[str, str] | None = None,
) -> Path:
    markdown = convert_xml_to_markdown(xml_path)
    header = _render_markdown_header(metadata)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f'{header}{markdown}', encoding='utf-8')
    return output_path


def _strip_leading_metadata(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    if not lines:
        return ''

    idx = 0
    if lines[0].startswith('#'):
        # no metadata block, return original
        return markdown_text

    while idx < len(lines):
        if lines[idx].strip() == '---':
            idx += 1
            break
        idx += 1

    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    if idx >= len(lines):
        return ''

    return '\n'.join(lines[idx:]).strip() + '\n'


def merge_markdown_documents(
    output_path: Path,
    company_name: str,
    corp_code: str,
    items: list[dict[str, str]],
    markdown_dir: Path,
    created_at: str | None = None,
) -> Path:
    company_name = company_name.strip() or corp_code
    created_at = created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    header_lines = [
        f'# {company_name} 공시 통합 문서',
        f'회사명: {company_name}',
        f'종목코드: {corp_code}',
        f'생성일: {created_at}',
        '',
        '## 포함한 문서 목록',
    ]

    for item in items:
        header_lines.append(f"- {item['rcept_dt']} | {item['rcept_no']} | {item['report_nm']}")

    header_lines.append('')

    body_lines: list[str] = []
    for item in items:
        body_lines.append(f"# {company_name} - {item['report_nm']}")
        body_lines.append(f"**공시접수 날짜:** {item['rcept_dt']}  ")
        body_lines.append(f"**접수번호:** {item['rcept_no']}")
        body_lines.append('')

        md_path = item.get('markdown_path')
        if md_path is None:
            md_path = markdown_dir / f"{item['rcept_no']}.md"
        else:
            md_path = Path(md_path)

        if md_path.exists():
            raw_content = md_path.read_text(encoding='utf-8')
            body_lines.append(_strip_leading_metadata(raw_content))
        else:
            body_lines.append(f'_Markdown 파일을 찾을 수 없습니다: {md_path}_')

        body_lines.append('')

    merged_text = '\n'.join(header_lines + [''] + body_lines).strip() + '\n'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(merged_text, encoding='utf-8')
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description='Convert extracted SECTION-2 XML to Markdown.')
    parser.add_argument('xml_file', type=Path, help='Input XML file path')
    parser.add_argument('-o', '--output', type=Path, help='Output Markdown file path')
    args = parser.parse_args()

    xml_path = args.xml_file.expanduser()
    if not xml_path.exists():
        print(f'XML 파일을 찾을 수 없습니다: {xml_path}')
        return 1

    output_path = args.output
    if output_path is None:
        output_path = xml_path.with_suffix('.md')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    markdown = convert_xml_to_markdown(xml_path)
    output_path.write_text(markdown, encoding='utf-8')
    print(f'변환 완료: {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
