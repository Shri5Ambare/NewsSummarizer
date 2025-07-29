# samachar_plus.py
import streamlit as st
import pandas as pd
import json
from PIL import Image
from bs4 import BeautifulSoup as soup
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
from urllib.error import URLError, HTTPError
from newspaper import Article
from textblob import TextBlob
import io, time, re
from functools import wraps
import logging

# ---------- CONFIG ----------
st.set_page_config(
    page_title="SAMACHAR+ 📰",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- CACHING ----------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_rss(url: str):
    """Fetch RSS with retry & 10 s timeout."""
    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    for attempt in range(3):
        try:
            with urlopen(req, timeout=10) as resp:
                return soup(resp.read(), features='xml')
        except (URLError, HTTPError) as e:
            logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < 2:  # Don't sleep on last attempt
                time.sleep(1.5)
    logger.error(f"Failed to fetch RSS from {url} after 3 attempts")
    return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_top_news():
    """Fetch top/trending news from Google News"""
    xml = fetch_rss("https://news.google.com/news/rss")
    return xml.find_all('item') if xml else []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_category_news(cat: str):
    """Fetch news by category"""
    xml = fetch_rss(f"https://news.google.com/news/rss/headlines/section/topic/{cat.upper()}")
    return xml.find_all('item') if xml else []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_news_search_topic(topic: str):
    """Search news by topic/keyword"""
    xml = fetch_rss(f"https://news.google.com/rss/search?q={quote_plus(topic)}")
    return xml.find_all('item') if xml else []

# ---------- UTILITIES ----------
def fetch_news_poster(poster_link, width=300):
    """Display news image with fallback"""
    if poster_link and poster_link.startswith('http'):
        try:
            with urlopen(poster_link, timeout=5) as response:
                img_data = response.read()
            img = Image.open(io.BytesIO(img_data))
            st.image(img, width=width)
            return
        except Exception as e:
            logger.warning(f"Failed to load image {poster_link}: {e}")
    
    # Fallback placeholder
    st.image("https://via.placeholder.com/300x200?text=No+Image", width=width)

def highlight(text, kw):
    """Highlight keywords in text"""
    if not kw or not text:
        return text
    kw = re.escape(kw.strip())
    return re.sub(f'({kw})', r'**\1**', text, flags=re.IGNORECASE)

def get_sentiment(text):
    """Analyze sentiment of text"""
    if not text:
        return ("😐 Neutral", "gray")
    
    try:
        pol = TextBlob(text).sentiment.polarity
        if pol > 0.15:
            return ("🙂 Positive", "green")
        elif pol < -0.15:
            return ("☹️ Negative", "red")
        else:
            return ("😐 Neutral", "gray")
    except Exception as e:
        logger.warning(f"Sentiment analysis failed: {e}")
        return ("😐 Neutral", "gray")

def safe_article_parse(link):
    """Safely parse article with error handling"""
    try:
        art = Article(link, language='en')
        art.download()
        art.parse()
        art.nlp()
        
        summary = art.summary or (art.text[:300] + "..." if art.text else "No content available.")
        image = art.top_image
        
        return summary, image
    except Exception as e:
        logger.warning(f"Failed to parse article {link}: {e}")
        return "Summary not available due to parsing error.", None

def display_news(items, qty, kw=''):
    """Display news items with enhanced error handling"""
    if not items:
        st.warning("No news items found.")
        return pd.DataFrame()
    
    rows = []
    progress_bar = st.progress(0)
    
    for idx, item in enumerate(items[:qty], 1):
        progress_bar.progress(idx / min(qty, len(items)))
        
        try:
            title = item.title.text if item.title else "No title"
            link = item.link.text if item.link else "#"
            pub = item.pubDate.text if item.pubDate else "N/A"
            
            st.markdown(f"### {idx}. {highlight(title, kw)}")
            
            # Parse article
            summary, image = safe_article_parse(link)
            sentiment, color = get_sentiment(summary)
            
            # Display image
            fetch_news_poster(image)
            
            # Display summary and sentiment
            with st.expander("📋 Summary & Sentiment"):
                st.write(highlight(summary, kw))
                st.markdown(f":{color}[**Sentiment:** {sentiment}]")
                st.markdown(f"[📖 Read full article]({link})")
            
            st.caption(f"📅 Published: {pub}")
            st.markdown("---")
            
            rows.append({
                "Title": title,
                "Summary": summary,
                "Link": link,
                "Sentiment": sentiment,
                "Published": pub
            })
            
        except Exception as e:
            logger.error(f"Error processing news item {idx}: {e}")
            st.error(f"Error loading news item {idx}")
    
    progress_bar.empty()
    return pd.DataFrame(rows)

def create_download_buttons(df, filename_base):
    """Create download buttons for CSV, Excel, and JSON"""
    if df.empty:
        return
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv_data = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            csv_data,
            f"{filename_base}.csv",
            "text/csv"
        )
    
    with col2:
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, engine='openpyxl')
        excel_buffer.seek(0)
        st.download_button(
            "⬇️ Download Excel",
            excel_buffer,
            f"{filename_base}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col3:
        json_data = json.dumps(df.to_dict("records"), indent=2)
        st.download_button(
            "⬇️ Download JSON",
            json_data,
            f"{filename_base}.json",
            "application/json"
        )

# ---------- STREAMLIT UI ----------
def main():
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #ff6b6b, #4ecdc4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: bold;
    }
    .news-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.title("⚙️ Controls")
        
        # Theme toggle
        dark_mode = st.checkbox("🌙 Dark Mode")
        if dark_mode:
            st.markdown("""
            <style>
            .stApp {
                background-color: #0e1117;
                color: #fafafa;
            }
            .main-header {
                color: #fafafa !important;
                -webkit-text-fill-color: #fafafa !important;
            }
            </style>
            """, unsafe_allow_html=True)
        
        # Refresh button
        if st.button("🔄 Refresh All News", type="primary"):
            st.cache_data.clear()
            st.rerun()
        
        # Settings
        st.markdown("### ⚙️ Settings")
        auto_refresh = st.checkbox("🔄 Auto-refresh (5 min)")
        if auto_refresh:
            time.sleep(300)
            st.rerun()

    # Header
    st.markdown('<h1 class="main-header">📰 SAMACHAR+ – Advanced News Portal</h1>', 
                unsafe_allow_html=True)
    st.markdown("---")

    # Main tabs
    tabs = st.tabs(["🔥 Trending", "📂 Categories", "🔍 Search", "📊 Analytics", "ℹ️ About"])

    # ---------- TRENDING NEWS ----------
    with tabs[0]:
        st.header("🔥 Trending News")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("Latest trending news from around the world")
        with col2:
            articles_count = st.slider("Number of articles", 5, 25, 10, key="trend")
        
        with st.spinner("Fetching trending news..."):
            items = fetch_top_news()
            
        if items:
            df = display_news(items, articles_count)
            if not df.empty:
                st.success(f"✅ Loaded {len(df)} trending articles")
                create_download_buttons(df, "trending_news")
        else:
            st.error("❌ Failed to fetch trending news. Please try again later.")

    # ---------- CATEGORY NEWS ----------
    with tabs[1]:
        st.header("📂 News by Category")
        
        categories = {
            'WORLD': '🌍 World News',
            'NATION': '🏛️ National News', 
            'BUSINESS': '💼 Business',
            'TECHNOLOGY': '💻 Technology',
            'ENTERTAINMENT': '🎬 Entertainment',
            'SPORTS': '⚽ Sports',
            'SCIENCE': '🔬 Science',
            'HEALTH': '🏥 Health'
        }
        
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_category = st.selectbox(
                "Choose a category",
                list(categories.keys()),
                format_func=lambda x: categories[x]
            )
        with col2:
            articles_count = st.slider("Number of articles", 5, 25, 10, key="cat")
        
        with st.spinner(f"Fetching {categories[selected_category]} news..."):
            items = fetch_category_news(selected_category)
            
        if items:
            df = display_news(items, articles_count)
            if not df.empty:
                st.success(f"✅ Loaded {len(df)} {categories[selected_category]} articles")
                create_download_buttons(df, f"{selected_category.lower()}_news")
        else:
            st.error(f"❌ Failed to fetch {categories[selected_category]}. Please try again later.")

    # ---------- SEARCH ----------
    with tabs[2]:
        st.header("🔍 Search News")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(
                "🔍 Enter keywords (comma-separated for multiple searches)",
                placeholder="e.g., artificial intelligence, climate change, sports"
            )
        with col2:
            articles_per_keyword = st.slider("Articles per keyword", 3, 15, 5, key="search")
        
        if st.button("🔍 Search News", type="primary"):
            if not search_query.strip():
                st.warning("⚠️ Please enter at least one keyword to search.")
            else:
                keywords = [k.strip() for k in search_query.split(",") if k.strip()]
                
                for i, keyword in enumerate(keywords):
                    st.subheader(f"🔍 Results for **{keyword}**")
                    
                    with st.spinner(f"Searching for '{keyword}'..."):
                        items = fetch_news_search_topic(keyword)
                    
                    if items:
                        df = display_news(items, articles_per_keyword, kw=keyword)
                        if not df.empty:
                            st.success(f"✅ Found {len(df)} articles for '{keyword}'")
                            create_download_buttons(df, f"search_{keyword.replace(' ', '_')}")
                    else:
                        st.warning(f"⚠️ No results found for '{keyword}'")
                    
                    if i < len(keywords) - 1:  # Add separator between searches
                        st.markdown("---")

    # ---------- ANALYTICS ----------
    with tabs[3]:
        st.header("📊 News Analytics")
        st.info("📈 Analytics features coming soon! This will include sentiment trends, category distribution, and more.")
        
        # Placeholder for future analytics
        if st.button("📊 Generate Sample Analytics"):
            sample_data = {
                'Category': ['World', 'Technology', 'Sports', 'Business', 'Health'],
                'Articles': [45, 32, 28, 25, 20],
                'Positive Sentiment': [60, 75, 80, 55, 70]
            }
            df_analytics = pd.DataFrame(sample_data)
            
            col1, col2 = st.columns(2)
            with col1:
                st.bar_chart(df_analytics.set_index('Category')['Articles'])
                st.caption("Articles by Category")
            
            with col2:
                st.line_chart(df_analytics.set_index('Category')['Positive Sentiment'])
                st.caption("Positive Sentiment by Category (%)")

    # ---------- ABOUT ----------
    with tabs[4]:
        st.header("ℹ️ About SAMACHAR+")
        
        st.markdown("""
        ### 🌟 Welcome to SAMACHAR+ 
        
        **SAMACHAR+** is an advanced news aggregation portal that brings you the latest news from around the world.
        
        #### ✨ Features:
        - 🔥 **Trending News**: Latest breaking news and trending topics
        - 📂 **Category-wise News**: Organized news by different categories
        - 🔍 **Smart Search**: Search news by keywords with highlighting
        - 📊 **Sentiment Analysis**: AI-powered sentiment analysis of news articles
        - 📱 **Responsive Design**: Works seamlessly on all devices
        - 💾 **Export Options**: Download news data in CSV, Excel, or JSON formats
        - 🌙 **Dark Mode**: Easy on the eyes dark theme
        
        #### 🛠️ Technology Stack:
        - **Streamlit** - Web application framework
        - **BeautifulSoup** - Web scraping and RSS parsing
        - **Newspaper3k** - Article extraction and processing
        - **TextBlob** - Natural language processing and sentiment analysis
        - **Pandas** - Data manipulation and analysis
        
        #### 📡 Data Sources:
        - Google News RSS feeds
        - Real-time news aggregation
        - Multiple news categories and sources
        
        ---
        
        **Made with ❤️ using Python & Streamlit**
        
        *Version: 2.0 Enhanced*
        """)

# ---------- ERROR HANDLING ----------
def run_app():
    """Run the app with global error handling"""
    try:
        main()
    except Exception as e:
        st.error(f"🚨 Application Error: {str(e)}")
        st.info("Please refresh the page or try again later.")
        logger.error(f"Application error: {e}")

if __name__ == "__main__":
    run_app()