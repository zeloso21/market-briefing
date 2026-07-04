#!/usr/bin/env python3
"""
AI 마켓 브리핑 업데이터
cron 자동 실행: 0 8 * * 1-5 /home/user/venv/bin/python3 /home/user/market_briefing/update_market.py
"""

import os
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, 'index.html')


def recent_biz_days(n=10):
    result, d = [], datetime.today() - timedelta(days=1)
    while len(result) < n:
        if d.weekday() < 5:
            result.append(d)
        d -= timedelta(days=1)
    return result


def _fmt_vol(v):
    if v >= 100000000: return f'{v/100000000:.1f}억주'
    if v >= 10000:     return f'{v/10000:.0f}만주'
    return f'{v:,}주'

def _fmt_amt(a):
    if a >= 1000000000000: return f'{a/1000000000000:.1f}조'
    if a >= 100000000:     return f'{a/100000000:.0f}억'
    return f'{a/10000:.0f}만'

def _empty(label, ticker=None):
    d = dict(label=label, value='—', chg='—', pct='—', up=None, date=None, vol=None, amt=None)
    if ticker: d['ticker'] = ticker
    return d


def _make(label, value_str, chg_str, pct_str, up, day, ticker=None, vol=None, amt=None):
    d = dict(label=label, value=value_str, chg=chg_str, pct=pct_str, up=up, date=day, vol=vol, amt=amt)
    if ticker: d['ticker'] = ticker
    return d


def fetch_krx_index(ticker, label):
    try:
        from pykrx import stock
        for day in recent_biz_days():
            fr = (day - timedelta(days=14)).strftime('%Y%m%d')
            to = day.strftime('%Y%m%d')
            df = stock.get_index_ohlcv(fr, to, ticker)
            if df is None or len(df) < 2:
                continue
            close = df['종가'].iloc[-1]
            prev  = df['종가'].iloc[-2]
            chg   = close - prev
            pct   = chg / prev * 100
            return _make(label, f'{close:,.2f}', f'{chg:+,.2f}', f'{pct:+.2f}', chg >= 0, day)
    except Exception as e:
        print(f'  [{label}] 오류: {e}')
    return _empty(label)


def fetch_krx_stock(ticker, label):
    try:
        from pykrx import stock
        for day in recent_biz_days():
            fr = (day - timedelta(days=14)).strftime('%Y%m%d')
            to = day.strftime('%Y%m%d')
            df = stock.get_market_ohlcv(fr, to, ticker)
            if df is None or len(df) < 2:
                continue
            row   = df.iloc[-1]
            close = int(row['종가'])
            prev  = int(df.iloc[-2]['종가'])
            chg   = close - prev
            pct   = chg / prev * 100
            vol_n = int(row['거래량']) if '거래량' in df.columns else 0
            vol   = _fmt_vol(vol_n) if vol_n else None
            amt   = _fmt_amt(vol_n * close) if vol_n else None
            return _make(label, f'{close:,}', f'{chg:+,}', f'{pct:+.2f}', chg >= 0, day, ticker, vol, amt)
    except Exception as e:
        print(f'  [{label}] 오류: {e}')
    return _empty(label, ticker)


def fetch_yf(symbol, label, decimals=2):
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period='7d')
        if hist is None or len(hist) < 2:
            return _empty(label)
        close = float(hist['Close'].iloc[-1])
        prev  = float(hist['Close'].iloc[-2])
        chg   = close - prev
        pct   = chg / prev * 100
        fmt   = f',.{decimals}f'
        day   = hist.index[-1].to_pydatetime().replace(tzinfo=None)
        return _make(label, format(close, fmt), format(chg, f'+{fmt}'), f'{pct:+.2f}', chg >= 0, day)
    except Exception as e:
        print(f'  [{label}] 오류: {e}')
    return _empty(label)


def _chg_html(item):
    if item['value'] == '—':
        return '<span class="neutral">—</span><span class="neutral">—</span>'
    cls = 'up' if item['up'] else 'down'
    arr = '▲' if item['up'] else '▼'
    return (f'<span class="{cls}">{arr} {item["chg"]}</span>'
            f'<span class="{cls}">{item["pct"]}%</span>')


def _idx_card(item):
    cls = 'up' if item['up'] else ('down' if item['up'] is False else 'neutral')
    return f'''
        <div class="card">
          <div class="card-top">
            <span class="label">{item['label']}</span>
            <div class="chg-row">{_chg_html(item)}</div>
          </div>
          <div class="val {cls}">{item['value']}</div>
        </div>'''


def _stk_card(item):
    cls = 'up' if item['up'] else ('down' if item['up'] is False else 'neutral')
    vol_amt = ''
    if item.get('vol') or item.get('amt'):
        parts = []
        if item.get('vol'): parts.append(f'거래량 {item["vol"]}')
        if item.get('amt'): parts.append(f'거래대금 {item["amt"]}')
        vol_amt = f'<div class="vol-amt">{" &nbsp;|&nbsp; ".join(parts)}</div>'
    return f'''
        <div class="card">
          <div class="card-top">
            <span class="label">{item['label']}</span>
            <div class="chg-row">{_chg_html(item)}</div>
          </div>
          <div class="val {cls}">{item['value']}</div>
          <div class="ticker">{item.get('ticker', '')}</div>
          {vol_amt}
        </div>'''


