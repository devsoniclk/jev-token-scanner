"""Feed token data to Jev for classification."""

from typing import Optional


class TokenClassifier:
    """Classify tokens using Jev decisions API."""

    def __init__(self, scanner, jev_client):
        self.scanner = scanner
        self.jev = jev_client

    def classify_token(self, token: dict, enrich: bool = True) -> dict:
        """
        Classify a single token.

        Args:
            token: token dict from scanner (get_markets / get_trending)
            enrich: whether to fetch detailed data from /coins/{id}

        Returns:
            dict with token info + Jev classification.
        """
        token_id = token.get("id", "")
        enriched = {}

        if enrich and token_id:
            try:
                enriched = self.scanner.enrich_token(token_id)
            except Exception:
                pass

        # Build state for Jev
        state = self._build_state(token, enriched)

        # Get Jev classification
        classification = self.jev.classify(state)

        return {
            "token_id": token_id,
            "name": token.get("name", ""),
            "symbol": token.get("symbol", ""),
            "state": state,
            "classification": {k: v for k, v in classification.items() if k != "raw_response"},
        }

    def classify_batch(self, tokens: list[dict], enrich: bool = True) -> list[dict]:
        """Classify a batch of tokens."""
        results = []
        for token in tokens:
            try:
                result = self.classify_token(token, enrich=enrich)
                results.append(result)
            except Exception as e:
                results.append({
                    "token_id": token.get("id", ""),
                    "name": token.get("name", ""),
                    "symbol": token.get("symbol", ""),
                    "error": str(e),
                })
        return results

    def _build_state(self, token: dict, enriched: dict) -> dict:
        """Build the state dict for Jev from token + enriched data."""
        state = {
            "name": token.get("name") or enriched.get("name", "Unknown"),
            "symbol": token.get("symbol") or enriched.get("symbol", "?"),
            "market_cap": token.get("market_cap") or enriched.get("market_cap"),
            "total_volume": token.get("total_volume") or enriched.get("total_volume"),
            "current_price": token.get("current_price") or enriched.get("current_price"),
            "price_change_24h": token.get("price_change_24h"),
            "market_cap_rank": token.get("market_cap_rank") or enriched.get("market_cap_rank"),
        }

        # Add enriched data if available
        if enriched:
            state["description"] = enriched.get("description", "")[:300]
            state["categories"] = enriched.get("categories", [])
            state["liquidity_score"] = enriched.get("liquidity_score")
            state["coingecko_score"] = enriched.get("coingecko_score")
            state["community_score"] = enriched.get("community_score")
            state["developer_score"] = enriched.get("developer_score")
            state["telegram_users"] = enriched.get("telegram_channel_user_count")
            state["twitter_followers"] = enriched.get("twitter_followers")
            state["reddit_subscribers"] = enriched.get("reddit_subscribers")
            state["contract_address"] = enriched.get("contract_address")
            state["platforms"] = enriched.get("platforms", {})
            state["genesis_date"] = enriched.get("genesis_date")
            state["sentiment_up"] = enriched.get("sentiment_up_percentage")
            state["sentiment_down"] = enriched.get("sentiment_down_percentage")
            state["watchlist_users"] = enriched.get("watchlist_users")
            state["circulating_supply"] = enriched.get("circulating_supply") or token.get("circulating_supply")
            state["total_supply"] = enriched.get("total_supply") or token.get("total_supply")
            state["max_supply"] = enriched.get("max_supply") or token.get("max_supply")
            state["ath"] = enriched.get("ath") or token.get("ath")
            state["ath_change_percentage"] = enriched.get("ath_change_percentage") or token.get("ath_change_percentage")

        # Clean None values
        return {k: v for k, v in state.items() if v is not None}
