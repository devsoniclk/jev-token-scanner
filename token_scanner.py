"""Fetch new/trending tokens from CoinGecko."""

import time
import requests
from typing import Optional


class TokenScanner:
    """CoinGecko token scanner for market and trending data."""

    def __init__(self, config: dict, api_key: Optional[str] = None):
        self.base_url = config["coingecko"]["base_url"]
        self.rate_limit = config["coingecko"]["rate_limit_delay"]
        self.vs_currency = config["coingecko"]["default_vs_currency"]
        self.per_page = config["coingecko"]["per_page"]
        self.api_key = api_key
        self._last_request = 0.0

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["x-cg-demo-api-key"] = self.api_key
        return h

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    def _get(self, endpoint: str, params: dict = None) -> dict:
        self._throttle()
        url = f"{self.base_url}{endpoint}"
        resp = requests.get(url, params=params or {}, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_trending(self, limit: int = 20) -> list[dict]:
        """Get trending tokens from CoinGecko /search/trending."""
        data = self._get("/search/trending")
        coins = data.get("coins", [])[:limit]
        results = []
        for c in coins:
            item = c.get("item", {})
            results.append({
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "symbol": item.get("symbol", "").upper(),
                "market_cap_rank": item.get("market_cap_rank"),
                "price_btc": item.get("price_btc"),
                "score": item.get("score", 0),
                "data": item.get("data", {}),
            })
        return results

    def get_markets(self, page: int = 1, limit: int = 50) -> list[dict]:
        """Get tokens by market cap from /coins/markets."""
        params = {
            "vs_currency": self.vs_currency,
            "order": "market_cap_desc",
            "per_page": min(limit, 250),
            "page": page,
            "sparkline": "false",
        }
        data = self._get("/coins/markets", params)
        results = []
        for c in data:
            results.append({
                "id": c.get("id", ""),
                "name": c.get("name", ""),
                "symbol": c.get("symbol", "").upper(),
                "market_cap": c.get("market_cap"),
                "current_price": c.get("current_price"),
                "total_volume": c.get("total_volume"),
                "price_change_24h": c.get("price_change_percentage_24h"),
                "market_cap_rank": c.get("market_cap_rank"),
                "circulating_supply": c.get("circulating_supply"),
                "total_supply": c.get("total_supply"),
                "max_supply": c.get("max_supply"),
                "ath": c.get("ath"),
                "ath_change_percentage": c.get("ath_change_percentage"),
                "atl": c.get("atl"),
                "atl_change_percentage": c.get("atl_change_percentage"),
                "last_updated": c.get("last_updated"),
            })
        return results

    def get_new_listings(self, limit: int = 50) -> list[dict]:
        """Get recently listed tokens from /coins/list then cross-ref with markets."""
        coins = self._get("/coins/list")
        # CoinGecko /coins/list returns all coins sorted by ID; take last N
        # (newly added tend to be appended). Get their market data next.
        recent = coins[-limit:] if len(coins) > limit else coins
        ids = [c["id"] for c in recent if "id" in c]
        if not ids:
            return []
        # Fetch market data for these IDs in batches of 50
        results = []
        for i in range(0, len(ids), 50):
            batch = ids[i:i + 50]
            params = {
                "vs_currency": self.vs_currency,
                "ids": ",".join(batch),
                "order": "market_cap_desc",
                "per_page": 50,
                "page": 1,
                "sparkline": "false",
            }
            try:
                data = self._get("/coins/markets", params)
                for c in data:
                    results.append({
                        "id": c.get("id", ""),
                        "name": c.get("name", ""),
                        "symbol": c.get("symbol", "").upper(),
                        "market_cap": c.get("market_cap"),
                        "current_price": c.get("current_price"),
                        "total_volume": c.get("total_volume"),
                        "price_change_24h": c.get("price_change_percentage_24h"),
                        "market_cap_rank": c.get("market_cap_rank"),
                        "circulating_supply": c.get("circulating_supply"),
                        "total_supply": c.get("total_supply"),
                        "max_supply": c.get("max_supply"),
                        "last_updated": c.get("last_updated"),
                    })
            except requests.HTTPError:
                continue
        return results

    def enrich_token(self, token_id: str) -> dict:
        """Get detailed info for a single token from /coins/{id}."""
        try:
            data = self._get(f"/coins/{token_id}", {
                "localization": "false",
                "tickers": "false",
                "community_data": "true",
                "developer_data": "false",
                "sparkline": "false",
            })
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "symbol": data.get("symbol", "").upper(),
                "description": (data.get("description", {}) or {}).get("en", "")[:500],
                "categories": data.get("categories", []),
                "market_cap": (data.get("market_data", {}) or {}).get("market_cap", {}).get("usd"),
                "total_volume": (data.get("market_data", {}) or {}).get("total_volume", {}).get("usd"),
                "current_price": (data.get("market_data", {}) or {}).get("current_price", {}).get("usd"),
                "liquidity_score": data.get("liquidity_score"),
                "coingecko_score": data.get("coingecko_score"),
                "developer_score": data.get("developer_score"),
                "community_score": data.get("community_score"),
                "public_interest_score": data.get("public_interest_score"),
                "community_data": data.get("community_data", {}),
                "telegram_channel_user_count": (data.get("community_data") or {}).get("telegram_channel_user_count"),
                "twitter_followers": (data.get("community_data") or {}).get("twitter_followers"),
                "reddit_subscribers": (data.get("community_data") or {}).get("reddit_subscribers"),
                "contract_address": data.get("contract_address"),
                "platforms": data.get("platforms", {}),
                "genesis_date": data.get("genesis_date"),
                "sentiment_up_percentage": (data.get("sentiment_votes_up_percentage")),
                "sentiment_down_percentage": (data.get("sentiment_votes_down_percentage")),
                "watchlist_users": data.get("watchlist_users"),
                "last_updated": data.get("last_updated"),
            }
        except requests.HTTPError:
            return {}
