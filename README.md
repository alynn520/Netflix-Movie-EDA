# AI Training Projects 2026

2026 NVIDIA AI 전문인력 양성과정에서 진행한 개인 프로젝트입니다.

공공 데이터(KOBIS)와 Netflix TOP10 데이터를 활용하여
영화의 극장 흥행과 OTT 성과의 관계를 탐색하기 위한
EDA(Exploratory Data Analysis)를 수행했습니다.

본 프로젝트에서는 데이터 수집, 전처리, 통합, 시각화를 중심으로
흥행 요인과 장르별 특성을 분석했습니다.

## Training

- 과정명 : NVIDIA AI 전문인력 양성과정 (2026)
- 주관 : 한컴아카데미 × NVIDIA DLI
- 형태 : 개인 미니 프로젝트

## Project Goal

- KOBIS 영화 데이터를 수집
- TMDb API를 이용하여 OTT 플랫폼 정보 확인
- Netflix TOP10 데이터와 통합
- 영화 흥행과 Netflix 성과 비교
- 장르별 특징 분석

## Dataset

| Data | Description |
|------|-------------|
| KOBIS | 영화 개봉 및 관객수 |
| TMDb API | OTT 플랫폼 정보 |
| Netflix Top10 | Netflix 주간 순위 데이터 |

## Analysis Process

1. KOBIS 영화 데이터 수집
2. TMDb API를 통한 OTT 정보 조회
3. Netflix 콘텐츠 필터링
4. Netflix Top10 데이터 병합
5. 데이터 전처리
6. EDA 수행 (Streamlit 활용)

## Exploratory Data Analysis

- 장르별 Netflix 성과 비교
- 극장 흥행과 OTT 성과 상관관계

## Tech Stack

- Python
- Pandas
- NumPy
- Matplotlib
- Scikit-Learn
- Requests
- TMDb API