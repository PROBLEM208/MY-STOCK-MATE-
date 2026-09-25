import streamlit as st
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib.parse
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 페이지 기본 설정 (와이드 레이아웃 적용)
st.set_page_config(
    page_title="MY STOCK MATE (MSM)",
    page_icon="📈",
    layout="wide"
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
    
    kr_presets = {
        "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "LG에너지솔루션": "373220.KS",
        "현대차": "005380.KS", "NAVER": "035420.KS", "네이버": "035420.KS",
        "카카오": "035720.KS", "알테오젠": "196170.KQ", "에코프로비엠": "247540.KQ"
    }
    if query_clean in kr_presets:
        return kr_presets[query_clean]
        
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
    """구글 뉴스 RSS 피드를 이용한 최신 뉴스 및 링크 가져오기"""
    try:
        encoded_query = urllib.parse.quote(f"{stock_name} 주식")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'xml')
        
        items = soup.find_all('item')
        
        news_list = []
        titles = []
        for item in items[:5]:
            title_text = item.title.text if item.title else ""
            link_url = item.link.text if item.link else "#"
            if title_text:
                news_list.append({"title": title_text, "link": link_url})
                titles.append(title_text)
        
        if not news_list:
            return [{"title": "최근 관련 뉴스를 찾을 수 없습니다.", "link": "#"}], 0
        
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
                
        return news_list, score
    except Exception:
        return [{"title": "뉴스 데이터를 불러오는 중 오류가 발생했습니다.", "link": "#"}], 0

# --- 차트용 데이터 계산 함수 (1년치 수집) ---
def fetch_chart_data(ticker_symbol):
    """yfinance를 통한 차트 지표 및 거래량 계산"""
    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        df = ticker_obj.history(period="1y")
        
        if df.empty:
            return None
        
        # 이동평균선
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 거래량 이동평균
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

stock_input = st.text_input("🏢 기업 이름 또는 종목 티커 입력", value="삼성전자", help="예: 삼성전자, 애플, AAPL, Tesla 등")

st.markdown("---")

if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

if st.button("📊 MSM 정밀 분석 시작하기", use_container_width=True):
    with st.spinner("티커 검색, 실시간 시세, 뉴스 및 거래량을 분석 중입니다..."):
        found_ticker = search_ticker(stock_input)
        if not found_ticker:
            found_ticker = stock_input.strip().upper()
            
        chart_data = fetch_chart_data(found_ticker)
        news_list, news_score = fetch_news_score(stock_input.strip())
        
        if chart_data is None:
            st.session_state.analyzed = False
            st.error("❌ 종목 데이터를 불러올 수 없습니다. 기업 이름을 정확히 입력하거나 티커(예: 005930.KS, AAPL)로 직접 입력해 주세요.")
        else:
            st.session_state.analyzed = True
            st.session_state.chart_data = chart_data
            st.session_state.news_list = news_list
            st.session_state.news_score = news_score
            st.session_state.stock_name = stock_input
            st.session_state.ticker = found_ticker

