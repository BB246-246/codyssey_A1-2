# 국내 여행지 추천 프로그램

여행 날짜를 입력하면 LLM이 그 시기에 어울리는 국내 여행지를 추천하고,
지도 API로 해당 지역 맛집을 검색해 최종 여행 리포트(Markdown)를 만들어주는 CLI 프로그램입니다.

## 동작 흐름

```
--date 입력
   ↓
[1/3] Gemini API  → 추천 도시 / 날씨 / 행사 / 추천 이유를 JSON으로 생성
   ↓
[2/3] Kakao Local API → 추천 도시의 맛집 5곳 검색
   ↓
[3/3] Gemini API  → 위 두 결과를 합쳐 최종 여행 리포트(Markdown) 생성
   ↓
results/ 폴더에 원본 JSON + 리포트 저장
```

사용 API
- LLM: Google Gemini (`google-generativeai`)
- 지도/장소 검색: Kakao Local — 키워드 검색

## API 호출 방식 (GET / POST)

### 두 메서드의 차이

| | GET | POST |
|---|---|---|
| 목적 | 조회 (서버 데이터를 읽기만 함) | 생성·처리 요청 |
| 데이터를 싣는 곳 | URL 뒤 쿼리스트링 `?query=...` | 요청 본문(body) |
| 길이 제한 | 있음 (실질 2000자 내외) | 사실상 없음 |
| 같은 요청 반복 | 항상 같은 결과 (캐시 가능) | 결과가 매번 달라질 수 있음 |

이 프로그램에서는 메서드를 고를 여지가 없습니다. Kakao Local 키워드 검색은 GET만,
Gemini `generateContent`는 POST만 허용하기 때문에 각 API의 규격을 그대로 따릅니다.

### Kakao Local — GET

이미 존재하는 장소 데이터를 **읽기만** 하고, 검색 조건이 짧아 URL에 다 담기므로 GET입니다.

```
GET https://dapi.kakao.com/v2/local/search/keyword.json?query=광양+맛집&size=5
Header: Authorization: KakaoAK {REST_API_KEY}
```

`requests.get(url, headers=..., params=...)`에 `params` 딕셔너리를 넘기면
`?query=...&size=5` 형태로 URL에 자동으로 붙습니다.
인증키는 URL이 아니라 **헤더**에 넣는데, URL은 서버 접근 로그에 그대로 남기 때문입니다.

응답 JSON의 `documents` 배열에서 장소 5건의 이름·주소·카테고리·URL·좌표를 꺼내 씁니다.

### Gemini — POST

`model.generate_content(prompt)` 한 줄이지만, SDK 내부에서는 아래 요청이 나갑니다.

```
POST https://generativelanguage.googleapis.com/v1beta/models/{모델}:generateContent
Body: {"contents": [{"parts": [{"text": "<프롬프트 전문>"}]}]}
```

POST여야 하는 이유는 세 가지입니다.

1. **길이** — 2차 리포트 프롬프트에는 맛집 목록 JSON이 통째로 들어가 수천 자가 됩니다. URL에 담을 수 없습니다.
2. **결과가 매번 다름** — 같은 프롬프트도 호출할 때마다 다른 답이 나오고, 호출마다 토큰이 과금됩니다. "반복해도 같은 결과"라는 GET의 전제와 맞지 않습니다.
3. **캐시 방지** — GET이면 중간 프록시가 응답을 캐시해 예전 답을 돌려줄 수 있습니다.

응답 객체에서 본문 텍스트만 `.text`로 꺼내 사용합니다.

## 지도 제공자 교체하기

Kakao에 의존하는 코드는 `search_restaurants()` 함수와 `.env`의 키 이름뿐입니다.
이 함수가 응답을 아래 6개 키로 정규화해서 돌려주기 때문에,
리포트 생성과 결과 저장은 어느 제공자를 쓰는지 알지 못합니다.

