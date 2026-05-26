import json
import requests
from pathlib import Path

from core.logging import get_logger

log = get_logger("jarvis.stocks")


def _get_stock_price(symbol: str) -> dict | None:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        return {
            "symbol": meta.get("symbol", symbol),
            "price": meta.get("regularMarketPrice", 0),
            "change": meta.get("regularMarketChange", 0),
            "change_pct": meta.get("regularMarketChangePercent", 0),
            "high": meta.get("regularMarketDayHigh", 0),
            "low": meta.get("regularMarketDayLow", 0),
            "currency": meta.get("currency", "USD"),
        }
    except Exception as e:
        log.warning("Stock fetch failed for %s: %s", symbol, e)
        return None


def _get_crypto_price(symbol: str) -> dict | None:
    try:
        symbol_id = symbol.lower()
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": symbol_id,
            "vs_currencies": "usd,eur",
            "include_24hr_change": "true",
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        if symbol_id not in data:
            return None
        d = data[symbol_id]
        return {
            "symbol": symbol.upper(),
            "price_usd": d.get("usd", 0),
            "price_eur": d.get("eur", 0),
            "change_24h": d.get("usd_24h_change", 0),
        }
    except Exception as e:
        log.warning("Crypto fetch failed for %s: %s", symbol, e)
        return None


_STOCK_ALIASES = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
    "amazon": "AMZN", "tesla": "TSLA", "meta": "META",
    "nvidia": "NVDA", "netflix": "NFLX", "intel": "INTC",
    "amd": "AMD", "ibm": "IBM", "oracle": "ORCL",
}

_CRYPTO_ALIASES = {
    "bitcoin": "bitcoin", "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "bnb": "binancecoin", "solana": "solana", "sol": "solana",
    "cardano": "cardano", "ada": "cardano",
    "xrp": "ripple", "ripple": "ripple",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "polkadot": "polkadot", "dot": "polkadot",
}


def stocks_crypto(parameters: dict | None = None, player=None, speak=None) -> str:
    p = parameters or {}
    action = p.get("action", "stock")
    symbol = p.get("symbol", "")

    if not symbol:
        return "Necesito el simbolo (symbol). Ej: AAPL, BTC, bitcoin"

    if action == "stock":
        sym = _STOCK_ALIASES.get(symbol.lower(), symbol.upper())
        data = _get_stock_price(sym)
        if not data:
            return f"No pude obtener datos de {sym}. Verifica el simbolo."

        emoji = "📈" if data["change"] >= 0 else "📉"
        return (
            f"{data['symbol']} {emoji}\n"
            f"Precio: {data['currency']} {data['price']:.2f}\n"
            f"Cambio: {data['change']:+.2f} ({data['change_pct']:+.2f}%)\n"
            f"Max del dia: {data['high']:.2f} | Min: {data['low']:.2f}"
        )

    elif action == "crypto":
        sym = _CRYPTO_ALIASES.get(symbol.lower(), symbol.lower())
        data = _get_crypto_price(sym)
        if not data:
            return f"No pude obtener datos de {sym}. Verifica el nombre."

        emoji = "📈" if data["change_24h"] >= 0 else "📉"
        return (
            f"{data['symbol']} {emoji}\n"
            f"USD: ${data['price_usd']:.2f}\n"
            f"EUR: {data['price_eur']:.2f} EUR\n"
            f"Cambio 24h: {data['change_24h']:+.2f}%"
        )

    else:
        return f"Accion desconocida: {action}. Usa: stock, crypto"
