# 모아봄 · 춘천 청년 기회 통합 플랫폼 백엔드

춘천 청년이 교육·활동·채용·지원 정책을 찾기 위해 여러 기관의 홈페이지를 방문해야 하는 문제에서 출발했습니다. 흩어진 정보를 공통 모델로 제공하고, 직업 탐색과 지역 채용·주거 정보까지 연결하는 춘천시 공공데이터 해커톤 프로젝트입니다.

이 저장소는 **API·DB 설계를 포함해 단독으로 구현한 백엔드**를 설명합니다. **데이터 수집·정제는 팀원과 2인 공동 작업**으로 진행했습니다. 화면의 AI 로드맵·합격 팁·개인 메모는 프론트엔드 담당 기능입니다.

## 담당 역할과 결과

| 구분 | 담당 내용 |
| --- | --- |
| 백엔드 단독 구현 | FastAPI API, PostgreSQL 테이블 설계, 검색·필터·페이지네이션, 자체 회원가입·로그인, 행동 기반 추천, 주거 비교 집계 |
| 수집·정제 공동 작업 | 커리어넷·정책 페이지 수집, 직업·채용·주거 데이터 정규화, 원문 보존, 데이터 적재 연결 |
| 팀원 제공 결과 연동 | 소스가 현재 두 폴더에 없는 통합 공고 수집·taxonomy 분류 결과를 공통 스키마로 적재하고 API로 제공 |

2026-10-08에 기존 연결 설정으로 Supabase를 읽기 전용 조회한 결과입니다.

| 데이터 | 실제 DB 저장 | 확인한 로컬 결과물 |
| --- | ---: | --- |
| 통합 공고 `opportunities` | 1,386건 | 15개 출처·9개 분류·taxonomy 2.0, 고유 ID 1,386개 |
| 직업 `career_jobs` | 12건 | 커리어넷 수집·정제 12건, 재정제 결과 전체 일치 |
| 민간 채용 `job_postings` | 50건 | 경제포털 채용 정제 50건, 재정제 결과 전체 일치 |
| 주거 거래 `housing_transactions` | 6,830건 | 전체 정제 246,166건 중 춘천 5,630건 + 서울 표본 1,200건 적재 |

주거 DB의 ID 집합은 위 춘천·서울 표본 파일과 일치했습니다. 건수는 결과물과 저장 규모이며, 정보 탐색 시간 단축·청년 정착률 개선 같은 서비스 효과는 별도로 측정하지 않았습니다.

## 기술 스택

| 영역 | 기술 | 사용 목적 |
| --- | --- | --- |
| API | Python, FastAPI 0.140.0, Uvicorn 0.51.0 | REST API, 자동 OpenAPI/Swagger |
| 입력·설정 | Pydantic 2.13.4, pydantic-settings 2.14.2 | 요청 검증, 환경변수 로딩 |
| DB | Supabase PostgreSQL | 통합 공고·사용자·행동·도메인 데이터 저장 |
| DB 연결 | SQLAlchemy 2.0.51, Psycopg 3.3.4 | 커넥션·세션·트랜잭션 관리, 파라미터 바인딩 SQL |
| 비밀번호 | pwdlib, Argon2 | 비밀번호 해시와 검증 |
| 동적 수집 | Playwright 1.61.0, Chromium, BeautifulSoup 4.15.0 | 렌더링된 커리어넷 본문 파싱 |
| 정적 수집 | Requests 2.34.2, BeautifulSoup | 정책 페이지 본문 추출 |
| CSV 정제 | pandas 3.0.5 | 인코딩·헤더 대응, 금액·주소·날짜 변환 |

백엔드 버전은 [requirements.txt](requirements.txt), 데이터 도구 버전은 별도 `moabom-data` 환경에서 확인했습니다. 로컬 백엔드 Python은 3.14.4였습니다. 수집 도구는 이 백엔드 requirements에 포함되어 있지 않습니다.

## 시스템 연결 구조

```mermaid
flowchart LR
    WEB[모아봄 웹 화면] <-->|JSON REST API| API[FastAPI]
    API --> SESSION[SQLAlchemy Session]
    SESSION --> DRIVER[Psycopg]
    DRIVER <-->|Session pooler · PostgreSQL| DB[(Supabase PostgreSQL)]
    ENV[DATABASE_URL] --> SESSION
    SOURCES[기관·대학·민간 사이트 / 공공데이터 CSV] --> DATA[수집·정제 JSON / JSONL]
    DATA --> UPSERT[도메인별 ID 기반 upsert]
    UPSERT --> DB
```

Supabase의 PostgreSQL에 직접 연결합니다. `app/config.py`에서 `DATABASE_URL`을 로딩하고, `app/database.py`의 `pool_pre_ping=True`로 연결 상태를 점검합니다. API 요청마다 세션을 제공하고 요청 종료 시 닫습니다. 자체 `users` 테이블과 비밀번호 해시를 사용하며, SQL은 대부분 SQLAlchemy `text()`로 실행합니다.

