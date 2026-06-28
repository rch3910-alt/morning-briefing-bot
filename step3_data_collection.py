# -*- coding: utf-8 -*-
import sys
import json
import requests
import feedparser
import yfinance as yf
from datetime import datetime, timezone, timedelta
import progress

sys.stdout.reconfigure(encoding="utf-8")

print("=" * 50)
print("[3단계] 증시 데이터 & 날씨 크롤링")
print("=" * 50)

# ── 1. 나스닥 지수 ───────────────────────────────────────────
def get_nasdaq():
    try:
        ticker = yf.Ticker("^IXIC")
        hist = ticker.history(period="2d")
        if len(hist) < 2:
            return None
        prev_close = hist["Close"].iloc[-2]
        last_close = hist["Close"].iloc[-1]
        change = last_close - prev_close
        pct = change / prev_close * 100
        return {
            "index": "나스닥 (NASDAQ)",
            "close": round(last_close, 2),
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "date": hist.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception as e:
        print(f"  [경고] 나스닥 조회 실패: {e}")
        return None

nasdaq = get_nasdaq()
if nasdaq:
    arrow = "▲" if nasdaq["change"] >= 0 else "▼"
    print(f"\n[증시] {nasdaq['index']} ({nasdaq['date']})")
    print(f"  종가: {nasdaq['close']:,.2f}  {arrow} {abs(nasdaq['change']):,.2f} ({nasdaq['change_pct']:+.2f}%)")
else:
    print("\n[증시] 나스닥 데이터 조회 실패")

# ── 2. 뉴스 RSS (증시 TOP5 + 반도체 TOP3) ───────────────────
def fetch_rss_news(url, max_items=5):
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            items.append({
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            })
        return items
    except Exception as e:
        print(f"  [경고] RSS 조회 실패 ({url}): {e}")
        return []

# 한국경제 증권 RSS
stock_news = fetch_rss_news("https://www.hankyung.com/feed/finance", max_items=5)
# 전자신문 반도체 RSS
semi_news = fetch_rss_news("https://rss.etnews.com/Section901.xml", max_items=3)

# RSS 실패 시 백업: 매일경제
if not stock_news:
    stock_news = fetch_rss_news("https://www.mk.co.kr/rss/30100041/", max_items=5)

print(f"\n[증시 뉴스 TOP{len(stock_news)}]")
for i, n in enumerate(stock_news, 1):
    print(f"  {i}. {n['title']}")

print(f"\n[반도체 뉴스 TOP{len(semi_news)}]")
for i, n in enumerate(semi_news, 1):
    print(f"  {i}. {n['title']}")

# ── 3. 날씨 (Open-Meteo, 서울 기준) ─────────────────────────
def get_weather():
    try:
        # 날씨
        w_url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=37.5641&longitude=126.9979"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
            "precipitation_hours&current=temperature_2m,weathercode"
            "&timezone=Asia%2FSeoul&forecast_days=1"
        )
        wr = requests.get(w_url, timeout=10).json()
        cur_temp = wr["current"]["temperature_2m"]
        max_temp = wr["daily"]["temperature_2m_max"][0]
        min_temp = wr["daily"]["temperature_2m_min"][0]
        precip_prob = wr["daily"]["precipitation_probability_max"][0]
        precip_hours = wr["daily"]["precipitation_hours"][0]

        # 미세먼지 (Open-Meteo Air Quality)
        aq_url = (
            "https://air-quality-api.open-meteo.com/v1/air-quality"
            "?latitude=37.5641&longitude=126.9979"
            "&current=pm10,pm2_5"
            "&timezone=Asia%2FSeoul"
        )
        aqr = requests.get(aq_url, timeout=10).json()
        pm10 = aqr["current"].get("pm10", None)
        pm25 = aqr["current"].get("pm2_5", None)

        def dust_grade(val, thresholds):
            if val is None:
                return "정보없음"
            if val <= thresholds[0]:
                return "좋음"
            elif val <= thresholds[1]:
                return "보통"
            elif val <= thresholds[2]:
                return "나쁨"
            return "매우나쁨"

        return {
            "cur_temp": cur_temp,
            "max_temp": max_temp,
            "min_temp": min_temp,
            "precip_prob": precip_prob,
            "precip_hours": precip_hours,
            "pm10": pm10,
            "pm10_grade": dust_grade(pm10, [30, 80, 150]),
            "pm25": pm25,
            "pm25_grade": dust_grade(pm25, [15, 35, 75]),
        }
    except Exception as e:
        print(f"  [경고] 날씨 조회 실패: {e}")
        return None

weather = get_weather()
if weather:
    print(f"\n[날씨] 서울 오늘 ({datetime.now().strftime('%Y-%m-%d')})")
    print(f"  현재 기온: {weather['cur_temp']}°C  (최고 {weather['max_temp']}°C / 최저 {weather['min_temp']}°C)")
    print(f"  강수 확률: {weather['precip_prob']}%  강수 시간: {weather['precip_hours']}시간")
    print(f"  미세먼지(PM10): {weather['pm10']}㎍/㎥ ({weather['pm10_grade']})")
    print(f"  초미세먼지(PM2.5): {weather['pm25']}㎍/㎥ ({weather['pm25_grade']})")
else:
    print("\n[날씨] 날씨 데이터 조회 실패")

# ── 4. 수집 결과를 JSON으로 임시 저장 (4단계에서 사용) ────────
collected = {
    "nasdaq": nasdaq,
    "stock_news": stock_news,
    "semi_news": semi_news,
    "weather": weather,
    "collected_at": datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"),
}
with open("output/collected_data.json", "w", encoding="utf-8") as f:
    json.dump(collected, f, ensure_ascii=False, indent=2)
print("\n[저장] output/collected_data.json 저장 완료")

progress.save(3, "3단계 완료")
print("\n3단계 완료!")
