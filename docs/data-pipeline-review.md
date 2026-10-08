# 모아봄 수집·정제 파이프라인 검토안

> `moabom-data`의 Python 11개와 JSON·CSV 결과물을 검토했습니다. 이 폴더는 백엔드와 같은 부모 폴더에 있는 별도 로컬 자료이며, 이 Git 저장소에는 소스가 포함되어 있지 않습니다.
> 수집·정제는 사용자와 팀원의 2인 공동 작업입니다. 전체 공고의 수집·분류 코드 중 두 폴더에 없는 부분은 사용자의 설명에 따라 팀원이 제공한 결과물로 구분합니다.
> 새로운 웹 크롤링이나 운영 DB 적재 없이 기존 파일과 코드로 확인했습니다.

## 1. 파이프라인 연결도

```mermaid
flowchart LR
    URL[커리어넷 URL 목록 12개] --> CR[crawl_careernet_jobs.py]
    CR --> CAREER[직업 원문 JSON 12건]
    CAREER --> CC[clean_career_jobs.py]
    CC --> CI[import_career_jobs.py]
    CI --> CT[(career_jobs)]
    CT --> CA[직업 탐색 API]

    JOBRAW[경제포털 채용 JSON 50건] --> JC[clean_jobs.py]
    JC --> JI[import_job_postings.py]
    JI --> JT[(job_postings)]
    JT --> JA[채용 탐색 API]

    CSV[국토부 다운로드 CSV 8개] --> CONV[csvTrans.py]
    CONV --> HR[주거 원문 JSON]
    HR --> HC[clean_housing.py]
    HC --> SAMPLE[서울 매칭 표본 생성]
    HC --> HI[import_housing_transactions.py]
    SAMPLE --> HI
    HI --> HT[(housing_transactions)]
    HT --> HA[거래 조회·지역 비교 API]

    POLICY[정책 페이지 URL 3개] --> PC[crawl_policy_pages.py]
    PC --> PR[정책 원문 JSON 3건]
    PR -. 정제·DB 적재 코드 미확인 .-> NEXT[후속 통합]
```

마지막 정책 원문 3건과 백엔드의 온통청년 정책 405건은 서로 다른 결과물입니다. 또한 직업·채용·주거 결과를 같은 `opportunities` 테이블에 적재하지 않고 도메인별 테이블에 적재합니다. 실제 어떤 파일이 서비스 DB에 적재되었는지는 DB 접속 복구 후 확인해야 합니다.

## 2. 직업 수집: 동적 페이지 → 원문 보존 → 검색용 정제

`crawl_careernet_jobs.py`는 `data-career/reference/careernet_job_urls.json`의 이름·URL을 읽고 커리어넷 도메인과 `seq` 값을 검증합니다. ID는 `CAREER:CAREERNET:<seq>` 형태입니다.

Playwright Chromium으로 페이지를 열어 DOM을 확보하고, BeautifulSoup으로 script·style·nav·header·footer 등을 제거합니다. 텍스트에서 ‘하는일’, ‘핵심능력’, ‘관련학과’, ‘관련자격’, ‘적성 및 흥미’ 같은 표식 사이를 추출합니다. 반복 문장·쉼표 목록을 정리하고 표준직업·고용직업 코드를 추출하며, 원문과 수집시각·출처·검수상태를 함께 저장합니다.

현재 `headless=False`, 페이지 대기 1.8초, 건별 대기 0.8초가 설정되어 있습니다. 건별 실패는 출력하고 다음 URL로 진행합니다. 자동 재시도나 스케줄은 없고, 결과는 마지막에 파일로 저장합니다.

`clean_career_jobs.py`는 원문에서 학과·자격을 다시 추출하여 앞 단계의 섹션 구분을 보완하고, 학과를 정규식으로 배열화합니다. 중첩된 schema 1.1을 API에서 사용하기 쉬운 schema 2.0으로 정리합니다.

| 확인 결과 | 값 |
| --- | ---: |
| URL 목록 / 수집 결과 / 정제 결과 | 각각 12건 |
| 정제 결과 고유 ID | 12개 |
| 설명·관련 학과·핵심 능력·적성·흥미가 있는 직업 | 각 12건 |
| 관련 자격증이 있는 직업 | 8건 |
| 코드로 재정제한 결과와 저장 JSON의 일치 | 12건 전체 일치 |

정제 사례: ‘인공지능전문가’의 원문에서 컴퓨터공학과·전자공학과·응용소프트웨어공학과·수학과·통계학과를 `related_majors` 배열로, 수리·논리력·공간지각력을 `core_abilities` 배열로 추출했습니다. 데이터에는 직업 개요가 있으나 원본의 소득·전망·만족도 등 추가 탭 필드는 비어 있습니다.