## 데이터베이스 설계

첨부된 Supabase 화면처럼 컬럼·자료형·기본키·NULL 허용 여부를 표시했습니다. **실선은 실제 DB 외래키, 점선은 코드가 사용하는 식별 관계**입니다. 구조도는 실제 DB 메타데이터를 바탕으로 생성했습니다.

![통합 공고·사용자·행동·선호도 테이블 구조](docs/images/database-schema.png)

[확대 가능한 SVG](docs/images/database-schema.svg) · [직업·채용·주거 구조도](docs/images/domain-schema.png) · [DB 설계 상세](docs/database-design.md)

| 설계 | 구현과 목적 |
| --- | --- |
| 공통 컬럼 + JSONB | 제목·분류·상태·날짜는 검색 가능한 컬럼으로, 출처별 기관·대상·세부 정보·원문은 JSONB로 저장 |
| 공고와 행동 이력 | `user_activity_events.opportunity_id → opportunities.id` 외래키, 공고 삭제 시 이력 `ON DELETE CASCADE` |
| 사용자별 선호도 | `(user_id, category)` 복합 기본키로 사용자별 분류 집계 한 행 유지, upsert로 점수·횟수 누적 |
| 회원 이메일 | `UNIQUE(email)`과 `lower(email)` 고유 인덱스로 중복 방지 |
| 도메인 분리 | 직업·민간 채용·주거는 각각 전용 테이블과 API 사용, 세 테이블 사이에는 현재 외래키 없음 |
| 조회 인덱스 | 공고 `(category, status)`, 직업 학과 JSONB GIN, 주거 `(city, housing_type, contract_date)` 등 확인 |

`users.id`와 행동·선호도의 `user_id`는 코드에서 함께 사용하지만 DB 외래키는 선언되어 있지 않습니다. 추천은 사용자 선호도의 `category`와 공고 `category`를 JOIN합니다. 인덱스는 실제 존재 여부를 확인했으며, 성능 향상 폭은 측정하지 않았습니다.

## 수집·정제에서 API까지

수집·정제 소스는 형제 폴더 `moabom-data`에 있습니다. 아래는 해당 코드와 저장 파일로 확인한 공동 작업 범위이며, 상세 파일·변환 예시는 [데이터 파이프라인 검토](docs/data-pipeline-review.md)에 정리했습니다.

| 파이프라인 | 처리 방식 | 결과 |
| --- | --- | --- |
| 커리어넷 직업 | Playwright 렌더링 → BeautifulSoup 섹션 추출 → 학과·자격·능력 배열화 → JSONB upsert | 직업 12건, 관련 자격증 있는 직업 8건 |
| 경제포털 채용 | 원본 JSON → 직무/직업코드 분리 → 급여 최솟값·최댓값/종류, 고용형태, KST 날짜 정규화 | 50건, 정규직 30·기간제 20건 |
| 국토부 전월세 CSV | 인코딩·헤더 탐색 → 만원에서 원으로 통일 → 계약년월+일 복원 → 지역 분리·ID 생성 | 춘천 5,630·서울 240,536건 정제 |
| 서울 비교 표본 | 거래유형·면적·보증금·월세 구간에 따라 고정 seed로 유형별 300건 추출 | 서울 1,200건을 춘천 데이터와 함께 적재 |
| 정책 페이지 | Requests → 본문 선택자·대체 선택자 → 원문 저장 | 3건, 제목 추출은 후속 검수 필요 |

주거 CSV는 공개시스템에서 내려받은 파일을 입력으로 사용합니다. 정책 원문 3건과 통합 공고의 온통청년 정책 405건은 별도 결과물입니다.

직업은 `관련학과` 본문을 `related_majors` 배열로 만들어 JSONB 포함 검색에 사용합니다. 주거는 CSV의 `계약년월`·`계약일`을 `date`로 복원해 기간별 조회에 사용하고, 보증금·월세를 원 단위 정수로 통일해 SQL 평균·중앙값 비교에 연결합니다. 원문은 `raw_fields` 또는 `raw_data`에 보존했습니다.

통합 공고는 대학 공지·링커리어·위비티·청년정책·나라장터 등 15개 출처 결과를 9개 분류로 제공합니다. 현재 폴더에 없는 수집·taxonomy 변환 프로그램의 세부 구현은 팀원 제공 결과로 구분합니다. 저장 JSON에서 분류 근거와 신뢰도를 확인하고, 백엔드 importer에서 구형·v2 분류를 처리합니다.

`scripts/import_json.py`는 `ON CONFLICT(id) DO UPDATE`로 재적재하며 전체 처리를 트랜잭션으로 감쌉니다. 검토 중 기존 ID의 `category_name`, `taxonomy_version`, `subcategories`가 갱신되지 않는 문제를 수정하고 PostgreSQL upsert SQL을 검사하는 회귀 테스트를 추가했습니다.

## API와 추천 로직

