import argparse 
import google.generativeai as genai
import os
from dotenv import load_dotenv
import requests
import json
import sys
from datetime import datetime
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")

if not GEMINI_API_KEY or not KAKAO_REST_API_KEY: # 키 미설정 시 설정 방법 안내
    print("[오류] API 키가 설정되지 않았습니다.")
    print("프로젝트 루트에 .env 파일을 만들고 아래 두 줄을 작성하세요:")
    print("  GEMINI_API_KEY=발급받은_키")
    print("  KAKAO_REST_API_KEY=발급받은_키")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
errors = [] #오류 목록 관리

parser = argparse.ArgumentParser(description="국내 여행지 추천 프로그램")
parser.add_argument("--date", required=True, help="여행 날짜 (YYYY-MM-DD)")
args = parser.parse_args()

try:
    datetime.strptime(args.date, "%Y-%m-%d")
except ValueError:
    parser.print_usage()
    print("Error: Invalid date format. Please use YYYY-MM-DD format.")
    sys.exit(1)

def get_travel_recommendations(date_str):
    prompt = f"""{date_str}에 여행하기 좋은 국내 도시를 1곳 추천해줘. 그리고 아래 JSON 형식으로 답변하고 다른 설명은 출력하지 마

    {{
        "recommended_city": "도시 이름",
        "weather": "날씨 정보",
        "events": ["행사/이벤트1", "행사/이벤트2"],
        "reason": "추천 이유(2~4문장)"
    }}"""
    model = genai.GenerativeModel("gemini-3.6-flash") #모델 객체 생성
    response = model.generate_content(prompt) #그 객체의 메소드로 호출
    return response.text

raw_text = get_travel_recommendations(args.date)

try:
    recommendation = json.loads(raw_text)
except json.JSONDecodeError:
    errors.append({"step": "llm_recommend", "type": "PARSE_ERROR", "message": "1차 JSON 파싱 실패: 재시도"})
    raw_text = get_travel_recommendations(args.date)
    try:
        recommendation = json.loads(raw_text)
    except json.JSONDecodeError:
        errors.append({"step": "llm_recommend", "type": "PARSE_ERROR", "message": "재시도도 실패"})
        recommendation = {}

print(f"[1/3] 1차 추천 생성 완료 - recommended_city: {recommendation.get('recommended_city')}")

def search_restaurants(city): #카카오 api에 요청 보내기
    url = "https://dapi.kakao.com/v2/local/search/keyword.json" # to where
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"} #헤더
    params = {"query": f"{city} 맛집", "size": 5} #파라미터(본문)

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        errors.append({"step": "place_search", "type": "REQUEST_ERROR", "message": str(e)})
        return []

    data = response.json()
    documents = data.get("documents", [])
    results = []
    for doc in documents:
        results.append({
            "name": doc.get("place_name"),
            "address": doc.get("road_address_name") or doc.get("address_name"),
            "category": doc.get("category_name"),
            "url": doc.get("place_url"),
            "x": doc.get("x"),
            "y": doc.get("y"),
        })
    return results

city = recommendation.get("recommended_city")

if not city:
    restaurants = []
    errors.append({"step": "place_search", "type": "SKIPPED", "message": "추천 도시 없음"})
else:
    restaurants = search_restaurants(city)
    if not restaurants:
        errors.append({"step": "place_search", "type": "EMPTY_RESULT", "message": f"0 results for query={city} 맛집"})

print(f"[2/3] 맛집 검색 완료 - {len(restaurants)}곳")

def generate_report(date_str, recommendation, restaurants):
    prompt = f"""아래 정보를 바탕으로 {date_str} 국내 여행 리포트를 Markdown으로 작성해줘.

[1차 추천 정보]
{json.dumps(recommendation, ensure_ascii=False, indent=2)}

[맛집 목록]
{json.dumps(restaurants, ensure_ascii=False, indent=2)}

아래 섹션을 반드시 포함하고, 다른 설명은 붙이지 마.
# {date_str} 국내 여행 추천 리포트
## 추천 지역
## 추천 이유
## 날씨 요약
## 행사/축제
## 맛집 추천
## 1일 일정 제안 (오전/오후/저녁)

맛집 목록이 비어 있으면 맛집 추천 섹션에 "- 데이터 없음"이라고만 적어줘.
"""
    try:
        model = genai.GenerativeModel("gemini-3.6-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        errors.append({"step": "llm_report", "type": "API_ERROR", "message": str(e)})
        return f"# {date_str} 국내 여행 추천 리포트\n\n리포트 생성에 실패했습니다."


report = generate_report(args.date, recommendation, restaurants)

report += "\n\n## 오류 요약(errors)\n"
if errors:
    for err in errors:
        report += f"- [{err['step']}] {err['type']}: {err['message']}\n"
else:
    report += "- 없음\n"

print("[3/3] 최종 리포트 생성 완료")

os.makedirs("results", exist_ok=True) # results 폴더 생성

raw_data = {
    "date": args.date,
    "recommendation": recommendation,
    "restaurants": restaurants,
    "errors": errors,
}

json_path = f"results/{args.date}_raw.json"
md_path = f"results/{args.date}_travel_plan.md"

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(raw_data, f, ensure_ascii=False, indent=2)

with open(md_path, "w", encoding="utf-8") as f:
    f.write(report)

print(f"\n완료! {md_path} 를 확인하세요.")






      