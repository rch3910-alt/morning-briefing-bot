# -*- coding: utf-8 -*-
"""
아침 브리핑 자동화 시스템 — 메인 실행 파일
매일 아침 6시 30분 (한국 시간) GitHub Actions 또는 윈도우 작업 스케줄러로 실행
--force 플래그로 중복 방지 체크 우회 가능
"""
import os
import re
import sys
import html
import requests
import feedparser
import yfinance as yf
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from deep_translator import GoogleTranslator, MyMemoryTranslator

sys.stdout.reconfigure(encoding="utf-8")

FORCE_MODE = "--force" in sys.argv

# ── 환경변수 로드 ─────────────────────────────────────────────
load_dotenv("input/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID")
SHEET_ID       = os.getenv("GOOGLE_SHEET_ID")
CREDS_FILE     = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID", "primary")
KMA_KEY        = os.getenv("KMA_API_KEY")
AIRKOREA_KEY   = os.getenv("AIRKOREA_API_KEY")

KST           = timezone(timedelta(hours=9))
NOW           = datetime.now(KST)
TODAY_STR     = NOW.strftime("%Y-%m-%d")
TODAY_DISPLAY = NOW.strftime("%Y년 %m월 %d일")
WEEKDAY       = ["월", "화", "수", "목", "금", "토", "일"][NOW.weekday()]

print(f"[{NOW.strftime('%Y-%m-%d %H:%M')}] 아침 브리핑 시스템 시작{'  (FORCE)' if FORCE_MODE else ''}")

# ── 구글 인증 ─────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]
creds     = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
gc        = gspread.authorize(creds)
worksheet = gc.open_by_key(SHEET_ID).sheet1

# ── 중복 방지 체크 ────────────────────────────────────────────
if not FORCE_MODE:
    if TODAY_STR in worksheet.col_values(1):
        print(f"[중복 방지] 오늘({TODAY_STR}) 이미 발송됨. 종료.")
        sys.exit(0)

# ── 1. 구글 캘린더 일정 ───────────────────────────────────────
def get_today_events():
    try:
        service   = build("calendar", "v3", credentials=creds)
        day_start = NOW.replace(hour=0,  minute=0,  second=0,  microsecond=0).isoformat()
        day_end   = NOW.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
        result    = service.events().list(
            calendarId=CALENDAR_ID, timeMin=day_start, timeMax=day_end,
            singleEvents=True, orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except Exception as e:
        print(f"[경고] 캘린더 조회 실패: {e}")
        return []

events = get_today_events()
print(f"캘린더 일정: {len(events)}개")

# ── 2. 글로벌 시장 데이터 (나스닥·다우존스·금·은·비트코인) ────
MARKET_TICKERS = [
    ("나스닥",    "^IXIC",   None),
    ("금",        "GC=F",    "$/oz"),
    ("비트코인",  "BTC-USD", "$"),
]

def get_market(name, symbol):
    try:
        hist = yf.Ticker(symbol).history(period="2d")
        if len(hist) < 1:
            return None
        if len(hist) >= 2:
            prev  = hist["Close"].iloc[-2]
            last  = hist["Close"].iloc[-1]
            change     = last - prev
            change_pct = change / prev * 100
        else:
            last = hist["Close"].iloc[-1]
            change = change_pct = 0.0
        return {
            "name":       name,
            "symbol":     symbol,
            "close":      round(last, 2),
            "change":     round(change, 2),
            "change_pct": round(change_pct, 2),
            "date":       hist.index[-1].strftime("%Y-%m-%d"),
        }
    except Exception as e:
        print(f"[경고] {name} 조회 실패: {e}")
        return None

markets = []
for name, sym, unit in MARKET_TICKERS:
    m = get_market(name, sym)
    if m:
        m["unit"] = unit
        markets.append(m)
    print(f"  {name}: {'OK' if m else 'FAIL'}")

# ── 3. Fear & Greed Index (CNN) ───────────────────────────────
def get_fear_greed():
    rating_ko_map = {
        "Extreme Fear": "극단적 공포",
        "Fear": "공포",
        "Neutral": "중립",
        "Greed": "탐욕",
        "Extreme Greed": "극단적 탐욕",
    }
    def score_to_emoji(s):
        if s <= 24:   return "😱"
        elif s <= 44: return "😨"
        elif s <= 55: return "😐"
        elif s <= 75: return "😊"
        else:         return "🤑"

    # 1차 시도: CNN API
    try:
        r = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://edition.cnn.com/markets/fear-and-greed",
                "Accept": "application/json",
            },
            timeout=10,
        )
        print(f"  Fear&Greed CNN 응답: {r.status_code}")
        data = r.json()
        fg = data["fear_and_greed"]
        score = round(fg["score"])
        rating = fg["rating"]
        return {"score": score, "rating": rating, "rating_ko": rating_ko_map.get(rating, rating), "emoji": score_to_emoji(score), "source": "CNN"}
    except Exception as e:
        print(f"[경고] CNN Fear&Greed 실패: {e}")

    # 2차 시도: alternative.me (암호화폐 F&G — 주식 시장 심리 보조 지표)
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        print(f"  Fear&Greed alternative.me 응답: {r.status_code}")
        data = r.json()
        score = int(data["data"][0]["value"])
        rating = data["data"][0]["value_classification"]
        return {"score": score, "rating": rating, "rating_ko": rating_ko_map.get(rating, rating), "emoji": score_to_emoji(score), "source": "Crypto F&G"}
    except Exception as e:
        print(f"[경고] alternative.me Fear&Greed 실패: {e}")

    return None

