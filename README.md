# 동학(싱글)

동학은 DART(금융감독원 전자공시시스템) 공시에서 필요한 정보를 추출해서 AI에게 정확한 정보를 제공하기 위해 요약재무정보와 매출 정보를 추출해서 Markdown으로 만드는 기능을 수행합니다. 변환된 Markdown은 AI에게 입력하는 데이터로서 활용할 수 있습니다. 

## 요구사항

- Python 3.10 이상
- DART Open API 키

## 설치

### 1. 저장소 클론

```bash
git clone https://github.com/JeaMinLim/donghak_single.git
cd donghak_single
```

### 2. API 키 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 DART API 키를 추가하세요:

```
OPENDART_APIKEY=your_api_key_here
```

DART Open API 키는 [DART 홈페이지](https://opendart.fss.or.kr/)에서 발급받을 수 있습니다.

## 사용 방법

### 기본 사용

#### 1. 대화형 모드 (파라미터 없이 실행)

```bash
python -m donghak_single
```

실행하면 다음 정보를 입력받습니다:
- 회사명 또는 6자리 종목코드
- 검색 시작일 (YYYYMMDD 형식, 미입력 시 5년간의 기록)

#### 2. CLI 파라미터로 직접 실행

회사명/종목코드와 시작일을 파라미터로 전달:

```bash
python -m donghak_single 삼성전자 20260101
python -m donghak_single 005930 20260101
```

#### 3. 임시파일 정리

다운로드된 데이터와 생성된 Markdown 파일을 삭제:

```bash
python -m donghak_single 임시파일정리
```

이 명령은 다음 폴더를 삭제합니다:
- `data/` - 다운로드된 공시 데이터
- `markdown/` - 생성된 Markdown 파일

## 폴더 구조

```
donghak_single/
├── donghak_single/
│   ├── __init__.py
│   ├── __main__.py           # 패키지 진입점
│   ├── corp_code.py          # DART corpCode 관리
│   ├── corp_disclosure.py    # 공시 다운로드
│   ├── extract_xml.py        # XML 섹션 추출
│   └── convert_md.py         # XML→Markdown 변환
├── data/
│   ├── corpcode/             # 종목코드 데이터
│   ├── report/
│   │   ├── unzip/            # 압축 해제된 XML 파일
│   │   └── (ZIP 파일들)
│   └── tmp/                  # 임시 마크다운 파일
├── markdown/                 # 최종 합쳐진 마크다운 파일
├── requirements.txt          # 의존성 (모두 표준 라이브러리)
└── README.md
```

## 추출되는 섹션

다음 섹션이 자동으로 추출되어 Markdown으로 변환됩니다:

1. **요약재무정보** (`summary`) - 주요 재무 지표
2. **매출 및 수주상황** (`sales`) - 매출 및 수주 정보

섹션 정보는 `donghak_single/__main__.py`의 `SECTION_DEFINITIONS`에서 정의됩니다.

## 출력 파일

### Markdown 파일

최종 병합된 Markdown 파일:
- 경로: `markdown/<회사명>_<YYYYMMDD>.md`
- 구성:
  - 회사 기본 정보 (회사명, 종목코드)
  - 각 공시 항목별 요약재무정보 및 매출 정보

### 임시 파일

처리 중 생성되는 임시 파일:
- 경로: `data/tmp/<접수번호>_<섹션>.md`
- 최종 병합 후 유지됨

## 예시

```bash
# 삼성전자의 2026년 공시 검색 및 처리
python -m donghak_single 삼성전자 20260101

# 결과:
# - data/report/ 에 공시 ZIP 파일 다운로드
# - data/report/unzip/ 에 XML 파일 압축 해제
# - data/tmp/ 에 임시 마크다운 파일 생성
# - markdown/삼성전자_20260603.md 에 최종 파일 생성
```

## 의존성

모든 의존성이 Python 표준 라이브러리에 포함되어 있습니다:
- `xml.etree.ElementTree` - XML 파싱
- `urllib` - HTTP 요청
- `json` - JSON 처리
- `zipfile` - 압축 파일 처리
- 기타 표준 라이브러리

선택사항으로 `lxml`을 사용하려면:
```bash
pip install lxml
```

## API 오류 처리

일반적인 오류 메시지:

- `"검색 결과가 없습니다"` - 회사명/종목코드가 정확하지 않습니다
- `"API 오류"` - DART Open API에서 오류 응답
- `"날짜는 YYYYMMDD 형식의 8자리 숫자여야 합니다"` - 날짜 형식 오류

## 라이선스

MIT License

## 참고

- [OpenDART](https://opendart.fss.or.kr/)