```python
{"name": ..., "address": ..., "category": ..., "url": ..., "x": ..., "y": ...}
```

따라서 제공자를 바꿀 때는 이 함수 내부의 4가지만 교체하면 되고, 나머지 코드는 그대로 둡니다.
엔드포인트 / 인증 헤더 / 검색 파라미터 이름 / 응답 필드 매핑입니다.

| | Kakao Local (현재) | 네이버 지역 검색 | Google Places |
|---|---|---|---|
| 메서드 | GET | GET | **POST** (검색어를 본문에 담음) |
| 인증 헤더 | `Authorization: KakaoAK {키}` | `X-Naver-Client-Id` + `X-Naver-Client-Secret` (키 2개) | `X-Goog-Api-Key` + `X-Goog-FieldMask` |
| 개수 파라미터 | `size` | `display` | `maxResultCount` |
| 결과 배열 | `documents` | `items` | `places` |
| 이름 필드 | `place_name` | `title` (HTML 태그 `<b>` 제거 필요) | `displayName.text` (중첩) |
| 주소 필드 | `road_address_name` | `roadAddress` | `formattedAddress` |
| 좌표 | `x`, `y` | `mapx`, `mapy` (단위 다름, 문서 확인) | `location.latitude/longitude` |

`try/except`로 감싸고 `raise_for_status()`로 상태 코드를 확인한 뒤
실패 시 빈 리스트를 돌려주는 구조는 제공자와 무관하게 그대로 재사용합니다.

## 실행 방법

### 1. 가상환경 준비

```bash
python -m venv venv
source venv/Scripts/activate     # Windows(Git Bash)
# .\venv\Scripts\Activate.ps1    # Windows(PowerShell)
# source venv/bin/activate       # macOS / Linux
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. API 키 설정 (아래 "API 키 설정 방법" 참고)

### 4. 실행

```bash
python main.py --date "2026-03-15"
```

실행 예시:

```
[1/3] 1차 추천 생성 완료 - recommended_city: 광양
[2/3] 맛집 검색 완료 - 5곳
[3/3] 최종 리포트 생성 완료

