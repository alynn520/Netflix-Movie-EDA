# EDA 전 연습용
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 한글 폰트 설정
plt.rcParams["font.family"] = "Malgun Gothic"

# 마이너스 기호 깨짐 방지
plt.rcParams["axes.unicode_minus"] = False

# 자전거 대여량
# parse_dates: datetime의 type이 object -> datetimes로 변경됨
df = pd.read_csv("D:/Nividia_AI/train.csv", encoding='cp949', parse_dates=["datetime"])
print(df.info())

df["year"] = df["datetime"].dt.year # year 컬럼이 생김
df["month"] = df["datetime"].dt.month
df["day"] = df["datetime"].dt.day
df["hour"] = df["datetime"].dt.hour
df["minute"] = df["datetime"].dt.minute
df["second"] = df["datetime"].dt.second
df["dayofweek"] = df["datetime"].dt.dayofweek

print(df.head())

#sns.barplot(data=df, x="month", y="count", hue="season")
#sns.pointplot(data=df, x="hour", y="count", hue="season")
sns.scatterplot(data=df, x="month", y="count", hue="season")
plt.show()