`import_career_jobs.py`가 직업 배열을 JSONB로 캐스팅하여 upsert하고, `/api/career-jobs`의 학과 검색은 `related_majors @> CAST(:major_json AS jsonb)`를 사용합니다. 즉 화면에서 선택할 수 있는 직업 탐색의 기초 데이터를 확보한 사례로 설명할 수 있습니다. 이 데이터만으로 AI 로드맵이 구현됐다고 표현할 근거는 없습니다.

## 3. 민간 채용 정제: 문자열 → 비교·검색 가능한 필드

`data-jobs/jobs_chuncheon_economy.json` 50건이 입력이며, 이를 생성한 채용 수집 프로그램은 이 폴더에서 확인되지 않았습니다.

`clean_jobs.py`는 직무명 끝의 괄호 안 직업코드를 분리하고, 급여 문자열에서 최솟값·최댓값을 추출합니다. 시급/일급/월급/연봉을 enum으로, 고용형태를 PERMANENT/FIXED_TERM/DAILY/OTHER로 정규화합니다. 등록일 `26-07-31`과 같은 표기는 KST ISO 날짜로 바꿉니다.

| 결과 | 건수 |
| --- | ---: |
| 입력 → 정제 결과 | 50 → 50 |
| 고유 ID | 50 |
| 고용형태 PERMANENT / FIXED_TERM | 30 / 20 |
| 급여 HOURLY / MONTHLY / YEARLY | 7 / 35 / 8 |
| 급여 최솟값 누락 / 원문 URL 누락 | 0 / 0 |
| 코드 재실행과 저장 JSON | 전체 일치 |

실제 저장 결과의 변환 예시는 다음과 같습니다.

```json
{
  "job_name": "승용차 운전원(자가용 운전원)",
  "job_code": "622901",
  "employment_type": "FIXED_TERM",
  "salary": {
    "type": "HOURLY",
    "minimum": 10320,
    "maximum": 10320,
    "display": "시급10,320원 이상 ~ 10,320원 이하"
  },
  "registration_at": "2026-07-31T00:00:00+09:00"
}
```

`import_job_postings.py`는 salary와 source를 DB 컬럼으로 펼쳐 저장하고 정제 레코드를 `raw_data` JSONB에도 보존합니다. API는 고용형태 필터·급여 표시·실제 마감일 기준 모집중 필터에 이 컬럼을 사용합니다.

급여 파싱은 일반 문자열에서 처음 두 숫자를 선택하는 방식입니다. ‘만원’ 표기나 급여 외 숫자가 섞이는 경우를 위한 검증은 추가할 수 있습니다. 현재 저장된 50건의 형식을 확인한 결과이며 모든 채용 사이트 형식을 처리한다고 주장할 수는 없습니다.

## 4. 주거 정제: 파일 형식·단위·날짜·식별자 통일

`csvTrans.py`는 국토교통부 실거래가 공개시스템에서 내려받은 CSV를 입력받습니다. 크롤러가 직접 CSV를 다운로드하는 구현은 없습니다.

변환 단계는 CP949, EUC-KR, UTF-8, UTF-16 계열 인코딩을 시도하고, 헤더 단어가 3개 이상 있는 행을 찾아 안내문을 건너뜁니다. pandas에서 구분자를 추정하고 컬럼명 공백·줄바꿈을 제거합니다. 여러 후보 컬럼명을 하나의 표준 필드에 대응시키고, 쉼표·단위가 있는 금액과 면적을 숫자로 변환합니다. **보증금·월세를 만원에서 원으로 변환**하여 서비스 DB 단위를 통일합니다.

`clean_housing.py`는 `raw_fields.계약년월`과 `계약일`을 조합해 실제 계약일을 복원하고, 주소를 province/city/legal_dong 등으로 나눕니다. 전세·월세를 JEONSE/MONTHLY_RENT로 분류하고, 주택 정보·금액·계약일·원본 NO 등을 SHA-256 입력으로 사용해 ID를 재생성합니다. 생성 ID 중복은 집합으로 검사하며 JSON 또는 JSONL로 출력합니다.

JSONL 출력 옵션은 있지만 정제 입력은 `json.loads()`로 전체 파일을 메모리에 올립니다. DB 적재기는 JSONL을 줄 단위로 읽어 기본 500건씩 실행하므로 두 단계의 메모리 처리 방식은 다릅니다.

| 주택유형 | 춘천 정제 | 서울 정제 | 서울 저장 표본 |
| --- | ---: | ---: | ---: |
| 아파트 APARTMENT | 1,981 | 68,848 | 300 |
| 단독·다가구 DETACHED_MULTI | 3,189 | 74,799 | 300 |
| 오피스텔 OFFICETEL | 333 | 39,971 | 300 |
| 연립·다세대 ROW_HOUSE | 127 | 56,918 | 300 |
| **합계** | **5,630** | **240,536** | **1,200** |

