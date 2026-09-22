# 주제별 말씀 모음

「주제별 말씀 모음.pdf」를 모바일에서 읽기 편하게 옮긴 정적 웹페이지입니다.

사이트: https://chris848484.github.io/scripture-collection/

## 열기

`index.html`을 브라우저에서 열면 됩니다. HTML 안에 스타일, 동작, 본문을 모두 담아 인터넷 연결 없이도 읽을 수 있습니다. 서버나 별도 패키지 설치가 필요하지 않습니다.

- 휴대폰과 PC에 맞춘 화면 구성
- 13개 주제 목차와 말씀별 직접 링크
- 글자 크기 조절 (사용 중인 브라우저에 저장)
- PDF의 본문, 절 번호와 순서 유지
- 키보드 탐색 및 인쇄용 화면 지원

## 본문 수정

`content.json`의 내용을 수정한 뒤 Python 3으로 다음 명령을 실행합니다.

```sh
python scripts/build_site.py
```

디자인과 읽기 동작은 `site.template.html`에 있습니다. `index.html`은 생성된 배포 파일입니다.

## GitHub Pages

저장소의 **Settings → Pages → Deploy from a branch → main → /(root)**를 선택합니다. `main`에 변경 내용을 올리면 무료 GitHub Pages 주소에 반영됩니다.

원본 PDF와 추출 점검용 임시 파일은 배포에 포함하지 않습니다.