완료! results/2026-03-15_travel_plan.md 를 확인하세요.
```

## API 키 설정 방법

프로젝트 루트에 `.env` 파일을 만들고 아래 두 줄을 작성합니다.
(값 부분에는 본인이 발급받은 키를 넣으며, **공유 및 커밋 금지**)

```
GEMINI_API_KEY=발급받은_키
KAKAO_REST_API_KEY=발급받은_키
```

`.env` 대신 환경변수로 설정해도 동작합니다.

```bash
export GEMINI_API_KEY="YOUR_KEY"        # macOS / Linux
$env:GEMINI_API_KEY="YOUR_KEY"          # Windows PowerShell
```

### 키 발급처

| 키 | 발급처 | 비고 |
|---|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey | 무료 티어 제공 |
| `KAKAO_REST_API_KEY` | https://developers.kakao.com | 내 애플리케이션 → 앱 키 → **REST API 키** |

Kakao는 키 발급 후 **애플리케이션 설정에서 "카카오맵" 제품을 활성화**해야 로컬 검색 API를 사용할 수 있습니다.
활성화하지 않으면 `403 NotAuthorizedError (disabled OPEN_MAP_AND_LOCAL service)` 가 반환됩니다.

## 결과물 확인 방법

실행하면 `results/` 폴더에 두 개의 파일이 생성됩니다.

| 파일 | 내용 |
|---|---|
| `results/{날짜}_raw.json` | 1차 추천 JSON + 맛집 검색 결과 + 오류 목록(`errors`) |
| `results/{날짜}_travel_plan.md` | 최종 여행 리포트 (추천 지역/이유, 날씨, 행사, 맛집, 1일 일정, 오류 요약) |

## 오류 처리 정책

| 상황 | 동작 |
|---|---|
| API 키 미설정 | 안내 메시지 출력 후 즉시 종료 |
| 날짜 형식 오류 | 사용법(usage) 출력 후 종료 |
| LLM JSON 파싱 실패 | **1회만** 재요청, 그래도 실패하면 빈 값으로 계속 진행 |
| 1차 추천 필드 누락 / 빈 값 | `MISSING_FIELD`로 기록하고 기본값으로 대체 후 계속 진행 |
| 1차 추천 필드 타입 불일치 | `TYPE_ERROR`로 기록하고 기본값으로 대체 후 계속 진행 |
| 도시명 형식 이탈 | `FORMAT_WARNING`으로 기록하고 정규화한 값으로 교체 후 계속 진행 |
| 지도 API 실패 (401/403/네트워크) | 맛집을 "데이터 없음"으로 처리하고 리포트 생성은 계속 진행 |
| 검색 결과 0건 | 중단하지 않고 "데이터 없음"으로 리포트에 표기 |

### 1차 추천 결과 검증

파싱에 성공해도 LLM이 일부 필드를 빠뜨리거나 다른 타입으로 돌려줄 수 있으므로,
맛집 검색으로 넘어가기 전에 아래 4개 필드를 검사합니다.

| 필드 | 기대 타입 | 기본값 |
|---|---|---|
| `recommended_city` | 문자열 | `""` |
| `weather` | 문자열 | `""` |
| `events` | 리스트 | `[]` |
| `reason` | 문자열 | `""` |

검사 후 값을 기본값으로 정규화하기 때문에, 이후 단계는 항상 예측 가능한 타입을 받습니다.
(`recommended_city`가 비면 맛집 검색은 `SKIPPED`로 기록되고 리포트 생성은 계속됩니다.)

### 도시명 정규화

`recommended_city`는 그대로 지도 검색어(`{도시} 맛집`)가 되므로 형식이 어긋나면 검색 결과가 나빠집니다.
그래서 **1차로 프롬프트에서 형식을 강제**하고, **2차로 코드에서 보정**하는 2단 구조를 씁니다.

1. 프롬프트의 `recommended_city` 설명에 "도시 이름 1개만, 시·도 이름·괄호 설명·나열 금지"를 명시
2. 그래도 새어나오는 경우를 `normalize_city()`가 정리 — 괄호 제거 → 쉼표·슬래시 앞부분만 사용 → 공백 정리

| LLM 출력 | 정규화 결과 |
|---|---|
| `"광양 (전남)"` | `광양` |
| `"광양, 순천"` | `광양` |
| `"강릉/속초"` | `강릉` |
| `"  경주  "` | `경주` |

값이 바뀐 경우에만 `FORMAT_WARNING`으로 기록해 원본과 보정값을 함께 남깁니다.
`시`, `군` 등 행정구역 접미사는 자르지 않습니다 — `동해시`→`동해`처럼 다른 뜻과 겹치거나
`광주`(광역시 / 경기도 광주시)처럼 지역이 모호해지는 경우가 있어 프롬프트 단계에서 거르는 편이 안전합니다.

발생한 모든 오류는 `errors` 목록에 누적되어 원본 JSON과 리포트의 `## 오류 요약(errors)` 섹션에 남습니다.

## 보안 주의 사항

- **API 키를 코드에 직접 작성하지 않습니다.** 모든 키는 `.env` 또는 환경변수에서 읽어옵니다.
- `.env`는 `.gitignore`에 등록되어 있어 Git에 커밋되지 않습니다. 이 설정을 해제하지 마세요.
- 실행 결과물(`results/`)과 로그에는 키가 출력되지 않습니다. 공유 전 한 번 더 확인하세요.
- 키가 유출되었다면 즉시 발급처에서 해당 키를 폐기하고 재발급하세요.

## 개발 환경

- Python 3.10 이상 (개발/테스트: 3.11)
- 의존 패키지: `requirements.txt` 참고 (`google-generativeai`, `requests`, `python-dotenv`)
