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
| 지도 API 실패 (401/403/네트워크) | 맛집을 "데이터 없음"으로 처리하고 리포트 생성은 계속 진행 |
| 검색 결과 0건 | 중단하지 않고 "데이터 없음"으로 리포트에 표기 |

발생한 모든 오류는 `errors` 목록에 누적되어 원본 JSON과 리포트의 `## 오류 요약(errors)` 섹션에 남습니다.

## 보안 주의 사항

- **API 키를 코드에 직접 작성하지 않습니다.** 모든 키는 `.env` 또는 환경변수에서 읽어옵니다.
- `.env`는 `.gitignore`에 등록되어 있어 Git에 커밋되지 않습니다. 이 설정을 해제하지 마세요.
- 실행 결과물(`results/`)과 로그에는 키가 출력되지 않습니다. 공유 전 한 번 더 확인하세요.
- 키가 유출되었다면 즉시 발급처에서 해당 키를 폐기하고 재발급하세요.

## 개발 환경

- Python 3.10 이상 (개발/테스트: 3.11)
- 의존 패키지: `requirements.txt` 참고 (`google-generativeai`, `requests`, `python-dotenv`)