fear_greed = get_fear_greed()
print(f"Fear&Greed: {'OK' if fear_greed else 'FAIL'}")

# ── 4. 번역 헬퍼 (MyMemory — 무료, API키 불필요) ─────────────
def translate_ko(text: str) -> str:
    # GoogleTranslator (비공식, 키 불필요) 우선 시도
    try:
        result = GoogleTranslator(source="auto", target="ko").translate(text[:500])
        if result:
            return result
    except Exception:
        pass
    # MyMemory 폴백 (소스 언어 명시)
    try:
        return MyMemoryTranslator(source="en-US", target="ko-KR").translate(text[:500])
    except Exception:
        return text

# ── 5. 미국 증시 뉴스 TOP5 (Reuters · CNBC · MarketWatch) ────
MARKET_NEWS_SOURCES = [
    ("Bloomberg",   "https://feeds.bloomberg.com/markets/news.rss"),
    ("WSJ",         "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("CNBC",        "https://www.cnbc.com/id/100727362/device/rss/rss.html"),
]

def fetch_rss(url: str, max_items: int = 10) -> list:
    try:
        feed = feedparser.parse(url)
        return [
            {"title": e.get("title", "").strip(), "link": e.get("link", "")}
            for e in feed.entries[:max_items]
            if e.get("title", "").strip()
        ]
    except Exception:
        return []

raw_market_news = []
for src_name, url in MARKET_NEWS_SOURCES:
    items = fetch_rss(url, 5)
    for it in items:
        it["source"] = src_name
    raw_market_news.extend(items)
    print(f"  {src_name} 뉴스: {len(items)}개")

# 중복 제거 후 5개 번역
seen_titles = set()
stock_news = []
for item in raw_market_news:
    if item["title"] not in seen_titles and len(stock_news) < 5:
        seen_titles.add(item["title"])
        item["title_ko"] = translate_ko(item["title"])
        stock_news.append(item)

# ── 6. 반도체 뉴스 TOP5 (Reuters · CNBC · Ars Technica 필터링) ──
SEMI_SOURCES = [
    ("Bloomberg Tech", "https://feeds.bloomberg.com/technology/news.rss"),
    ("CNBC Tech",      "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    ("EE Times",       "https://www.eetimes.com/feed/"),
]
SEMI_KEYWORDS = [
    "semiconductor", "chip", "nvidia", "amd", "intel", "tsmc", "qualcomm",
    "broadcom", "micron", "arm", "gpu", "cpu", "memory", "nand", "dram",
    "foundry", "wafer", "silicon", "hynix", "samsung", "ai chip", "soc",
]

raw_semi_news = []
for src_name, url in SEMI_SOURCES:
    items = fetch_rss(url, 20)
    filtered = [
        it for it in items
        if any(kw in it["title"].lower() for kw in SEMI_KEYWORDS)
    ]
    for it in filtered:
        it["source"] = src_name
    raw_semi_news.extend(filtered)
    print(f"  {src_name} 반도체 뉴스: {len(filtered)}개")

seen_semi = set()
semi_news = []
for item in raw_semi_news:
    if item["title"] not in seen_semi and len(semi_news) < 5:
        seen_semi.add(item["title"])
        item["title_ko"] = translate_ko(item["title"])
        semi_news.append(item)

# ── 6. 날씨 (기상청 단기예보) + 미세먼지 (에어코리아) ──────────

def _grade(v, thresholds):
    if v is None:
        return "정보없음"
    for thr, label in zip(thresholds, ["좋음", "보통", "나쁨"]):
        if v <= thr:
            return label
    return "매우나쁨"

def _get_weather_kma():
    """기상청 단기예보 API — 서울 중구 (nx=60, ny=127)"""
    if not KMA_KEY:
        print("  [날씨] KMA_API_KEY 없음 → Open-Meteo 폴백")
        return None
    try:
        # 기준시각: 0200/0500/0800/1100/1400/1700/2000/2300 중 최근 발표
        base_hours = [2, 5, 8, 11, 14, 17, 20, 23]
        candidates = [h for h in base_hours if h <= NOW.hour]
        if candidates:
            base_h, base_date = max(candidates), NOW.strftime("%Y%m%d")
        else:
            base_h, base_date = 23, (NOW - timedelta(days=1)).strftime("%Y%m%d")

        today_str    = NOW.strftime("%Y%m%d")
        cur_hour_str = f"{NOW.hour:02d}00"

        r = requests.get(
            "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
            params={
                "serviceKey": KMA_KEY,
                "pageNo": 1, "numOfRows": 1000,
                "dataType": "JSON",
                "base_date": base_date, "base_time": f"{base_h:02d}00",
                "nx": 60, "ny": 127,
            },
            timeout=15,
        )
        items = r.json()["response"]["body"]["items"]["item"]
        today_items = [it for it in items if it["fcstDate"] == today_str]

        fcst = {}
        for it in today_items:
            fcst.setdefault(it["category"], {})[it["fcstTime"]] = it["fcstValue"]

        # 현재 기온: 현재 시각 이후 가장 가까운 TMP
        tmp_data = fcst.get("TMP", {})
        cur_temp = next(
            (float(tmp_data[t]) for t in sorted(tmp_data) if t >= cur_hour_str),
            float(list(tmp_data.values())[-1]) if tmp_data else None,
        )

        # 최고/최저 기온 (TMX·TMN 우선, 없으면 TMP 전체에서 max/min)
        tmx = fcst.get("TMX", {})
        tmn = fcst.get("TMN", {})
        max_temp = float(next(iter(tmx.values()))) if tmx else (max(float(v) for v in tmp_data.values()) if tmp_data else None)
        min_temp = float(next(iter(tmn.values()))) if tmn else (min(float(v) for v in tmp_data.values()) if tmp_data else None)

        # 강수 확률 (POP: 3시간 단위, 현재 이후 최대)
        pop_data = fcst.get("POP", {})
        remaining_pops = [int(v) for t, v in pop_data.items() if t >= cur_hour_str]
        precip_prob = max(remaining_pops) if remaining_pops else 0

        # 강수 시간대 (PTY: 1=비, 2=비/눈, 3=눈, 4=소나기, 현재 이후)
        pty_data = fcst.get("PTY", {})
        rain_windows, in_rain, start_t = [], False, None
        for t in sorted(pty_data):
            if t < cur_hour_str:
                continue
            if int(pty_data[t]) != 0:
                if not in_rain:
                    in_rain, start_t = True, f"{t[:2]}:{t[2:]}"
            elif in_rain:
                rain_windows.append(f"{start_t}~{t[:2]}:{t[2:]}")
                in_rain = False
        if in_rain and start_t:
            rain_windows.append(f"{start_t}~24:00")

        # 일 강수량 합산 (PCP: "강수없음" / "1.0mm 미만" / "5.0mm" 등 혼합)
        precip_sum = sum(
            float(m.group())
            for v in fcst.get("PCP", {}).values()
            if "강수없음" not in str(v)
            for m in [re.search(r"[\d.]+", str(v))] if m
        )

        # 최대 풍속 (WSD: m/s → km/h)
        wsd_data = fcst.get("WSD", {})
        wind_max = max((float(v) for v in wsd_data.values()), default=0) * 3.6

        # 기상 특보
        alerts = []
        if wind_max >= 75:
            alerts.append(f"🚨 강풍경보 (최대풍속 {wind_max:.0f}km/h)")
        elif wind_max >= 50:
            alerts.append(f"⚠️ 강풍주의보 (최대풍속 {wind_max:.0f}km/h)")
        if precip_sum >= 90:
            alerts.append(f"🚨 호우경보 (예상강수 {precip_sum:.0f}mm)")
        elif precip_sum >= 60:
            alerts.append(f"⚠️ 호우주의보 (예상강수 {precip_sum:.0f}mm)")

        print(f"  기상청: {cur_temp}°C  강수확률={precip_prob}%  강수시간대={rain_windows or '없음'}")
        return {
            "cur_temp":     cur_temp,
            "max_temp":     max_temp,
            "min_temp":     min_temp,
            "precip_prob":  precip_prob,
            "precip_hours": sum(1 for v in pty_data.values() if int(v) != 0),
            "precip_sum":   precip_sum,
            "wind_max":     wind_max,
            "rain_windows": rain_windows,
            "alerts":       alerts,
        }
    except Exception as e:
        print(f"[경고] 기상청 날씨 조회 실패: {e}")
        return None

def _get_weather_openmeteo():
    """Open-Meteo 폴백 (기상청 API 실패 시)"""
    try:
        wr = requests.get(
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=37.5641&longitude=126.9979"
            "&models=best_match"
            "&daily=temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,precipitation_hours,"
            "precipitation_sum,windspeed_10m_max,weathercode"
            "&hourly=precipitation_probability"
            "&current=temperature_2m,weathercode"
            "&timezone=Asia%2FSeoul&forecast_days=1",
            timeout=10,
        ).json()
        daily   = wr["daily"]
        hourly  = wr.get("hourly", {})
        current = wr["current"]
        h_probs = hourly.get("precipitation_probability", [])
        h_times = hourly.get("time", [])
        cur_hour = NOW.hour

        rain_windows, in_rain, start_h = [], False, None
        for t, p in zip(h_times, h_probs):
            try:
                h = int(t[11:13])
            except (ValueError, IndexError):
                continue
            if h < cur_hour:
                continue
            if p is not None and p > 50:
                if not in_rain:
                    in_rain, start_h = True, t[11:16]
            elif in_rain:
                rain_windows.append(f"{start_h}~{t[11:16]}")
                in_rain = False
        if in_rain and start_h:
            rain_windows.append(f"{start_h}~24:00")

        remaining = [p for t, p in zip(h_times, h_probs) if p is not None and len(t) >= 13 and int(t[11:13]) >= cur_hour]
        precip_prob = max(remaining) if remaining else daily["precipitation_probability_max"][0]
        wind_max   = daily["windspeed_10m_max"][0]
        precip_sum = daily["precipitation_sum"][0]

        alerts = []
        if wind_max >= 75:
            alerts.append(f"🚨 강풍경보 (최대풍속 {wind_max:.0f}km/h)")
        elif wind_max >= 50:
            alerts.append(f"⚠️ 강풍주의보 (최대풍속 {wind_max:.0f}km/h)")
        if precip_sum >= 90:
            alerts.append(f"🚨 호우경보 (예상강수 {precip_sum:.0f}mm)")
        elif precip_sum >= 60:
            alerts.append(f"⚠️ 호우주의보 (예상강수 {precip_sum:.0f}mm)")
        if daily["weathercode"][0] >= 95:
            alerts.append("⛈️ 뇌우 예보")

        print("  Open-Meteo 날씨 폴백 사용")
        return {
            "cur_temp":     current["temperature_2m"],
            "max_temp":     daily["temperature_2m_max"][0],
            "min_temp":     daily["temperature_2m_min"][0],
            "precip_prob":  precip_prob,
            "precip_hours": daily["precipitation_hours"][0],
            "precip_sum":   precip_sum,
            "wind_max":     wind_max,
            "rain_windows": rain_windows,
            "alerts":       alerts,
        }
    except Exception as e:
        print(f"[경고] Open-Meteo 날씨 조회 실패: {e}")
        return None

def _get_aqi_airkorea():
    """에어코리아 실시간 측정소 데이터 — 서울 중구"""
    if not AIRKOREA_KEY:
        return None, None
    try:
        ar = requests.get(
            "http://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMsrstnAcctoRltmMesureDnsty",
            params={
                "serviceKey": AIRKOREA_KEY,
                "returnType": "json",
                "numOfRows": 1, "pageNo": 1,
                "stationName": "중구",
                "dataTerm": "DAILY", "ver": "1.3",
            },
            timeout=10,
        )
        it   = ar.json()["response"]["body"]["items"][0]
        pm10 = float(it["pm10Value"]) if it.get("pm10Value") not in (None, "-", "") else None
        pm25 = float(it["pm25Value"]) if it.get("pm25Value") not in (None, "-", "") else None
        print(f"  에어코리아: PM10={pm10} PM2.5={pm25}")
        return pm10, pm25
    except Exception as e:
        print(f"[경고] 에어코리아 조회 실패: {e}")
        return None, None

def _get_aqi_aqicn():
    """AQICN 서울 관측소 폴백"""
    try:
        token = os.getenv("AQICN_TOKEN", "demo")
        aqicn = requests.get(f"https://api.waqi.info/feed/seoul/?token={token}", timeout=10).json()
        if aqicn.get("status") == "ok":
            iaqi = aqicn["data"].get("iaqi", {})
            pm10 = iaqi.get("pm10", {}).get("v")
            pm25 = iaqi.get("pm25", {}).get("v")
            print(f"  AQICN 폴백: PM10={pm10} PM2.5={pm25}")
            return pm10, pm25
    except Exception as e:
        print(f"[경고] AQICN 조회 실패: {e}")
    return None, None

def _get_aqi_openmeteo():
    """Open-Meteo CAMS 폴백 (모델 예측값)"""
    try:
        aqr = requests.get(
            "https://air-quality-api.open-meteo.com/v1/air-quality"
            "?latitude=37.5641&longitude=126.9979&current=pm10,pm2_5&timezone=Asia%2FSeoul",
            timeout=10,
        ).json()
        pm10 = aqr["current"].get("pm10")
        pm25 = aqr["current"].get("pm2_5")
        print(f"  Open-Meteo AQI 폴백: PM10={pm10} PM2.5={pm25}")
        return pm10, pm25
    except Exception as e:
        print(f"[경고] Open-Meteo AQI 조회 실패: {e}")
    return None, None

def get_weather():
    w = _get_weather_kma() or _get_weather_openmeteo()
    if w is None:
        return None

    pm10, pm25 = _get_aqi_airkorea()
    if pm10 is None and pm25 is None:
        pm10, pm25 = _get_aqi_aqicn()
    if pm10 is None and pm25 is None:
        pm10, pm25 = _get_aqi_openmeteo()

    w["pm10"]       = pm10
    w["pm10_grade"] = _grade(pm10, [30, 80, 150])
    w["pm25"]       = pm25
    w["pm25_grade"] = _grade(pm25, [15, 35, 75])
    return w

weather = get_weather()
print(f"날씨: {'OK' if weather else 'FAIL'}")

# ── 7. 텔레그램 메시지 생성 ───────────────────────────────────
def fmt_market(m):
    arrow = "▲" if m["change"] >= 0 else "▼"
    price = f"{m['close']:,.2f}" if m["close"] < 100000 else f"{m['close']:,.0f}"
    chg   = f"{abs(m['change']):,.2f}" if abs(m['change']) < 100 else f"{abs(m['change']):,.0f}"
    unit  = f" {m['unit']}" if m.get("unit") else ""
    return f"{m['name']:6s} {price}{unit}  {arrow} {chg} ({m['change_pct']:+.2f}%)"

def build_message():
    lines = [f"<b>📅 아침 브리핑 — {TODAY_DISPLAY} ({WEEKDAY}요일)</b>\n"]

    # 증시
    lines.append("<b>📈 미국 증시 마감 (현지 기준)</b>")
    if markets:
        for m in markets:
            lines.append(f"  {fmt_market(m)}")
    else:
        lines.append("  데이터 조회 실패")

    # Fear & Greed Index
    if fear_greed:
        fg = fear_greed
        src = f"  ({fg['source']})" if fg.get("source") != "CNN" else ""
        lines.append(f"\n<b>🔥 공포&amp;탐욕 지수{src}</b>")
        lines.append(f"  {fg['emoji']} {fg['score']} / 100  —  {fg['rating_ko']} ({fg['rating']})")

    # 증시 뉴스
    lines.append("\n<b>📰 미국 증시 뉴스 TOP5</b>")
    if stock_news:
        for i, n in enumerate(stock_news, 1):
            lines.append(f"  {i}. {html.escape(n['title_ko'])}")
            lines.append(f"     [{n['source']}]")
    else:
        lines.append("  뉴스 없음")

    # 반도체 뉴스
    lines.append("\n<b>⚙️ 반도체 뉴스 TOP5</b>")
    if semi_news:
        for i, n in enumerate(semi_news, 1):
            lines.append(f"  {i}. {html.escape(n['title_ko'])}")
            lines.append(f"     [{n['source']}]")
    else:
        lines.append("  뉴스 없음")

    # 캘린더
    lines.append("\n<b>📆 오늘 일정</b>")
    if events:
        for e in events[:5]:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            lines.append(f"  - {html.escape(e.get('summary', '(제목 없음)'))} [{start}]")
    else:
        lines.append("  일정 없음")

    # 날씨
    if weather:
        w = weather
        rain_time = "  ".join(w["rain_windows"]) if w["rain_windows"] else "없음"
        precip_text = (
            f"{w['precip_prob']}%  (예상 강수: {w['precip_sum']}mm)"
            if w["precip_sum"] > 0 else f"{w['precip_prob']}%"
        )
        lines.append(
            f"\n<b>🌤 날씨 (서울)</b>\n"
            f"  기온: {w['cur_temp']}°C  (최고 {w['max_temp']}° / 최저 {w['min_temp']}°)\n"
            f"  강수 확률: {precip_text}\n"
            f"  강수 시간대: {rain_time}\n"
            f"  미세먼지: {w['pm10_grade']} / 초미세먼지: {w['pm25_grade']}"
        )
        if w["alerts"]:
            lines.append("  " + "  ".join(w["alerts"]))

    return "\n".join(lines)

# ── 8. 마크다운 저장 ──────────────────────────────────────────
def build_markdown():
    lines = [
        f"# 아침 브리핑 — {TODAY_DISPLAY} ({WEEKDAY}요일)",
        f"> 매일 아침 6시30 자동 생성  |  수집 시각: {NOW.strftime('%Y-%m-%d %H:%M')}",
        "", "---", "", "## 📈 미국 증시 마감", "",
    ]
    for m in markets:
        arrow = "▲" if m["change"] >= 0 else "▼"
        lines.append(f"- **{m['name']}**: {m['close']:,.2f}  {arrow} {abs(m['change']):,.2f} ({m['change_pct']:+.2f}%)")

    if fear_greed:
        fg = fear_greed
        lines += ["", "---", "", "## 😰 Fear & Greed Index", "",
            f"- **{fg['score']} / 100**  {fg['emoji']}  {fg['rating_ko']} ({fg['rating']})",
        ]

    lines += ["", "---", "", "## 📰 미국 증시 뉴스 TOP5", ""]
    for i, n in enumerate(stock_news, 1):
        lines.append(f"{i}. [{n['title_ko']}]({n['link']})  *({n['source']})*")
    if not stock_news:
        lines.append("- 없음")

    lines += ["", "---", "", "## 💾 반도체 뉴스 TOP5", ""]
    for i, n in enumerate(semi_news, 1):
        lines.append(f"{i}. [{n['title_ko']}]({n['link']})  *({n['source']})*")
    if not semi_news:
        lines.append("- 없음")

    if events:
        lines += ["", "---", "", "## 📆 오늘 일정", ""]
        for e in events[:5]:
            start = e["start"].get("dateTime", e["start"].get("date", ""))
            lines.append(f"- {e.get('summary', '(제목 없음)')} `{start}`")

    if weather:
        w = weather
        rain_time = ", ".join(w["rain_windows"]) if w["rain_windows"] else "없음"
        lines += ["", "---", "", "## 🌤 날씨 (서울)", "",
            f"- 현재 기온: **{w['cur_temp']}°C**  (최고 {w['max_temp']}° / 최저 {w['min_temp']}°)",
            f"- 강수 확률: **{w['precip_prob']}%**  예상 강수량: {w['precip_sum']}mm",
            f"- 강수 시간대: {rain_time}",
            f"- 최대 풍속: {w['wind_max']} km/h",
            f"- 미세먼지(PM10): {w['pm10']}㎍/㎥ → **{w['pm10_grade']}**",
            f"- 초미세먼지(PM2.5): {w['pm25']}㎍/㎥ → **{w['pm25_grade']}**",
        ]
        if w["alerts"]:
            lines += ["", "### 🚨 기상 특보"]
            for a in w["alerts"]:
                lines.append(f"- {a}")

    lines += ["", "---", "_이 브리핑은 GitHub Actions + Python으로 자동 생성됩니다._"]
    return "\n".join(lines)

os.makedirs("output", exist_ok=True)
with open("output/결과_아침_브리핑.md", "w", encoding="utf-8") as f:
    f.write(build_markdown())
print("마크다운 저장 완료")

# ── 9. 텔레그램 발송 ─────────────────────────────────────────
msg  = build_message()
resp = requests.post(
    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
    timeout=10,
)
if resp.status_code == 200:
    print("텔레그램 발송 성공!")
    if not FORCE_MODE:
        worksheet.append_row([TODAY_STR, NOW.strftime("%H:%M"), "발송 완료"])
        print(f"시트에 '{TODAY_STR}' 기록 완료")
else:
    print(f"텔레그램 발송 실패: {resp.text}")
    sys.exit(1)

print(f"[{datetime.now(KST).strftime('%H:%M')}] 아침 브리핑 완료")
