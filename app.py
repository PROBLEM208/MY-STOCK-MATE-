import streamlit as st
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib.parse
import plotly.graph_objects as go

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="MY STOCK MATE (MSM)",
    page_icon="📈",
    layout="centered"
)

# --- 기능 1: 실시간 환율 수집 (USD/KRW) ---
@st.cache_data(ttl=3600)
def get_exchange_rate():
    """미국 달러 환율 정보 수집 (기본값: 1,350원)"""
    try:
        usd_krw = yf.Ticker("KRW=X").history(period="1d")
        if not usd_krw.empty:
            return float(usd_krw['Close'].iloc[-1])
        return 1350.0
    except Exception:
        return 1350.0

# --- 기능 2: 기업 이름 기반 티커 자동 검색 ---
def search_ticker(query):
    """기업 이름을 기반으로 한국/미국 주식 티커 자동 검색"""
    query_clean = query.strip()
    
    # 한국 대표 종목 매핑 사전
    kr_presets = {
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "LG에너지솔루션": "373220.KS",
        "현대차": "005380.KS", "NAVER": "035420.KS", "네이버": "035420.KS",
        "카카오": "035720.KS", "알테오젠": "196170.KQ", "에코프로비엠": "247540.KQ"
    }
    if query_clean in kr_presets:
        return kr_presets[query_clean]
        
    # 야후 파이낸스 자동 검색 API 활용
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query_clean)}&quotesCount=5"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5).json()
        quotes = res.get('quotes', [])
        if quotes:
            return quotes[0]['symbol']
    except Exception:
        pass
        
    return None

# --- 뉴스 수집 및 감성 분석 ---
def fetch_news_score(stock_name):
    """구글 뉴스 RSS 피드를 이용한 최신 뉴스 분석"""
    try:
        encoded_query = urllib.parse.quote(f"{stock_name} 주식")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'xml')
        
        items = soup.find_all('item')
        titles = [item.title.text for item in items[:5] if item.title]
        
        if not titles:
            return ["최근 관련 뉴스를 찾을 수 없습니다."], 0
        
        pos_keywords = ['상승', '호재', '실적', '흑자', '수주', '돌파', '신고가', '매수', '급등', '목표가 상향']
        neg_keywords = ['하락', '악재', '적자', '급락', '위기', '손실', '우려', '매도', '목표가 하향']
        reverse_words = ['멈춰', '극복', '탈출', '반등', '해소']
        
        score = 0
        for title in titles:
            has_reverse = any(rw in title for rw in reverse_words)
            for pk in pos_keywords:
                if pk in title: score += 1.5
            for nk in neg_keywords:
                if nk in title and not has_reverse: score -= 1.5
                
        return titles, score
    except Exception:
        return ["뉴스 데이터를 불러오는 중 오류가 발생했습니다."], 0

# --- 기능 3: 거래량 분석 및 차트 데이터 계산 ---
def fetch_chart_data(ticker_symbol):
    """yfinance를 통한 차트 지표 및 거래량 계산"""
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        df = ticker_obj.history(period="6mo")
        
        if df.empty:
            return None
        
        # 20일 이동평균선
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        # RSI (14일)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 거래량 분석 (최근 5일 평균 대비 당일 거래량 비율)
        df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
        latest = df.iloc[-1]
        
        vol_ratio = (latest['Volume'] / latest['Vol_MA5']) * 100 if latest['Vol_MA5'] > 0 else 100
        
        return {
            "price": float(latest['Close']),
            "ma20": float(latest['MA20']),
            "rsi": float(latest['RSI']),
            "vol_ratio": float(vol_ratio),
            "df": df
        }
    except Exception:
        return None

# --- UI 레이아웃 구성 ---
st.title("📈 MY STOCK MATE (MSM)")
st.caption("내 손안의 스마트 AI 주식 분석 비서")
st.divider()

# 사용자 입력창 (기업 이름만 입력해도 가능)
stock_input = st.text_input("🏢 기업 이름 또는 종목 티커 입력", value="삼성전자", help="예: 삼성전자, 애플, AAPL, Tesla 등")

st.markdown("---")

# 세션 상태 초기화
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# 분석 시작 버튼
if st.button("📊 MSM 정밀 분석 시작하기", use_container_width=True):
    with st.spinner("티커 검색, 실시간 시세, 뉴스 및 거래량을 분석 중입니다..."):
        # 1. 티커 검색
        found_ticker = search_ticker(stock_input)
        if not found_ticker:
            found_ticker = stock_input.strip().upper()
            
        chart_data = fetch_chart_data(found_ticker)
        news_titles, news_score = fetch_news_score(stock_input.strip())
        
        if chart_data is None:
            st.session_state.analyzed = False
            st.error("❌ 종목 데이터를 불러올 수 없습니다. 기업 이름을 정확히 입력하거나 티커(예: 005930.KS, AAPL)로 직접 입력해 주세요.")
        else:
            st.session_state.analyzed = True
            st.session_state.chart_data = chart_data
            st.session_state.news_titles = news_titles
            st.session_state.news_score = news_score
            st.session_state.stock_name = stock_input
            st.session_state.ticker = found_ticker

