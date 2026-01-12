from typing import List, Dict, Any, Optional
from langchain_core.tools import StructuredTool
from langchain_community.tools.tavily_search import TavilySearchResults
from pydantic import BaseModel, Field
import yfinance as yf
import requests
from datetime import datetime, timedelta
import json
from app.core.config import settings


class StockQueryInput(BaseModel):
    symbol: str = Field(description="Stock ticker symbol (e.g., AAPL, RELIANCE.NS)")
    query_type: str = Field(default="quote", description="Type of query: quote, financials, or news")


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")


class TechnicalIndicatorInput(BaseModel):
    symbol: str = Field(description="Stock ticker symbol")
    indicator: str = Field(description="Indicator name: RSI, MACD, or MA")
    period: Optional[int] = Field(default=14, description="Period for calculation")


def get_stock_quote(symbol: str, query_type: str = "quote") -> str:
    """Get stock quote, financials, or news for a given symbol"""
    try:
        ticker = yf.Ticker(symbol)
        
        if query_type == "quote":
            info = ticker.info
            quote = ticker.history(period="1d")
            
            if quote.empty:
                return f"No data found for {symbol}"
            
            current_price = quote['Close'].iloc[-1]
            prev_close = info.get('previousClose', current_price)
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close else 0
            
            result = {
                "symbol": symbol,
                "current_price": round(current_price, 2),
                "previous_close": round(prev_close, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "volume": quote['Volume'].iloc[-1],
                "market_cap": info.get('marketCap'),
                "pe_ratio": info.get('trailingPE'),
                "52_week_high": info.get('fiftyTwoWeekHigh'),
                "52_week_low": info.get('fiftyTwoWeekLow')
            }
            
        elif query_type == "financials":
            info = ticker.info
            result = {
                "symbol": symbol,
                "company_name": info.get('longName'),
                "sector": info.get('sector'),
                "industry": info.get('industry'),
                "market_cap": info.get('marketCap'),
                "pe_ratio": info.get('trailingPE'),
                "forward_pe": info.get('forwardPE'),
                "peg_ratio": info.get('pegRatio'),
                "dividend_yield": info.get('dividendYield'),
                "revenue": info.get('totalRevenue'),
                "profit_margin": info.get('profitMargins'),
                "roe": info.get('returnOnEquity'),
                "debt_to_equity": info.get('debtToEquity')
            }
            
        elif query_type == "news":
            news = ticker.news[:5]  # Get latest 5 news items
            result = {
                "symbol": symbol,
                "news": [
                    {
                        "title": item.get('title'),
                        "publisher": item.get('publisher'),
                        "link": item.get('link'),
                        "published": datetime.fromtimestamp(item.get('providerPublishTime', 0)).isoformat()
                    }
                    for item in news
                ]
            }
        else:
            return f"Invalid query_type: {query_type}. Use 'quote', 'financials', or 'news'"
        
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        return f"Error fetching stock data for {symbol}: {str(e)}"


def calculate_technical_indicator(symbol: str, indicator: str, period: int = 14) -> str:
    """Calculate technical indicators (RSI, MACD, Moving Average)"""
    try:
        import pandas as pd
        import numpy as np
        
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo")
        
        if hist.empty:
            return f"No historical data found for {symbol}"
        
        close_prices = hist['Close'].values
        
        if indicator.upper() == "RSI":
            # Calculate RSI
            delta = pd.Series(close_prices).diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            return json.dumps({
                "symbol": symbol,
                "indicator": "RSI",
                "period": period,
                "current_value": round(current_rsi, 2),
                "interpretation": "Overbought (>70)" if current_rsi > 70 else "Oversold (<30)" if current_rsi < 30 else "Neutral"
            }, indent=2)
            
        elif indicator.upper() == "MACD":
            # Calculate MACD
            ema12 = pd.Series(close_prices).ewm(span=12, adjust=False).mean()
            ema26 = pd.Series(close_prices).ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line
            
            return json.dumps({
                "symbol": symbol,
                "indicator": "MACD",
                "macd_line": round(macd_line.iloc[-1], 2),
                "signal_line": round(signal_line.iloc[-1], 2),
                "histogram": round(histogram.iloc[-1], 2),
                "signal": "Bullish" if histogram.iloc[-1] > 0 else "Bearish"
            }, indent=2)
            
        elif indicator.upper() == "MA":
            # Moving Average
            ma = pd.Series(close_prices).rolling(window=period).mean()
            current_price = close_prices[-1]
            current_ma = ma.iloc[-1]
            
            return json.dumps({
                "symbol": symbol,
                "indicator": f"MA({period})",
                "current_price": round(current_price, 2),
                "moving_average": round(current_ma, 2),
                "position": "Above MA" if current_price > current_ma else "Below MA"
            }, indent=2)
        else:
            return f"Unsupported indicator: {indicator}. Use RSI, MACD, or MA"
            
    except Exception as e:
        return f"Error calculating {indicator} for {symbol}: {str(e)}"


def web_search(query: str) -> str:
    """Search the web for current information"""
    try:
        if not settings.TAVILY_API_KEY:
            # Fallback to a simple search (in production, you'd want Tavily)
            return f"Web search not configured. Please set TAVILY_API_KEY. Query: {query}"
        
        tavily = TavilySearchResults(
            api_key=settings.TAVILY_API_KEY,
            max_results=5
        )
        results = tavily.invoke(query)
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error performing web search: {str(e)}"


def get_financial_tools() -> List[StructuredTool]:
    """Get all available financial tools"""
    tools = []
    
    # Stock quote tool
    stock_tool = StructuredTool.from_function(
        func=get_stock_quote,
        name="get_stock_quote",
        description="Get stock quote, financials, or news for a ticker symbol. Use format like AAPL for US stocks, RELIANCE.NS for Indian stocks (NSE), or RELIANCE.BO for BSE.",
        args_schema=StockQueryInput
    )
    tools.append(stock_tool)
    
    # Technical indicator tool
    indicator_tool = StructuredTool.from_function(
        func=calculate_technical_indicator,
        name="calculate_technical_indicator",
        description="Calculate technical indicators (RSI, MACD, Moving Average) for a stock symbol",
        args_schema=TechnicalIndicatorInput
    )
    tools.append(indicator_tool)
    
    # Web search tool
    if settings.TAVILY_API_KEY:
        search_tool = StructuredTool.from_function(
            func=web_search,
            name="web_search",
            description="Search the web for current information, news, or market updates",
            args_schema=WebSearchInput
        )
        tools.append(search_tool)
    
    return tools
