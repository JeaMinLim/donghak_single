#!/usr/bin/env python3
from __future__ import annotations

from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable
import shutil

from .corp_code import find_corp_code_by_query, find_corp_name_by_code, initialize_corpcode
from .corp_disclosure import (
    check_api_status,
    download_report_zip,
    fetch_disclosures_json,
    parse_disclosures_json,
)
from .convert_md import merge_markdown_documents, save_markdown_from_xml
from .extract_xml import extract_section_by_title

TMP_DIR = Path("data/tmp")
MARKDOWN_DIR = Path("markdown")
DATA_DIR = Path("data")
SECTION_DEFINITIONS = [
    ("1. 요약재무정보", "summary"),
    ("4. 매출 및 수주상황", "sales"),
]


@dataclass
class SectionInfo:
    rcept_dt: str
    rcept_no: str
    report_nm: str
    section_label: str
    markdown_path: Path


def parse_search_start_date(date_text: str) -> str:
    date_text = date_text.strip()
    if not date_text:
        return (datetime.now() - timedelta(days=365 * 5)).strftime("%Y%m%d")

    if len(date_text) != 8 or not date_text.isdigit():
        raise ValueError("날짜는 YYYYMMDD 형식의 8자리 숫자여야 합니다.")

    try:
        datetime.strptime(date_text, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("입력한 날짜가 유효하지 않습니다. YYYYMMDD 형식으로 다시 입력하세요.") from exc

    return date_text


def safe_filename(value: str) -> str:
    return "".join(
        ch if ch.isalnum() or ch in (" ", "_", "-") else "_"
        for ch in value.strip()
    ).replace(" ", "_")


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def format_report_section_name(report_nm: str, suffix: str) -> str:
    return f"{report_nm} - {suffix}"


def download_and_extract_report(rcept_no: str) -> Path:
    out_path = download_report_zip(rcept_no)
    print(f"다운로드 완료: {rcept_no} -> {out_path}")
    return Path("data/report/unzip") / f"{rcept_no}.xml"


def extract_and_save_section(
    xml_path: Path,
    rcept_no: str,
    rcept_dt: str,
    report_nm: str,
    title_text: str,
    suffix: str,
) -> SectionInfo:
    xml_path = xml_path.expanduser()
    section_xml = extract_section_by_title(
        xml_path,
        title_text,
        TMP_DIR,
        out_name=f"{rcept_no}_{suffix}.xml",
    )

    metadata = {
        "공시접수 날짜": rcept_dt,
        "접수번호": rcept_no,
        "보고서 이름": format_report_section_name(report_nm, suffix),
    }
    markdown_path = TMP_DIR / f"{rcept_no}_{suffix}.md"
    save_markdown_from_xml(section_xml, markdown_path, metadata=metadata)
    print(f"Markdown 저장 완료: {markdown_path}")

    return SectionInfo(
        rcept_dt=rcept_dt,
        rcept_no=rcept_no,
        report_nm=format_report_section_name(report_nm, suffix),
        section_label=suffix,
        markdown_path=markdown_path,
    )


def format_disclosure_list(parsed: dict) -> None:
    total_count = parsed.get("total_count")
    print(f"총 건수: {total_count}")
    print("공시접수날짜\t|\t접수번호\t|\t보고서이름")
    for item in parsed.get("list", []):
        print(f"{item.get('rcept_dt', '')}\t|\t{item.get('rcept_no', '')}\t|\t{item.get('report_nm', '')}")


def collect_disclosure_sections(list_items: Iterable[dict]) -> list[SectionInfo]:
    saved_sections: list[SectionInfo] = []

    for item in list_items:
        rcept_no = item.get("rcept_no")
        if not rcept_no:
            continue

        rcept_dt = item.get("rcept_dt", "")
        report_nm = item.get("report_nm", "")

        try:
            xml_path = download_and_extract_report(rcept_no)
            if not xml_path.exists():
                print(f"XML 파일 없음: {xml_path}")
                continue

            for title_text, suffix in SECTION_DEFINITIONS:
                try:
                    section_info = extract_and_save_section(
                        xml_path,
                        rcept_no,
                        rcept_dt,
                        report_nm,
                        title_text,
                        suffix,
                    )
                    saved_sections.append(section_info)
                except Exception as exc:
                    print(f"{title_text} 추출 실패: {rcept_no}: {exc}")

        except Exception as exc:
            print(f"다운로드 실패: {rcept_no}: {exc}")

    return saved_sections


def parse_arguments() -> tuple[str | None, str | None]:
    parser = ArgumentParser(description="DART 공시를 검색하고 요약재무정보/매출 및 수주상황을 Markdown으로 변환합니다.")
    parser.add_argument("query", nargs="?", help="회사명 또는 6자리 종목코드")
    parser.add_argument("start_date", nargs="?", help="검색 시작일 YYYYMMDD")
    args = parser.parse_args()
    return args.query, args.start_date


def prompt_query(default_query: str | None) -> str:
    if default_query:
        return default_query.strip()
    return input("회사명 또는 6자리 종목코드를 입력하세요: ").strip()


def prompt_start_date(default_start_date: str | None) -> str:
    if default_start_date is not None:
        return default_start_date
    return input("검색 시작일을 YYYYMMDD 형식으로 입력하세요 (미입력 시 5년간의 기록을 검색): ")


def cleanup_temp_folders() -> None:
    """data 폴더와 markdown 폴더를 삭제합니다."""
    for folder in [DATA_DIR, MARKDOWN_DIR]:
        if folder.exists():
            try:
                shutil.rmtree(folder)
                print(f"삭제됨: {folder}")
            except Exception as exc:
                print(f"삭제 실패: {folder}: {exc}")
        else:
            print(f"존재하지 않음: {folder}")


def main() -> None:
    initialize_corpcode()
    query_arg, date_arg = parse_arguments()

    query = prompt_query(query_arg)
    if not query:
        print("회사명 또는 종목코드를 입력해야 합니다.")
        return

    # 임시파일정리 명령 처리
    if query == "임시파일정리":
        cleanup_temp_folders()
        return

    corp_code = find_corp_code_by_query(query)
    company_name = find_corp_name_by_code(corp_code) if corp_code else query
    if not company_name:
        company_name = query

    if not corp_code:
        print("검색 결과가 없습니다.")
        return

    print(f"검색 결과 corp_code: {corp_code}")

    date_input = prompt_start_date(date_arg)
    try:
        start_date = parse_search_start_date(date_input)
    except ValueError as exc:
        print(exc)
        return

    end_date = datetime.now().strftime("%Y%m%d")
    print(f"검색 시작일: {start_date}, 종료일: {end_date}")

    try:
        disclosures_json = fetch_disclosures_json(corp_code, start_date, end_date)
        parsed = parse_disclosures_json(disclosures_json)
    except Exception as exc:
        print(f"공시 검색 중 오류가 발생했습니다: {exc}")
        return

    if not check_api_status(parsed):
        return

    ensure_directories(TMP_DIR, MARKDOWN_DIR)
    format_disclosure_list(parsed)

    list_items = parsed.get("list", [])
    if not list_items:
        return

    saved_sections = collect_disclosure_sections(list_items)
    if not saved_sections:
        print("추출된 섹션이 없습니다.")
        return

    merged_filename = f"{safe_filename(company_name)}_{datetime.now().strftime('%Y%m%d')}.md"
    merged_path = MARKDOWN_DIR / merged_filename
    merge_markdown_documents(
        merged_path,
        company_name,
        corp_code,
        [
            {
                "rcept_dt": section.rcept_dt,
                "rcept_no": section.rcept_no,
                "report_nm": section.report_nm,
                "markdown_path": str(section.markdown_path),
            }
            for section in saved_sections
        ],
        TMP_DIR,
    )
    print(f"합쳐진 Markdown 저장 완료: {merged_path}")


if __name__ == "__main__":
    main()