8개 원본 JSON의 계약일 필드는 전부 비어 있었지만 정제 파일의 계약일 누락은 0건입니다. 정제 파일별 ID 중복도 0건입니다. 이는 저장 데이터의 식별자 유일성이며, 동일한 실거래가 재수집됐을 때까지 의미적으로 중복 제거된다는 보장은 아닙니다. ID에 원본 NO가 포함되어 있어 원본 행 순서가 달라지는 상황도 검토해야 합니다.

춘천 4개 유형 5,630건은 raw JSON에서 정제 함수를 재실행한 결과와 저장된 정제 결과가 정확히 같았습니다. 서울도 저장 파일의 건수·지역·ID·날짜를 확인했으며, 전체 재정제 비교는 수행하지 않았습니다. [파일별 감사 결과](data-pipeline-audit.json)에서 원본과 정제 건수를 확인할 수 있습니다.

별도의 `seoul_housing_sample_500.json`도 있지만 이는 다른 표본 파일이며 위 1,200건에 더해 전체 고유 데이터를 늘리는 것으로 계산하지 않았습니다.

### 발견한 원본 파일명 오류

`housing_transactions_row_house_chuncheon.json`은 실제로 서울 56,918건이며, `housing_transactions_row_house_seoul.json`은 춘천 127건입니다. 대응 CSV 파일명도 확인이 필요합니다. 정제 결과 파일에서는 서울/춘천이 내용에 맞게 구분되어 있습니다.

이번 검토의 춘천 row_house 재현은 이름이 아닌 내용에 따라 `housing_transactions_row_house_seoul.json`을 입력으로 사용했습니다. 원본을 수정하지 않았으며, 이후 작업에서 파일명·manifest·지역 검증을 함께 고치는 것이 좋습니다.

## 5. 서울 비교 표본 생성과 해석

`create_seoul_matched_samples.py`는 춘천의 분포에 따라 서울에서 주택유형별 기본 300건을 뽑습니다. 층화 기준은 거래유형·면적구간·보증금구간·월세구간입니다. 비례 배분한 정수 표본수에 잔여분을 할당하고, 고정된 random seed로 추출하며 ID 중복을 제외합니다.

동일 그룹이 부족하면 거래유형·면적·보증금·월세 일치 여부의 우선순위로 다른 그룹을 찾습니다. 실제 구간 간 수치 거리를 계산하는 방식은 아닙니다. 별도 `create_chuncheon_row_house_sample.py`는 춘천 여부를 확인하고 동일 층화 기준으로 가능한 수만큼 표본을 뽑지만, 이 스크립트의 기본 출력 파일은 현재 폴더에서 발견하지 못했습니다.

저장 서울 표본 4개를 기본 seed와 현재 정제 파일로 다시 생성해 비교했습니다.

| 유형 | 재현 표본수 | 저장 결과와 정확한 일치 |
| --- | ---: | --- |
| 아파트 | 300 | 일치 |
| 단독·다가구 | 300 | 일치 |
| 오피스텔 | 300 | 일치 |
| 연립·다세대 | 300 | 불일치 |

[표본 재현 감사 결과](sampling-audit.json)에 사용한 seed를 기록했습니다. 연립·다세대는 과거 입력·설정·실행 버전이 달랐는지 추가 확인해야 합니다.

주거 가격 차이를 비교하려는 경우 **보증금과 월세 자체를 매칭 조건으로 사용하면 가격 차이가 인위적으로 작아질 수 있습니다.** 면적·주택유형·거래유형·계약 기간 등의 조건을 맞추고 가격을 결과로 비교하는 정책을 별도로 검토하는 것이 좋습니다. 지금 결과물은 구현된 표본 생성 방식의 증거이며, 편향 없는 전체 시장 가격 비교의 증거는 아닙니다.

`housing.py`의 `/compare`는 이러한 표본을 직접 생성하지 않고 DB에 저장된 거래를 조건별로 묶어 평균·중앙값을 계산합니다. 실제 적재 파일, 표본 여부와 거래기간을 응답이나 문서에 표시하면 해석이 더 분명해집니다.

## 6. 정책 원문 수집과 남은 작업

`crawl_policy_pages.py`는 공식 정책 URL 3개에 Requests Session으로 접근해 HTTP 상태를 검사합니다. 제목은 h1/h2/h3/OG/title 순으로 찾고, 본문은 article·board-view·content·main 등 여러 선택자를 시도한 뒤 body로 대체합니다. 본문 공백을 정리하고 URL 해시 ID, 출처, 수집시각, 검수상태를 보존합니다. 요청 timeout은 30초, 건별 간격은 1초입니다.