def build_html(indices, stocks):
    now = datetime.now().strftime('%Y.%m.%d %H:%M')
    all_dates = [x['date'] for x in indices + stocks if x['date']]
    data_date = max(all_dates).strftime('%Y.%m.%d') if all_dates else '—'
    idx_html = ''.join(_idx_card(i) for i in indices)
    stk_html = ''.join(_stk_card(s) for s in stocks)

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 마켓 브리핑</title>
<style>
*, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
  background: #f0f3ef;
  min-height: 100vh;
  color: #111;
}}
.header {{
  background: linear-gradient(160deg, #0b4d2e 0%, #145d39 100%);
  padding: 28px 40px 0;
  color: #fff;
}}
.badge {{
  font-size: 12px;
  color: #82c49c;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 5px;
}}
.h-title {{ font-size: 32px; font-weight: 800; letter-spacing: -1px; margin-bottom: 20px; }}
.update-bar {{
  background: #fff;
  border-radius: 10px 10px 0 0;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: 14px;
  color: #145d39;
  font-weight: 600;
}}
.update-bar .meta {{ font-size: 12px; color: #888; font-weight: 400; margin-left: 8px; }}
.body {{
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 20px 48px;
}}
.sec-head {{
  font-size: 15px;
  font-weight: 700;
  color: #222;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}}
.grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 32px;
}}
.card {{
  background: #fff;
  border-radius: 10px;
  border: 1px solid #dde4d8;
  padding: 17px 20px 15px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  transition: box-shadow .15s ease;
}}
.card:hover {{ box-shadow: 0 5px 16px rgba(0,0,0,0.09); }}
.card-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}}
.label   {{ font-size: 13px; color: #777; font-weight: 500; }}
.chg-row {{ display: flex; gap: 7px; font-size: 12px; font-weight: 600; }}
.val     {{ font-size: 26px; font-weight: 800; letter-spacing: -1px; color: #111; }}
.ticker  {{ font-size: 11px; color: #bbb; margin-top: 6px; }}
.vol-amt {{ font-size: 11px; color: #999; margin-top: 5px; }}
.up      {{ color: #c62828; }}
.down    {{ color: #1565c0; }}
.neutral {{ color: #ccc; }}
</style>
</head>
<body>
<div class="header">
  <div class="badge">✦ 하나증권 WM기획실 · AI 시황 에이전트</div>
  <div class="h-title">AI 마켓 브리핑</div>
  <div class="update-bar">
    <span>✦ AI 시황 업데이트 완료</span>
    <span class="meta">기준: {data_date} &nbsp;|&nbsp; 갱신: {now}</span>
  </div>
</div>
<div class="body">
  <div class="sec-head">🏦 주요 지수</div>
  <div class="grid">{idx_html}</div>
  <div class="sec-head">📈 관심 종목</div>
  <div class="grid">{stk_html}</div>
</div>
</body>
</html>'''


def main():
    print(f'AI 마켓 브리핑 업데이터 — {datetime.now():%Y-%m-%d %H:%M:%S}')

    print('\n[주요 지수]')
    indices = [
        fetch_yf('^KS11',    '코스피',       decimals=2),
        fetch_yf('^KQ11',    '코스닥',       decimals=2),
        fetch_yf('USDKRW=X', '원/달러 환율', decimals=1),
        fetch_yf('^GSPC',    'S&P 500'),
        fetch_yf('^IXIC',    '나스닥종합'),
        fetch_yf('^N225',    '닛케이225'),
    ]
    for x in indices:
        v = f'{x["value"]}  ({x["chg"]}, {x["pct"]}%)' if x['value'] != '—' else '데이터 없음'
        print(f'  {x["label"]:14s} {v}')

    print('\n[관심 종목]')
    stocks = [
        fetch_krx_stock('005930', '삼성전자'),
        fetch_krx_stock('000660', 'SK하이닉스'),
        fetch_krx_stock('214370', '케어젠'),
    ]
    for x in stocks:
        v = f'{x["value"]}원  ({x["chg"]}, {x["pct"]}%)' if x['value'] != '—' else '데이터 없음'
        print(f'  {x["label"]:14s} {v}')

    html = build_html(indices, stocks)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'\n✅ 저장: {OUTPUT_PATH}')

    # git push (GitHub Pages 자동 업데이트)
    git_dir = SCRIPT_DIR
    try:
        import subprocess
        result = subprocess.run(['git', '-C', git_dir, 'remote', 'get-url', 'origin'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            today = datetime.now().strftime('%Y-%m-%d')
            subprocess.run(['git', '-C', git_dir, 'add', 'index.html'], check=True)
            subprocess.run(['git', '-C', git_dir, 'commit', '-m', f'Update {today}'],
                           capture_output=True)
            subprocess.run(['git', '-C', git_dir, 'push'], check=True, capture_output=True)
            print('   GitHub Pages 업데이트 완료')
    except Exception as e:
        print(f'   git push 생략: {e}')


if __name__ == '__main__':
    main()
