# 변환 스크립트

- `build_site.py`: content.json과 site.template.html을 합쳐 단일 index.html을 만듭니다. Python 3 표준 라이브러리만 사용합니다.
- `extract_pdf.py`: 원본 PDF에서 본문을 추출하고 절 번호와 문자 보존을 검증합니다. pdfplumber가 필요합니다.

저장소 최상위 폴더에서 `python scripts/build_site.py`를 실행하세요.