if st.session_state.get("analyzed", False):
    chart_data = st.session_state.chart_data
    news_list = st.session_state.news_list
    news_score = st.session_state.news_score
    curr_stock_name = st.session_state.stock_name
    curr_ticker = st.session_state.ticker

    st.subheader(f"📊 [{curr_stock_name}] ({curr_ticker}) 분석 결과")
    
    price = chart_data['price']
    ma20 = chart_data['ma20']
    rsi = chart_data['rsi']
    vol_ratio = chart_data['vol_ratio']
    
    is_kor = curr_ticker.endswith(".KS") or curr_ticker.endswith(".KQ")
    exchange_rate = get_exchange_rate()
    
    if is_kor:
        price_display = f"{price:,.0f}원"
        ma20_display = f"20일선: {ma20:,.0f}원"
    else:
        price_krw = price * exchange_rate
        price_display = f"${price:,.2f} (약 {price_krw:,.0f}원)"
        ma20_display = f"20일선: ${ma20:,.2f}"
    
    if news_score > 0:
        news_text = f"긍정 우세 (+{news_score:.1f})"
        news_delta = "호재 기사 우세"
    elif news_score < 0:
        news_text = f"부정 우세 ({news_score:.1f})"
        news_delta = "악재 기사 주의"
    else:
        news_text = "중립 (0.0)"
        news_delta = "특이 기사 없음"
        
    vol_delta = f"평균 대비 {vol_ratio:.0f}%"
    if vol_ratio >= 150:
        vol_status = "🔥 급증"
    elif vol_ratio <= 50:
        vol_status = "🧊 소외"
    else:
        vol_status = "➡️ 보통"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재가", price_display, ma20_display)
    m2.metric("뉴스 분위기", news_text, news_delta)
    m3.metric("RSI (과열도)", f"{rsi:.1f}", "70이상 과열 / 30이하 과매도")
    m4.metric("거래량 분석", vol_status, vol_delta)
    
    st.markdown("---")
    
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
        
    st.markdown("### 📈 XM 스타일 프로 트레이딩 차트")
    show_chart = st.toggle("차트 화면 표시하기", value=True)
    
    if show_chart:
        df = chart_data['df']
        
        # 2단 서브플롯 생성 (1단: 캔들+이동평균선+거래량 / 2단: RSI 보조지표)
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.75, 0.25],
            specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
        )
        
        # 1. 메인 캔들스틱 차트 (양봉: 빨강 / 음봉: 파랑)
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
            name="OHLC", increasing_line_color='#FF3B30', decreasing_line_color='#007AFF'
        ), row=1, col=1, secondary_y=False)
        
        # 이동평균선 오버레이 (5일선, 20일선, 60일선)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA5'], mode='lines', name="5일선", line=dict(color='#FFCC00', width=1)), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], mode='lines', name="20일선", line=dict(color='#FF9500', width=1.5)), row=1, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA60'], mode='lines', name="60일선", line=dict(color='#AF52DE', width=1.5)), row=1, col=1, secondary_y=False)
        
        # 거래량 바 차트 (우측 Y축 활용)
        colors = ['#FF3B30' if c >= o else '#007AFF' for c, o in zip(df['Close'], df['Open'])]
        fig.add_trace(go.Bar(
            x=df.index, y=df['Volume'], name="거래량", marker_color=colors, opacity=0.3
        ), row=1, col=1, secondary_y=True)
        
        # 2. 보조지표 패널: RSI
        fig.add_trace(go.Scatter(
            x=df.index, y=df['RSI'], mode='lines', name="RSI", line=dict(color='#34C759', width=1.5)
        ), row=2, col=1)
        
        # RSI 70/30 과열/과매도 가이드라인
        fig.add_hline(y=70, line_dash="dash", line_color="#FF3B30", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#007AFF", row=2, col=1)
        
        # XM 스타일 다크 테마 및 기간 선택(Range Selector) / 확대축소 설정
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#131722",
            plot_bgcolor="#131722",
            height=550,
            margin=dict(l=10, r=10, t=30, b=10),
            dragmode="pan",  # 마우스/손가락 드래그로 자유롭게 이동
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1)
        )
        
        # 기간 선택 퀵 버튼 및 하단 슬라이더 추가
        fig.update_xaxes(
            rangeslider_visible=True,
            rangeslider_thickness=0.08,
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1개월", step="month", stepmode="backward"),
                    dict(count=3, label="3개월", step="month", stepmode="backward"),
                    dict(count=6, label="6개월", step="month", stepmode="backward"),
                    dict(count=1, label="1년", step="year", stepmode="backward"),
                    dict(label="전체", step="all")
                ]),
                font=dict(color="#FFFFFF"),
                bgcolor="#2A2E39",
                activecolor="#2962FF"
            ),
            row=2, col=1
        )
        
        # 거래량 Y축 레이아웃 숨김 처리 (캔들 차트와 중첩 방지)
        fig.update_yaxes(showgrid=False, secondary_y=True, row=1, col=1)
        
        # 차트 출력 (휠 스크롤 줌 및 모바일 제스처 확대를 허용)
        st.plotly_chart(
            fig, 
            use_container_width=True, 
            config={
                'scrollZoom': True,          # 마우스 휠 및 두 손가락으로 확대/축소 가능
                'displayModeBar': True,       # 우측 상단 상호작용 툴바 표시
                'modeBarButtonsToRemove': []
            }
        )
        
    with st.expander("📰 분석에 반영된 최근 뉴스 보기 (클릭 시 기사로 이동)", expanded=True):
        for i, item in enumerate(news_list, 1):
            if item['link'] != "#":
                st.markdown(f"{i}. [{item['title']}]({item['link']})")
            else:
                st.write(f"{i}. {item['title']}")
                
    stop_loss = ma20 * 0.97
    if is_kor:
        stop_loss_str = f"{stop_loss:,.0f}원"
    else:
        stop_loss_str = f"${stop_loss:,.2f} (약 {stop_loss * exchange_rate:,.0f}원)"
        
    st.caption(f"🛡️ **[위험 관리 기준]:** 20일선 -3% 이탈 지점인 **{stop_loss_str}** 부근을 참고 손절선으로 제시합니다.")
