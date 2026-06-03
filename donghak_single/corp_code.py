#!/usr/bin/env python3
import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DATA_DIR = Path("data") / "corpcode"
DEFAULT_ZIP_NAME = "corpCode.zip"
ENV_FILE = ".env"
ENV_KEY = "OPENDART_APIKEY"


def load_env(path: str = ENV_FILE) -> dict:
    env = {}
    if not os.path.exists(path):
        return env

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"\'')
    return env


def get_api_key() -> str:
    env = load_env()
    api_key = os.environ.get(ENV_KEY) or env.get(ENV_KEY)
    if not api_key:
        raise RuntimeError(
            f"API key not found. Set {ENV_KEY} in the environment or in the {ENV_FILE} file."
        )
    return api_key


def fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=20) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"HTTP error {exc.code}: {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"URL error: {exc.reason}") from exc


def save_file(path: str, data: bytes) -> None:
    with open(path, "wb") as file:
        file.write(data)


def ensure_data_dir(path: Path = DATA_DIR) -> None:
    path.mkdir(parents=True, exist_ok=True)


def extract_zip(zip_path: Path, target_dir: Path = DATA_DIR) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(target_dir)


def is_zip_recent_enough(zip_path: str) -> bool:
    modified_date = datetime.fromtimestamp(os.path.getmtime(zip_path)).date()
    today = datetime.now().date()
    return modified_date == today or modified_date < today - timedelta(days=1)


def initialize_corpcode(output_name: str = DEFAULT_ZIP_NAME) -> None:
    ensure_data_dir()
    output_file = DATA_DIR / Path(output_name).name
    api_key = get_api_key()
    request_url = f"{DEFAULT_API_URL}?crtfc_key={api_key}"

    if os.path.exists(output_file) and is_zip_recent_enough(output_file):
        modified_date = datetime.fromtimestamp(os.path.getmtime(output_file)).date()
        print(
            f"Existing zip file was downloaded on {modified_date}. "
            "Skipping download and extracting existing zip."
        )
        print(f"Extracting existing zip into: {DATA_DIR}")
        extract_zip(output_file)
        print("Extraction complete.")
        return

    print(f"Downloading OpenDart corpCode.xml from: {request_url}")
    zip_data = fetch_bytes(request_url)
    save_file(output_file, zip_data)

    print(f"Saved zip response to: {output_file}")
    print(f"Extracting zip into: {DATA_DIR}")
    extract_zip(output_file)
    print("Extraction complete.")


def find_corp_code_by_query(query: str, xml_filename: str = "CORPCODE.xml") -> str | None:
    xml_path = DATA_DIR / xml_filename
    if not xml_path.exists():
        raise FileNotFoundError(f"CORPCODE 파일을 찾을 수 없습니다: {xml_path}")

    query = query.strip()
    if not query:
        return None

    search_by_stock = query.isdigit() and len(query) == 6
    normalized_query = query.lower()

    for event, element in ET.iterparse(str(xml_path), events=("end",)):
        if element.tag != "list":
            continue

        corp_code = element.findtext("corp_code")
        stock_code = element.findtext("stock_code")
        corp_name = element.findtext("corp_name")

        if search_by_stock:
            if stock_code == query:
                return corp_code
        else:
            if corp_name and corp_name.strip().lower() == normalized_query:
                return corp_code

        element.clear()

    return None


def find_corp_name_by_code(corp_code: str, xml_filename: str = "CORPCODE.xml") -> str | None:
    xml_path = DATA_DIR / xml_filename
    if not xml_path.exists():
        raise FileNotFoundError(f"CORPCODE 파일을 찾을 수 없습니다: {xml_path}")

    corp_code = corp_code.strip()
    if not corp_code:
        return None

    for event, element in ET.iterparse(str(xml_path), events=("end",)):
        if element.tag != "list":
            continue

        current_code = element.findtext("corp_code")
        if current_code == corp_code:
            corp_name = element.findtext("corp_name")
            element.clear()
            return corp_name.strip() if corp_name else None

        element.clear()

    return None
