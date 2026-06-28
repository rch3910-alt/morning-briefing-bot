# -*- coding: utf-8 -*-
import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import progress

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv("input/.env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print("=" * 50)
print("[4단계] 브리핑 마크다운 생성 & 텔레그램 발송")
print("=" * 50)

# ── 수집 데이터 로드 ───────────────────────────────────────────
with open("output/collected_data.json", encoding="utf-8") as f:
    data = json.load(f)

nasdaq = data.get("nasdaq")
stock_news = data.get("stock_news", [])
semi_news = data.get("semi_news", [])
weather = data.get("weather")
collected_at = data.get("collected_at", "")

KST = timezone(timedelta(hours=9))
today = datetime.now(KST).strftime("%Y년 %m월 %d일")
weekday = ["월", "화", "수", "목", "금", "토", "일"][datetime.now(KST).weekday()]

# ── 마크다운 브리핑 생성 ──────────────────────────────────────
def build_markdown():
    lines = [
        f"# 아침 브리핑 — {today} ({weekday}요일)",
        f"> 매일 아침 6시30 자동 생성  |  수집 시각: {collected_at}",
        "",
        "---",
        "",
        "## 📈 증시",
    ]

    if nasdaq:
        arrow = "▲" if nasdaq["change"] >= 0 else "▼"
        sign = "+" if nasdaq["change"] >= 0 else ""
        lines += [
            f"**{nasdaq['index']}** ({nasdaq['date']})",
            f"- 종가: **{nasdaq['close']:,.2f}**  {arrow} {abs(nasdaq['change']):,.2f} ({sign}{nasdaq['change_pct']:.2f}%)",
        ]
    else:
        lines.append("- 데이터 조회 실패")

    lines += ["", "---", "", "## 📰 증시 이슈 뉴스 TOP5", ""]
    for i, n in enumerate(stock_news, 1):
        lines.append(f"{i}. [{n['title']}]({n['link']})")
    if not stock_news:
        lines.append("- 뉴스 없음")

    lines += ["", "---", "", "## 💾 반도체 섹터 뉴스 TOP3", ""]
    for i, n in enumerate(semi_news, 1):
        lines.append(f"{i}. [{n['title']}]({n['link']})")
    if not semi_news:
        lines.append("- 뉴스 없음")

    lines += ["", "---", "", "## 🌤 오늘 날씨 (서울)", ""]
    if weather:
        precip_text = f"{weather['precip_hours']}시간" if weather['precip_hours'] > 0 else "없음"
        lines += [
            f"- 현재 기온: **{weather['cur_temp']}°C**  (최고 {weather['max_temp']}°C / 최저 {weather['min_temp']}°C)",
            f"- 강수 확률: **{weather['precip_prob']}%**  강수 시간: {precip_text}",
            f"- 미세먼지(PM10): {weather['pm10']}㎍/㎥ → **{weather['pm10_grade']}**",
            f"- 초미세먼지(PM2.5): {weather['pm25']}㎍/㎥ → **{weather['pm25_grade']}**",
        ]
    else:
        lines.append("- 날씨 데이터 조회 실패")

    lines += ["", "---", "", "_이 브리핑은 GitHub Actions + Python으로 자동 생성됩니다._"]
    return "\n".join(lines)

md_content = build_markdown()

os.makedirs("output", exist_ok=True)
with open("output/결과_아침_브리핑.md", "w", encoding="utf-8") as f:
    f.write(md_content)
print("마크다운 저장 완료: output/결과_아침_브리핑.md")

# ── 텔레그램 발송용 텍스트 생성 ──────────────────────────────
def build_telegram_msg(is_test=False):
    prefix = "[TEST] " if is_test else ""
    arrow_n = "▲" if nasdaq and nasdaq["change"] >= 0 else "▼"

    nasdaq_line = (
        f"나스닥: {nasdaq['close']:,.2f}  {arrow_n} {abs(nasdaq['change']):,.2f} ({nasdaq['change_pct']:+.2f}%)"
        if nasdaq else "나스닥: 조회 실패"
    )

    news_lines = "\n".join(
        f"  {i}. {n['title']}" for i, n in enumerate(stock_news[:5], 1)
    ) or "  뉴스 없음"

    semi_lines = "\n".join(
        f"  {i}. {n['title']}" for i, n in enumerate(semi_news[:3], 1)
    ) or "  뉴스 없음"

    weather_lines = (
        f"  기온: {weather['cur_temp']}°C (최고 {weather['max_temp']}° / 최저 {weather['min_temp']}°)\n"
        f"  강수 확률: {weather['precip_prob']}%\n"
        f"  미세먼지: {weather['pm10_grade']} / 초미세먼지: {weather['pm25_grade']}"
        if weather else "  날씨 조회 실패"
    )

    return (
        f"{prefix}아침 브리핑 시스템 테스트 발송\n"
        f"📅 {today} ({weekday}요일)\n"
        f"{'='*30}\n\n"
        f"📈 증시\n{nasdaq_line}\n\n"
        f"📰 증시 뉴스 TOP5\n{news_lines}\n\n"
        f"💾 반도체 뉴스 TOP3\n{semi_lines}\n\n"
        f"🌤 날씨 (서울)\n{weather_lines}"
    )

# ── 텔레그램 발송 ────────────────────────────────────────────
def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    return resp.status_code == 200, resp.text

msg = build_telegram_msg(is_test=True)
ok, resp_text = send_telegram(msg)
if ok:
    print("텔레그램 테스트 발송 성공!")
else:
    print(f"텔레그램 발송 실패: {resp_text}")

progress.save(4, "4단계 완료")
print("\n4단계 완료!")
