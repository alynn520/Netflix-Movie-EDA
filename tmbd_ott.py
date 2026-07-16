from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


###########################################################
# 기본 경로 설정
###########################################################

# 현재 Python 파일이 있는 폴더
BASE_DIR = Path(__file__).resolve().parent

# 입력 파일
INPUT_CSV = BASE_DIR / "KOBIS_개봉일람.csv"

# 출력 파일
ALL_OUTPUT_CSV = BASE_DIR / "all_movies_with_ott.csv"
OTT_OUTPUT_CSV = BASE_DIR / "ott_movies_only.csv"
PARTIAL_OUTPUT_CSV = BASE_DIR / "all_movies_with_ott_partial.csv"

# CSV 컬럼명
TITLE_COL = "영화명"
RELEASE_COL = "개봉일"

# TMDb 국가 및 언어 설정
COUNTRY_CODE = "KR"
LANGUAGE = "ko-KR"

# API 요청 간격
REQUEST_DELAY = 0.25

# 몇 개마다 중간 저장할지
CHECKPOINT_INTERVAL = 100


###########################################################
# 환경변수 및 TMDb 인증 설정
###########################################################

load_dotenv(BASE_DIR / ".env")

TMDB_ACCESS_TOKEN = os.getenv(
    "TMDB_ACCESS_TOKEN",
    ""
).strip()

TMDB_API_KEY = os.getenv(
    "TMDB_API_KEY",
    ""
).strip()

if not TMDB_ACCESS_TOKEN and not TMDB_API_KEY:
    raise RuntimeError(
        ".env 파일에 TMDB_ACCESS_TOKEN 또는 "
        "TMDB_API_KEY를 입력해야 합니다."
    )

headers = {
    "accept": "application/json"
}

# Access Token이 있으면 Bearer 인증 사용
if TMDB_ACCESS_TOKEN:
    # 실수로 Bearer까지 붙여 넣었을 때 제거
    if TMDB_ACCESS_TOKEN.lower().startswith("bearer "):
        TMDB_ACCESS_TOKEN = TMDB_ACCESS_TOKEN[7:].strip()

    headers["Authorization"] = (
        f"Bearer {TMDB_ACCESS_TOKEN}"
    )


###########################################################
# HTTP 세션 및 재시도 설정
###########################################################

session = requests.Session()
session.headers.update(headers)

retry_strategy = Retry(
    total=4,
    connect=4,
    read=4,
    status=4,
    backoff_factor=1,
    status_forcelist=[
        429,
        500,
        502,
        503,
        504
    ],
    allowed_methods=["GET"]
)

adapter = HTTPAdapter(
    max_retries=retry_strategy
)

session.mount("https://", adapter)
session.mount("http://", adapter)


###########################################################
# 공통 함수
###########################################################