업무 API 12개를 제공하며 목록 응답은 `items`, `pagination`, `filters`로 구성됩니다. 상세 경로의 `{id}`는 각 API의 리소스 ID입니다.

| 메서드 | 경로 | 기능 |
| --- | --- | --- |
| GET | `/api/opportunities`, `/api/opportunities/{id}` | 분류·상태·키워드 검색, 목록·상세 |
| POST | `/api/auth/signup`, `/api/auth/login` | 이메일 중복 확인, 비밀번호 해시·검증 |
| POST | `/api/user-events` | 행동 이력 저장·선호도 누적 |
| GET | `/api/recommendations` | 선호도·지역 점수 기반 추천 |
| GET | `/api/career-jobs`, `/api/career-jobs/{id}` | 직업명·설명 검색, 학과 필터, 상세 |
| GET | `/api/job-postings`, `/api/job-postings/{id}` | 채용 검색, 고용형태·모집중 필터, 상세 |
| GET | `/api/housing/transactions`, `/api/housing/compare` | 지역·주택유형·면적 필터, 지역 비교 |

추가로 `/`, `/health`, `/health/db`를 제공합니다. SQL 입력은 파라미터로 바인딩하고 페이지 크기를 제한합니다. 주거 비교에는 PostgreSQL `AVG`, `FILTER`, `PERCENTILE_CONT(0.5)`를 사용합니다.

추천은 규칙 기반으로 `사용자별 분류 선호 점수 + 지역 점수`를 계산합니다.

| 행동 | VIEW 조회 | CLICK 원문 클릭 | BOOKMARK 북마크 | APPLY 지원 |
| --- | ---: | ---: | ---: | ---: |
| 선호도 증가 | 1 | 3 | 5 | 8 |

행동 INSERT와 선호도 upsert를 한 트랜잭션에서 처리합니다. 공모전·해커톤은 전국/온라인 10·춘천 7·강원 5·기타 2점, 다른 분류는 춘천 10·강원 6·전국/온라인 3·기타 0점을 부여합니다. 선호 이력이 없으면 0점에서 지역 점수로 추천하며, `CLOSED` 공고는 제외합니다.

## 실행과 확인

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env의 DATABASE_URL을 본인의 DB 연결 정보로 작성
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs` · DB 확인: `http://127.0.0.1:8000/health/db`

`DATABASE_URL`은 Supabase Dashboard **Connect → Session pooler**의 값을 사용합니다. 이 백엔드는 DB 비밀번호로 접속하므로 프론트엔드용 Supabase URL·API 키 설치 예제를 적용할 필요는 없습니다. 현재 저장소에는 테이블을 생성하는 migration이 없어 기존 스키마가 준비된 DB가 필요합니다. `.env`는 Git에서 제외됩니다.

```bash
# 로컬 JSON 감사 · DB 접속 없음
python3 scripts/audit_data.py --as-of 2026-10-08

# importer 회귀 검사 · DB 접속 없음
DATABASE_URL=postgresql+psycopg://offline:offline@localhost/offline .venv/bin/python -m unittest discover -s tests -v

# 저장한 메타데이터에서 구조도 SVG 다시 생성
python3 scripts/render_schema_diagram.py
python3 scripts/render_schema_diagram.py --input docs/domain-schema-snapshot.json --output docs/images/domain-schema.svg
```

검증한 범위는 전체 코드 검토, 공고 1,386건 normalize, 회귀 테스트 3개, 직업·채용 정제 재현, 춘천 주거 정제 재현, 실제 DB 구조·건수 조회입니다. 읽기 전용 세션에서 목록·상세·추천·주거 비교 GET 라우터 함수를 실행했습니다. HTTP 종단 간 시험·POST 요청·재적재·부하 측정은 이번 검토에서 수행하지 않았습니다.

## 현재 한계와 후속 과제

- 로그인은 비밀번호 확인과 사용자 정보 반환까지 구현했습니다. 이후 요청을 검증하는 토큰·세션과 사용자별 권한 처리가 필요합니다.
- 공고 상태는 수집 당시 값입니다. 로컬 `OPEN` 278건 중 240건은 검토일 전에 마감되어 자동 갱신·날짜 경계 정책이 필요합니다.
- 주거의 서울 표본은 가격 변수까지 매칭하므로 지역 가격 차이를 대표하는 무작위 표본으로 해석할 수 없습니다. 서울 연립·다세대 표본은 재현 결과가 저장 파일과 달랐습니다.
- DB migration, 수집·정제 소스 공개 링크, 빠진 수집 도구 의존성, 자동 수집·재시도·운영 지표를 보완할 수 있습니다.

설계·기여 검토: [백엔드 검토안](docs/backend-portfolio-review.md) · 데이터 품질: [공고 감사](docs/data-audit.json), [파이프라인 감사](docs/data-pipeline-audit.json), [표본 재현 검사](docs/sampling-audit.json) · 실제 DB 확인: [스키마 메타데이터](docs/database-schema.json), [읽기 검증 결과](docs/live-read-validation.json)
