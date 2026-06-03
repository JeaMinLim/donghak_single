#!/usr/bin/env python3
import json
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from .corp_code import fetch_bytes, get_api_key

DEFAULT_LIST_API = "https://opendart.fss.or.kr/api/list.json"
DEFAULT_DOC_API = "https://opendart.fss.or.kr/api/document.xml"  # document API endpoint (rcept_no)
REPORT_DIR = Path("data") / "report"
UNZIP_DIR = REPORT_DIR / "unzip"


def fetch_disclosures_json(corp_code: str, bgn_de: str, end_de: str, pblntf_ty: str = "A") -> str:
    """Fetch disclosure list JSON from OpenDart for given corp_code and date range.

    Returns the raw JSON text as a string.
    """
    api_key = get_api_key()
    params = (
        f"crtfc_key={api_key}&corp_code={corp_code}"
        f"&bgn_de={bgn_de}&end_de={end_de}&pblntf_ty={pblntf_ty}"
        f"&page_count=100"
    )
    url = f"{DEFAULT_LIST_API}?{params}"
    data = fetch_bytes(url)
    return data.decode("utf-8")


def parse_disclosures_json(raw_json: str) -> dict:
    """Parse raw disclosure JSON and return the parsed structure."""
    return json.loads(raw_json)


def check_api_status(parsed: dict) -> bool:
    """Check OpenDart API status field.

    Returns True if status == "000" (normal). If not, prints the message
    from the response and returns False.
    """
    if not isinstance(parsed, dict):
        print("API 응답이 올바른 JSON 형식이 아닙니다.")
        return False
    status = parsed.get("status")
    if status != "000":
        message = parsed.get("message", "알 수 없는 오류")
        print(f"API 오류: {message}")
        return False
    return True


def extract_zip_to_unzip_dir(zip_path: Path, unzip_dir: Path, show_progress: bool = True) -> None:
    """Extract ZIP contents into the flatten unzip directory."""
    if not zip_path.exists():
        return

    unzip_dir.mkdir(parents=True, exist_ok=True)
    try:
        extracted = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                if member.is_dir():
                    continue
                basename = Path(member.filename).name
                if not basename:
                    continue
                target_path = unzip_dir / basename
                with zf.open(member) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())
                extracted.append(target_path)
        if show_progress:
            print(f"압축 해제 완료 -> {unzip_dir} ({len(extracted)} files)")
    except zipfile.BadZipFile:
        print(f"ZIP 파일이 아니거나 손상됨: {zip_path}")


def download_report_zip(rcept_no: str, dest_dir: Path = REPORT_DIR, show_progress: bool = True) -> Path:
    """Download disclosure original file for given rcept_no and save as ZIP.

    Streams the response and writes to `data/report/<rcept_no>.zip`.
    Returns the saved ZIP path. Raises RuntimeError on HTTP/URL errors.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_path = dest_dir / f"{rcept_no}.zip"
    unzip_dir = UNZIP_DIR

    if out_path.exists():
        if show_progress:
            print(f"{rcept_no}: 이미 다운로드됨, 스킵")
        extract_zip_to_unzip_dir(out_path, unzip_dir, show_progress=show_progress)
        return out_path

    api_key = get_api_key()
    params = f"crtfc_key={api_key}&rcept_no={rcept_no}"
    url = f"{DEFAULT_DOC_API}?{params}"

    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            head = resp.read(1024)
            text_head = None
            try:
                text_head = head.decode("utf-8")
            except Exception:
                text_head = None

            if text_head and (text_head.lstrip().startswith("<?xml") or "<status>" in text_head):
                rest = resp.read()
                full_text = (head + rest).decode("utf-8", errors="replace")
                try:
                    root = ET.fromstring(full_text)
                    status = root.findtext("status")
                    message = root.findtext("message") or ""
                    if status != "000":
                        print(f"문서 다운로드 API 오류: {message}")
                        print("문서 다운로드 API 문서: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003")
                        raise RuntimeError(message)
                except ET.ParseError:
                    pass

            total = resp.getheader("Content-Length")
            total_size = int(total) if total and total.isdigit() else None
            chunk_size = 8192
            downloaded = 0
            with open(out_path, "wb") as f:
                if head:
                    f.write(head)
                    downloaded += len(head)

                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if show_progress:
                        if total_size:
                            percent = downloaded * 100 / total_size
                            print(f"{rcept_no}: {downloaded}/{total_size} bytes ({percent:5.1f}%)", end="\r", flush=True)
                        else:
                            print(f"{rcept_no}: {downloaded} bytes downloaded", end="\r", flush=True)
            if show_progress:
                print()
            extract_zip_to_unzip_dir(out_path, unzip_dir, show_progress=show_progress)
            return out_path
    except HTTPError as exc:
        raise RuntimeError(f"HTTP error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"URL error: {exc.reason}") from exc