def add_authentication(
    params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    API Key 방식일 경우 요청 파라미터에 api_key를 추가합니다.
    Access Token 방식이면 기존 파라미터만 반환합니다.
    """

    result = dict(params or {})

    if not TMDB_ACCESS_TOKEN and TMDB_API_KEY:
        result["api_key"] = TMDB_API_KEY

    return result


def request_json(
    url: str,
    params: dict[str, Any] | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """
    TMDb API를 호출하고 JSON 응답과 오류 메시지를 반환합니다.
    """

    request_params = add_authentication(params)

    try:
        response = session.get(
            url,
            params=request_params,
            timeout=20
        )

    except requests.RequestException as error:
        return None, f"REQUEST_ERROR: {error}"

    if response.status_code != 200:
        try:
            error_data = response.json()
            error_message = error_data.get(
                "status_message",
                str(error_data)
            )
        except ValueError:
            error_message = response.text[:300]

        return (
            None,
            f"HTTP_{response.status_code}: "
            f"{error_message}"
        )

    try:
        return response.json(), None

    except ValueError:
        return None, "INVALID_JSON_RESPONSE"


def normalize_title(value: Any) -> str:
    """
    제목 비교를 위해 공백과 특수문자를 제거합니다.
    """

    if pd.isna(value):
        return ""

    text = str(value).strip().lower()

    return re.sub(
        r"[^0-9a-z가-힣]",
        "",
        text
    )


def extract_year(value: Any) -> int | None:
    """
    날짜 값에서 네 자리 연도를 추출합니다.

    예:
    2023-05-01 -> 2023
    20230501   -> 2023
    2023.0     -> 2023
    """

    if pd.isna(value):
        return None

    text = str(value).strip()

    match = re.search(
        r"(18|19|20)\d{2}",
        text
    )

    if not match:
        return None

    return int(match.group())


def unique_values(values: list[str]) -> list[str]:
    """
    순서를 유지하면서 중복된 서비스명을 제거합니다.
    """

    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned_value = str(value).strip()

        if cleaned_value and cleaned_value not in seen:
            result.append(cleaned_value)
            seen.add(cleaned_value)

    return result


###########################################################
# 인증 테스트
###########################################################

def test_tmdb_authentication() -> None:
    """
    실제 영화 검색을 한 번 수행해서 인증이 정상인지 확인합니다.
    """

    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "query": "기생충",
        "language": LANGUAGE,
        "region": COUNTRY_CODE,
        "include_adult": "false"
    }

    data, error = request_json(
        url,
        params=params
    )

    if error:
        raise RuntimeError(
            "TMDb 인증 또는 연결에 실패했습니다.\n"
            f"{error}"
        )

    results = data.get("results", []) if data else []

    if not results:
        raise RuntimeError(
            "인증은 성공했지만 테스트 영화 검색 결과가 없습니다."
        )

    print("TMDb API 인증 확인 완료")
    print(
        "테스트 검색 결과:",
        results[0].get("title", "")
    )


###########################################################
# 영화 검색
###########################################################

def calculate_match_score(
    movie: dict[str, Any],
    input_title: str,
    input_release_year: int | None
) -> int:
    """
    KOBIS 영화와 TMDb 검색 결과의 매칭 점수를 계산합니다.
    """

    input_normalized = normalize_title(
        input_title
    )

    tmdb_title = normalize_title(
        movie.get("title", "")
    )

    tmdb_original_title = normalize_title(
        movie.get("original_title", "")
    )

    score = 0

    # 한국어 제목 또는 표시 제목이 정확히 일치
    if input_normalized == tmdb_title:
        score += 15

    # 원제가 정확히 일치
    if input_normalized == tmdb_original_title:
        score += 12

    # 제목 일부가 서로 포함
    if (
        input_normalized
        and tmdb_title
        and (
            input_normalized in tmdb_title
            or tmdb_title in input_normalized
        )
    ):
        score += 4

    if (
        input_normalized
        and tmdb_original_title
        and (
            input_normalized in tmdb_original_title
            or tmdb_original_title in input_normalized
        )
    ):
        score += 3

    # 개봉연도 비교
    tmdb_release_year = extract_year(
        movie.get("release_date")
    )

    if (
        input_release_year is not None
        and tmdb_release_year is not None
    ):
        year_difference = abs(
            input_release_year - tmdb_release_year
        )

        if year_difference == 0:
            score += 8
        elif year_difference == 1:
            score += 3
        elif year_difference >= 3:
            score -= 3

    return score


def search_movie(
    title: Any,
    release_date: Any = None
) -> tuple[dict[str, Any] | None, str]:
    """
    영화 제목과 개봉연도를 이용해 가장 적합한 TMDb 영화를 찾습니다.
    """

    if pd.isna(title):
        return None, "EMPTY_TITLE"

    title_text = str(title).strip()

    if (
        not title_text
        or title_text.lower() == "nan"
    ):
        return None, "EMPTY_TITLE"

    release_year = extract_year(
        release_date
    )

    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "query": title_text,
        "language": LANGUAGE,
        "region": COUNTRY_CODE,
        "include_adult": "false"
    }

    data, error = request_json(
        url,
        params=params
    )

    if error:
        return None, f"SEARCH_API_ERROR | {error}"

    results = data.get("results", []) if data else []

    if not results:
        return None, "SEARCH_NOT_FOUND"

    # 제목과 연도를 기준으로 가장 점수가 높은 영화 선택
    scored_results = [
        (
            calculate_match_score(
                movie,
                title_text,
                release_year
            ),
            movie
        )
        for movie in results
    ]

    scored_results.sort(
        key=lambda item: item[0],
        reverse=True
    )

    best_score, best_movie = scored_results[0]

    # 점수가 0 이하라면 검색은 됐지만 매칭이 매우 불확실함
    if best_score <= 0:
        return {
            "id": best_movie.get("id"),
            "title": best_movie.get("title", ""),
            "original_title": best_movie.get(
                "original_title",
                ""
            ),
            "release_date": best_movie.get(
                "release_date",
                ""
            ),
            "match_score": best_score
        }, "LOW_MATCH_SCORE"

    return {
        "id": best_movie.get("id"),
        "title": best_movie.get("title", ""),
        "original_title": best_movie.get(
            "original_title",
            ""
        ),
        "release_date": best_movie.get(
            "release_date",
            ""
        ),
        "match_score": best_score
    }, "SEARCH_SUCCESS"


###########################################################
# OTT 제공 서비스 조회
###########################################################

def get_watch_providers(
    movie_id: int
) -> tuple[dict[str, Any] | None, str]:
    """
    한국에서 제공되는 구독, 무료, 광고, 대여 및 구매 정보를 조회합니다.
    """

    url = (
        "https://api.themoviedb.org/3/movie/"
        f"{movie_id}/watch/providers"
    )

    data, error = request_json(url)

    if error:
        return None, f"PROVIDER_API_ERROR | {error}"

    all_regions = (
        data.get("results", {})
        if data
        else {}
    )

    kr_data = all_regions.get(COUNTRY_CODE)

    if not kr_data:
        return {
            "flatrate": [],
            "free": [],
            "ads": [],
            "rent": [],
            "buy": [],
            "link": ""
        }, "NO_KR_PROVIDER_DATA"

    provider_types = [
        "flatrate",
        "free",
        "ads",
        "rent",
        "buy"
    ]

    result: dict[str, Any] = {
        "link": kr_data.get("link", "")
    }

    for provider_type in provider_types:
        provider_items = kr_data.get(
            provider_type,
            []
        )

        result[provider_type] = unique_values(
            [
                provider.get(
                    "provider_name",
                    ""
                )
                for provider in provider_items
            ]
        )

    if result["flatrate"]:
        status = "SUBSCRIPTION_OTT_FOUND"

    elif any(
        result[provider_type]
        for provider_type in [
            "free",
            "ads",
            "rent",
            "buy"
        ]
    ):
        status = "OTHER_ONLINE_PROVIDER_FOUND"

    else:
        status = "KR_DATA_WITHOUT_PROVIDER"

    return result, status


###########################################################
# CSV 데이터 불러오기 및 정리
###########################################################

def load_movie_data() -> pd.DataFrame:
    """
    KOBIS CSV를 불러오고 빈 영화명을 제거합니다.
    """

    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"입력 파일을 찾을 수 없습니다:\n{INPUT_CSV}"
        )

    dataframe = pd.read_csv(
        INPUT_CSV,
        encoding="utf-8"
    )

    # 컬럼명 앞뒤 공백 제거
    dataframe.columns = (
        dataframe.columns
        .astype(str)
        .str.strip()
    )

    required_columns = {
        TITLE_COL,
        RELEASE_COL
    }

    missing_columns = (
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        raise KeyError(
            "CSV에 필요한 컬럼이 없습니다: "
            f"{sorted(missing_columns)}\n"
            f"현재 컬럼: {dataframe.columns.tolist()}"
        )

    original_count = len(dataframe)

    # 전체가 비어 있는 행 제거
    dataframe = dataframe.dropna(
        how="all"
    ).copy()

    # 영화명이 NaN인 행 제거
    dataframe = dataframe.dropna(
        subset=[TITLE_COL]
    ).copy()

    # 영화명 앞뒤 공백 제거
    dataframe[TITLE_COL] = (
        dataframe[TITLE_COL]
        .astype(str)
        .str.strip()
    )

    # 빈 문자열 및 "nan" 문자열 제거
    dataframe = dataframe[
        dataframe[TITLE_COL].ne("")
        & dataframe[TITLE_COL]
        .str.lower()
        .ne("nan")
    ].copy()

    dataframe = dataframe.reset_index(
        drop=True
    )

    print(
        f"원본 행 수: {original_count}"
    )
    print(
        f"유효 영화 수: {len(dataframe)}"
    )
    print(
        f"제거된 빈 행 수: "
        f"{original_count - len(dataframe)}"
    )

    print("\n첫 번째 데이터 확인")
    print(
        dataframe[
            [TITLE_COL, RELEASE_COL]
        ].head()
    )

    return dataframe


###########################################################
# 중간 결과 저장
###########################################################

def save_partial_result(
    original_df: pd.DataFrame,
    result_rows: list[dict[str, Any]],
    processed_count: int
) -> None:
    """
    프로그램 중단에 대비해 처리된 부분까지 저장합니다.
    """

    partial_original = (
        original_df
        .iloc[:processed_count]
        .reset_index(drop=True)
    )

    partial_result = pd.DataFrame(
        result_rows
    )

    partial_df = pd.concat(
        [
            partial_original,
            partial_result
        ],
        axis=1
    )

    partial_df.to_csv(
        PARTIAL_OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig"
    )


###########################################################
# 전체 영화 처리
###########################################################

def analyze_movies(
    dataframe: pd.DataFrame
) -> pd.DataFrame:
    """
    모든 영화의 TMDb ID 및 OTT 정보를 조회합니다.
    """

    result_rows: list[dict[str, Any]] = []

    total = len(dataframe)

    for position, row in enumerate(
        dataframe.itertuples(index=False),
        start=1
    ):
        title = getattr(row, TITLE_COL)
        release_date = getattr(
            row,
            RELEASE_COL
        )

        print(
            f"[{position}/{total}] "
            f"{title} | {release_date}"
        )

        movie_data, search_status = search_movie(
            title,
            release_date
        )

        # 검색 실패
        if movie_data is None:
            result_rows.append({
                "TMDB_ID": pd.NA,
                "TMDB_TITLE": "",
                "TMDB_ORIGINAL_TITLE": "",
                "TMDB_RELEASE_DATE": "",
                "TMDB_MATCH_SCORE": pd.NA,
                "OTT": "",
                "OTT_ALL": "",
                "OTT_FREE": "",
                "OTT_ADS": "",
                "OTT_RENT": "",
                "OTT_BUY": "",
                "Netflix": False,
                "OTT_LINK": "",
                "OTT_STATUS": search_status
            })

        else:
            movie_id = movie_data.get("id")

            providers, provider_status = (
                get_watch_providers(
                    int(movie_id)
                )
            )

            if providers is None:
                result_rows.append({
                    "TMDB_ID": movie_id,
                    "TMDB_TITLE": movie_data.get(
                        "title",
                        ""
                    ),
                    "TMDB_ORIGINAL_TITLE": (
                        movie_data.get(
                            "original_title",
                            ""
                        )
                    ),
                    "TMDB_RELEASE_DATE": (
                        movie_data.get(
                            "release_date",
                            ""
                        )
                    ),
                    "TMDB_MATCH_SCORE": (
                        movie_data.get(
                            "match_score"
                        )
                    ),
                    "OTT": "",
                    "OTT_ALL": "",
                    "OTT_FREE": "",
                    "OTT_ADS": "",
                    "OTT_RENT": "",
                    "OTT_BUY": "",
                    "Netflix": False,
                    "OTT_LINK": "",
                    "OTT_STATUS": (
                        f"{search_status} | "
                        f"{provider_status}"
                    )
                })

            else:
                flatrate = providers["flatrate"]
                free = providers["free"]
                ads = providers["ads"]
                rent = providers["rent"]
                buy = providers["buy"]

                all_providers = unique_values(
                    flatrate
                    + free
                    + ads
                    + rent
                    + buy
                )

                netflix_available = any(
                    "netflix" in provider.lower()
                    for provider in flatrate
                )

                result_rows.append({
                    "TMDB_ID": movie_id,
                    "TMDB_TITLE": movie_data.get(
                        "title",
                        ""
                    ),
                    "TMDB_ORIGINAL_TITLE": (
                        movie_data.get(
                            "original_title",
                            ""
                        )
                    ),
                    "TMDB_RELEASE_DATE": (
                        movie_data.get(
                            "release_date",
                            ""
                        )
                    ),
                    "TMDB_MATCH_SCORE": (
                        movie_data.get(
                            "match_score"
                        )
                    ),
                    "OTT": ", ".join(flatrate),
                    "OTT_ALL": ", ".join(
                        all_providers
                    ),
                    "OTT_FREE": ", ".join(free),
                    "OTT_ADS": ", ".join(ads),
                    "OTT_RENT": ", ".join(rent),
                    "OTT_BUY": ", ".join(buy),
                    "Netflix": netflix_available,
                    "OTT_LINK": providers["link"],
                    "OTT_STATUS": (
                        f"{search_status} | "
                        f"{provider_status}"
                    )
                })

        # 100개마다 중간 저장
        if (
            position % CHECKPOINT_INTERVAL == 0
            or position == total
        ):
            save_partial_result(
                dataframe,
                result_rows,
                position
            )

            print(
                f"중간 저장 완료: "
                f"{position}/{total}"
            )

        time.sleep(REQUEST_DELAY)

    result_df = pd.DataFrame(
        result_rows
    )

    final_df = pd.concat(
        [
            dataframe.reset_index(drop=True),
            result_df
        ],
        axis=1
    )

    return final_df


###########################################################
# 최종 파일 저장
###########################################################

def save_results(
    final_df: pd.DataFrame
) -> None:
    """
    전체 결과와 구독형 OTT 영화만 필터링한 결과를 저장합니다.
    """

    # 구독형 OTT 서비스가 존재하는 영화
    ott_df = final_df[
        final_df["OTT"]
        .fillna("")
        .str.strip()
        .ne("")
    ].copy()

    final_df.to_csv(
        ALL_OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    ott_df.to_csv(
        OTT_OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig"
    )

    # 최종 저장 후 중간 파일 삭제
    if PARTIAL_OUTPUT_CSV.exists():
        PARTIAL_OUTPUT_CSV.unlink()

    print("\n처리 완료")
    print(f"전체 영화 수: {len(final_df)}")
    print(
        f"구독형 OTT 영화 수: {len(ott_df)}"
    )
    print(
        f"Netflix 영화 수: "
        f"{int(final_df['Netflix'].sum())}"
    )

    print("\nOTT 조회 상태별 개수")

    status_counts = (
        final_df["OTT_STATUS"]
        .value_counts(dropna=False)
    )

    print(status_counts.to_string())

    print("\n저장 위치")
    print(f"전체 결과: {ALL_OUTPUT_CSV}")
    print(f"OTT 영화: {OTT_OUTPUT_CSV}")


###########################################################
# 프로그램 실행
###########################################################

def main() -> None:
    test_tmdb_authentication()

    movie_df = load_movie_data()

    final_df = analyze_movies(
        movie_df
    )

    save_results(
        final_df
    )


if __name__ == "__main__":
    main()