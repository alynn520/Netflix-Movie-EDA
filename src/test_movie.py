# 영화 하나만 조회

import pandas as pd
import requests
import time

# TMDb API 설정
ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiIwYjNhNjdiNGFmMjE0YjE3MDk1YzU0NGIwMGI1MDRhMiIsIm5iZiI6MTc4NDA4MzcyMS4zNjksInN1YiI6IjZhNTZmNTA5MDA2OWQ1OTVkYWY0NDdkZCIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.Lp0h9qDdU1xcWw3N-ixvWWoded-H7M22w044XfHKaFg"

headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}

# 파일 경로
df = pd.read_csv("/content/KOBIS_개봉일람.csv", encoding = "utf-8")

TITLE_COL = "영화명"
RELEASE_COL = "개봉일"

test_title = df.iloc[1][TITLE_COL]
test_release_date = df.iloc[1][RELEASE_COL]

print("영화명:", test_title)
print("개봉일:", test_release_date)

search_url = "https://api.themoviedb.org/3/search/movie"

search_params = {
    "query": str(test_title).strip(),
    "language": "ko-KR",
    "region": "KR"
}

search_response = requests.get(
    search_url,
    headers=headers,
    params=search_params
)

print("검색 API 상태 코드:", search_response.status_code)
print("검색 API 응답:", search_response.json())