# 분석 결과 출력
if st.session_state.get("analyzed", False):
    chart_data = st.session_state.chart_data
    news_titles = st.session_state.news_titles
    news_score = st.session_state.news_score
    curr_stock_name = st.session_state.stock_name
    curr_ticker = st.session_state.ticker

    st.subheader(f"📊 [{curr_stock_name}] ({curr_ticker}) 분석 결과")
    
    price = chart_data['price']
    ma20 = chart_data['ma20']
    rsi = chart_data['rsi']
    vol_ratio = chart_data['vol_ratio']
    
    # 한국 / 미국 주식 구분 및 환율 계산
    is_kor = curr_ticker.endswith(".KS") or curr_ticker.endswith(".KQ")
    exchange_rate = get_exchange_rate()
    
    if is_kor:
        price_display = f"{price:,.0f}원"
        ma20_display = f"20일선: {ma20:,.0f}원"
    else:
        price_krw = price * exchange_rate
        price_display = f"${price:,.2f} (약 {price_krw:,.0f}원)"
        ma20_display = f"20일선: ${ma20:,.2f}"
    
    # 뉴스 점수 텍스트 변환
    if news_score > 0:
        news_text = f"긍정 우세 (+{news_score:.1f})"
        news_delta = "호재 기사 우세"
    elif news_score < 0:
        news_text = f"부정 우세 ({news_score:.1f})"
        news_delta = "악재 기사 주의"
    else:
        news_text = "중립 (0.0)"
        news_delta = "특이 기사 없음"
        
    # 거래량 텍스트 변환
    vol_delta = f"평균 대비 {vol_ratio:.0f}%"
    if vol_ratio >= 150:
        vol_status = "🔥 거래량 급증"
    elif vol_ratio <= 50:
        vol_status = "🧊 거래량 소외"
    else:
        vol_status = "➡️ 평이한 수준"

    # 메트릭 카드를 4개로 배치 (거래량 지표 추가)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재가", price_display, ma20_display)
    m2.metric("뉴스 분위기", news_text, news_delta)
    m3.metric("RSI (과열도)", f"{rsi:.1f}", "70이상 과열 / 30이하 과매도")
    m4.metric("거래량 분석", vol_status, vol_delta)
    
    st.markdown("---")
    
    # 시그널 판정 (거래량 급증 조건 추가 반영)
    if news_score > 0 and price > ma20 and rsi < 70 and vol_ratio >= 130:
        st.success("🔥 **[종합 시그널: 강력 매수 관점]** 호재 뉴스, 20일선 수복, 거래량 급증이 동시 발생하여 상승 동력이 매우 강합니다!")
    elif news_score > 0 and price > ma20 and rsi < 70:
        st.success("✅ **[종합 시그널: 관심 관점]** 뉴스 호재와 함께 20일선 위에 안정적으로 위치해 있습니다.")
    elif rsi >= 70:
        st.warning("⚠️ **[종합 시그널: 단기 과열]** RSI가 과열 구간입니다. 추격 매수에 유의하세요.")
    elif price < ma20:
        st.info("📉 **[종합 시그널: 관망 구간]** 주가가 20일선 밑에 있으므로 추세 전환 확인이 필요합니다.")
    else:
        st.warning("➡️ **[종합 시그널: 중립]** 방향성을 탐색 중인 구간입니다.")
        
    # 차트 설정 및 출력
    st.markdown("### 📈 주가 차트 설정")
    show_chart = st.toggle("차트 화면 표시하기", value=True)
    
    if show_chart:
        chart_type = st.radio(
            "차트 유형 선택:",
            ["📊 캔들스틱 (봉차트)", "📈 종가 선 차트", "🌊 영역 차트"],
            horizontal=True,
            key="selected_chart_type"
        )
        
        df = chart_data['df']
        fig = go.Figure()
        
        if "캔들스틱" in chart_type:
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name="주가", increasing_line_color='red', decreasing_line_color='blue'
            ))
        elif "선 차트" in chart_type:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name="종가", line=dict(color='#1f77b4', width=2)))
        elif "영역 차트" in chart_type:
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', fill='tozeroy', name="종가 영역", line=dict(color='#00CC96')))
        
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], mode='lines', name="20일선", line=dict(color='orange', width=1.5, dash='dash')))
        
        fig.update_layout(
            margin=dict(l=10, r=10, t=10, b=10),
            height=380,
            dragmode=False,
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False})
        
    # 뉴스 및 손절 라인 안내
    with st.expander("📰 분석에 반영된 최근 뉴스 보기", expanded=True):
        for i, t in enumerate(news_titles, 1):
            st.write(f"{i}. {t}")
            
    stop_loss = ma20 * 0.97
    if is_kor:
        stop_loss_str = f"{stop_loss:,.0f}원"
    else:
        stop_loss_str = f"${stop_loss:,.2f} (약 {stop_loss * exchange_rate:,.0f}원)"
        
    st.caption(f"🛡️ **[위험 관리 기준]:** 20일선 -3% 이탈 지점인 **{stop_loss_str}** 부근을 참고 손절선으로 제시합니다.")
