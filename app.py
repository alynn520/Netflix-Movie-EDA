# streamlit 사용 버전
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.set_page_config(
    page_title="영화 흥행 분석",
    layout="wide"
)

st.title("🎬 극장 흥행 vs Netflix 흥행 분석")

# ----------------------------------
# 데이터 읽기
# ----------------------------------

@st.cache_data
def load_data():
    df = pd.read_csv("final_dataset.csv")

    df["극장관객수"] = (
        df["극장관객수"]
        .astype(str)
        .str.replace(",", "")
        .astype(int)
    )

    def people_group(x):
        if x >= 10000000:
            return "1000만 이상"
        elif x >= 5000000:
            return "500만~999만"
        elif x >= 1000000:
            return "100만~499만"
        else:
            return "100만 미만"

    df["관객수그룹"] = df["극장관객수"].apply(people_group)

    return df


df = load_data()

df_filtered = df[df["Netflix"]]

# ----------------------------------
# 데이터 보기
# ----------------------------------

st.header("데이터")

st.dataframe(df)

# ----------------------------------
# 기본 통계
# ----------------------------------

st.header("기본 통계")

col1, col2, col3 = st.columns(3)

col1.metric("전체 영화", len(df))
col2.metric("Netflix 진입 영화", len(df_filtered))
col3.metric("평균 관객수", f"{int(df['극장관객수'].mean()):,}")

# ----------------------------------
# 산점도
# ----------------------------------

st.header("극장 흥행 vs Netflix 최고순위")

fig, ax = plt.subplots(figsize=(10,6))

colors = {
    "1000만 이상":"red",
    "500만~999만":"orange",
    "100만~499만":"green",
    "100만 미만":"blue"
}

for group, data in df_filtered.groupby("관객수그룹"):

    ax.scatter(
        data["최고순위"],
        data["극장관객수"],
        label=group,
        s=80
    )

ax.set_xlabel("Netflix 최고순위")
ax.set_ylabel("극장 관객수")
ax.invert_xaxis()
ax.grid(alpha=0.3)
ax.legend()

st.pyplot(fig)

# ----------------------------------
# 장르 비교
# ----------------------------------

st.header("장르별 극장 흥행 vs Netflix 흥행")

theater = df.groupby("장르")["극장관객수"].mean()
netflix = df_filtered.groupby("장르")["최고순위"].mean()

compare = pd.concat([theater, netflix], axis=1)
compare.columns = ["극장관객수", "최고순위"]
compare = compare.dropna()

fig, ax1 = plt.subplots(figsize=(12,6))

ax1.plot(
    compare.index,
    compare["최고순위"],
    marker="o",
)

ax1.set_ylabel("Netflix 최고순위")
ax1.invert_yaxis()

ax2 = ax1.twinx()

ax2.bar(
    compare.index,
    compare["극장관객수"],
    alpha=0.4
)

ax2.set_ylabel("평균 극장 관객수")

plt.xticks(rotation=45)

st.pyplot(fig)

# ----------------------------------
# 장르 선택
# ----------------------------------

st.header("장르별 데이터")

genre = st.selectbox(
    "장르 선택",
    sorted(df["장르"].unique())
)

st.dataframe(
    df[df["장르"] == genre]
)