결과는 복지포털·춘천시청·강원특별자치도 각 1건으로 총 3건이며, 전부 REVIEW_REQUIRED입니다. 추출된 제목은 ‘복지’, ‘퀵 메뉴’, ‘전자민원’으로 정책 제목보다 사이트 공통 영역을 잡은 경우가 있습니다. 출처별 본문·제목 선택자를 좁히고 메뉴 텍스트를 제외하는 정제가 필요합니다.

이 3건을 표준 정책 스키마나 opportunities로 변환·적재하는 코드가 없어, 수집된 원문 단계로 설명하는 것이 정확합니다.

## 7. 전체 통합 공고와의 연결 범위

백엔드 `data/moabom_opportunities_v2.json`은 15개 출처 1,386건이며, 원문 `raw_fields`, 세부 `details`, 분류 근거 `details.taxonomy`, 수집시각을 보존합니다. 다음 형태를 적재 스크립트가 DB 컬럼으로 변환합니다.

```json
{
  "id": "BAEWOBOHM:11603",
  "title": "스마트폰으로 찍는 사진반",
  "category": {"code": "EDUCATION", "name": "교육·강좌"},
  "taxonomy_version": "2.0",
  "subcategories": [],
  "status": "OPEN",
  "organization": {"name": "춘천시 평생학습관", "department": null},
  "dates": {"recruit_end_at": "2026-07-31T23:59:59+09:00"},
  "location": {"region": "춘천시", "address": null, "operation_type": "OFFLINE"},
  "source": "춘천시 평생학습 통합플랫폼 배워봄"
}
```

이는 실제 저장 레코드의 일부 필드를 발췌한 예시이며, 상태 OPEN은 수집 당시의 값입니다.

대학 공지·링커리어·위비티·나라장터·보조금24·온통청년 등의 수집과 공고 taxonomy 2.0 변환 스크립트는 검토한 폴더에 없습니다. 사용자 확인에 따라 해당 결과물은 팀원이 제공한 작업으로 구분했습니다. JSON의 raw_fields나 분류 이유로 데이터의 형태는 설명할 수 있으나, 크롤링 도구·재시도·중복제거·지역제한 판정 알고리즘까지 구현된 것으로 확정할 수는 없습니다.

## 8. 포트폴리오에 쓸 수 있는 설명과 보완 항목

설명 가능한 기술적 기여는 동적·정적 페이지 수집, 원문 보존, 도메인별 schema 2.0 정제, 숫자·날짜·단위 통일, ID 재생성, 고정 seed 표본 생성, JSONB upsert와 API의 연결입니다. 개인 기여는 API·DB·백엔드 단독 구현과 수집·정제 공동 작업으로 표시합니다.

후속 보완 항목은 수집 라이브러리가 빠진 requirements, 데이터 폴더 Git 관리, 입력·출력·설정·코드 버전을 기록하는 manifest, 원본 파일명과 지역 검증, 정책 제목 선택자, 주거 표본 편향과 재현 불일치, 날짜·누락 필드 검사, 자동 갱신·재시도·실패 기록입니다.

세 도메인 importer는 `engine.begin()` 안에서 SQL 오류를 잡고 다음 건으로 진행할 수 있습니다. PostgreSQL에서는 실패한 트랜잭션을 rollback/savepoint로 복구하지 않으면 뒤의 SQL도 실패하므로, 건별 또는 배치별 실패 격리와 최종 commit 성공 기준의 건수 보고가 필요합니다.

### 로컬 재현 명령 예시

다음 명령은 `moabom-data`에서 실행하는 예시이며, 이번 검토에서는 기존 함수와 파일을 읽어 비교했습니다. 원본 파일을 덮어쓰지 않도록 출력 경로를 별도로 지정하는 것이 좋습니다.

```bash
python clean_career_jobs.py data-career/career_jobs.json -o /tmp/career_jobs_review.json
python clean_jobs.py data-jobs/jobs_chuncheon_economy.json -o /tmp/jobs_review.json
python clean_housing.py data-house/raw/housing_transactions_apartment_chuncheon.json -o /tmp/housing_review.json
```

백엔드 통합 공고 집계는 이 저장소에서 재현할 수 있습니다.

```bash
python3 scripts/audit_data.py --as-of 2026-10-08
DATABASE_URL=postgresql+psycopg://offline:offline@localhost/offline .venv/bin/python -m unittest discover -s tests -v
```

위 명령은 운영 DB에 연결·적재하지 않습니다. DB 연결을 복구하면 먼저 읽기 전용 schema 확인을 수행하고, 적재 대상·스키마·날짜 정책을 검토한 뒤 수집 파이프라인 운영을 정리하면 됩니다.
