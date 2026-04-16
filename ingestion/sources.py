"""
Financial news source definitions.
Each source has a name, type (rss or api), and URL.
"""

RSS_SOURCES = [
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "category": "business",
    },
    {
        "name": "Reuters Finance",
        "url": "https://feeds.reuters.com/reuters/financialsNews",
        "category": "finance",
    },
    {
        "name": "CNBC Finance",
        "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "category": "finance",
    },
    {
        "name": "CNBC Economy",
        "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "category": "economy",
    },
    {
        "name": "MarketWatch",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories/",
        "category": "markets",
    },
    {
        "name": "Financial Times",
        "url": "https://www.ft.com/?format=rss",
        "category": "finance",
    },
    {
        "name": "BBC Business",
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "category": "business",
    },
    {
        "name": "The Economist Finance",
        "url": "https://www.economist.com/finance-and-economics/rss.xml",
        "category": "finance",
    },
    {
        "name": "Investing.com News",
        "url": "https://www.investing.com/rss/news.rss",
        "category": "markets",
    },
    {
        "name": "Seeking Alpha",
        "url": "https://seekingalpha.com/feed.xml",
        "category": "markets",
    },
    # Startups & venture
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "startups",
    },
    {
        "name": "TechCrunch Startups",
        "url": "https://techcrunch.com/category/startups/feed/",
        "category": "startups",
    },
    {
        "name": "Crunchbase News",
        "url": "https://news.crunchbase.com/feed/",
        "category": "startups",
    },
    {
        "name": "VentureBeat",
        "url": "https://venturebeat.com/feed/",
        "category": "startups",
    },
    # IPO-focused
    {
        "name": "Renaissance Capital IPO News",
        "url": "https://www.renaissancecapital.com/feeds/iponews.xml",
        "category": "ipo",
    },
    {
        "name": "WSJ Markets",
        "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "category": "markets",
    },
    {
        "name": "WSJ Business",
        "url": "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
        "category": "business",
    },
    # The Economist (broader)
    {
        "name": "The Economist Business",
        "url": "https://www.economist.com/business/rss.xml",
        "category": "business",
    },
    {
        "name": "Fortune",
        "url": "https://fortune.com/feed/",
        "category": "business",
    },
    # Newsletters
    {
        "name": "Morning Brew",
        "url": "https://www.morningbrew.com/daily/feed.rss",
        "category": "business",
    },
    {
        "name": "Techpresso",
        "url": "https://techpresso.co/feed",
        "category": "startups",
    },
]
