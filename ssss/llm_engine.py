#!/usr/bin/env python3
"""
MCX Silver Futures - LLM-Powered Trading Engine
===============================================
Replaces ML decision engine with LLM-based trading decisions.

Features:
  • Analyzes OHLC data and technical indicators
  • Generates structured trading signals (BUY/SELL/HOLD)
  • Provides confidence scores and risk levels
  • Includes ATR-based stop loss and target calculation
  • Strict JSON output format for integration

Usage:
    from llm_engine import LLMTradingEngine
    
    engine = LLMTradingEngine()
    decision = engine.generate_decision(ohlc_data, indicators, position)
"""

import json
import logging
import math
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _strip_llm_api_key(key: Optional[str]) -> Optional[str]:
    if key is None:
        return None
    s = str(key).strip()
    return s or None


def _default_openai_compatible_base() -> str:
    """
    When LLM_BASE_URL / OPENAI_BASE_URL are unset, choose a default /v1 host.
    OpenAI project keys (sk-proj-…) must use api.openai.com; OpenRouter keys use openrouter.ai.
    """
    key = (
        _strip_llm_api_key(os.getenv("OPENAI_API_KEY"))
        or _strip_llm_api_key(os.getenv("LLM_API_KEY"))
        or ""
    )
    kl = key.lower()
    if kl.startswith("sk-or-v1-") or kl.startswith("sk-or-"):
        return "https://openrouter.ai/api/v1"
    return "https://api.openai.com/v1"


def _normalize_llm_model(model: str, base_url: str) -> str:
    """Map placeholder env values; align model id with OpenAI vs OpenRouter conventions."""
    m = (model or "").strip() or "gpt-4o-mini"
    if m.lower() in ("openai", "default", "openai-api"):
        m = "gpt-4o-mini"
    is_or = "openrouter.ai" in (base_url or "").lower()
    if is_or:
        if "/" not in m:
            m = f"openai/{m}"
    else:
        if m.startswith("openai/"):
            m = m.split("/", 1)[1]
    return m


def _floor_completion_budget(model: str, requested: int) -> int:
    """
    GPT-5 / reasoning-style models can spend the whole completion budget before
    emitting visible text; tiny limits (e.g. 100) yield empty content + finish_reason length.
    """
    try:
        req = max(1, int(requested))
    except (TypeError, ValueError):
        req = 350
    env_min = (os.getenv("LLM_MIN_COMPLETION_TOKENS") or "").strip()
    if env_min:
        try:
            floor = max(1, int(env_min))
        except ValueError:
            floor = 1024
    else:
        ml = (model or "").lower()
        if (
            ml.startswith("gpt-5")
            or ml.startswith("o1")
            or ml.startswith("o3")
            or ml.startswith("o4")
        ):
            floor = 1024
        else:
            floor = 384
    out = max(req, floor)
    if out > req:
        logger.warning(
            "LLM_MAX_TOKENS=%s is below minimum %s for model %s; using %s completion tokens.",
            requested,
            floor,
            model,
            out,
        )
    return out


def _should_use_max_completion_tokens(model: str, base_url: str) -> bool:
    """
    Newer OpenAI chat models reject max_tokens and require max_completion_tokens.
    OpenRouter/OpenAI-compatible hosts still expect max_tokens.
    """
    env = str(os.getenv("LLM_USE_MAX_COMPLETION_TOKENS", "")).strip().lower()
    if env in ("1", "true", "yes"):
        return True
    if env in ("0", "false", "no"):
        return False
    if "openrouter.ai" in (base_url or "").lower():
        return False
    if "api.openai.com" not in (base_url or "").lower():
        return False
    ml = (model or "").lower()
    return (
        ml.startswith("gpt-5")
        or ml.startswith("o1")
        or ml.startswith("o3")
        or ml.startswith("o4")
    )


@dataclass
class TradingDecision:
    """Trading decision structure."""
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0-100
    entry_price: float
    stop_loss: float
    target: float
    reason: str
    timestamp: str
    risk_reward_ratio: float


class LLMTradingEngine:
    """
    LLM-powered trading decision engine for MCX Silver futures.
    
    Uses structured prompt engineering to generate consistent,
    risk-aware trading decisions based on technical analysis.
    """
    
    def __init__(
        self,
        model_provider: str = "openai",
        api_key: str = None,
        min_confidence_pct: Optional[float] = None,
    ):
        """
        Initialize LLM trading engine.
        
        Args:
            model_provider: LLM provider (openai, anthropic, local)
            api_key: API key for the provider
            min_confidence_pct: Minimum confidence 0–100 for BUY/SELL (matches bot MIN_CONFIDENCE if passed)
        """
        self.model_provider = model_provider
        self.api_key = _strip_llm_api_key(api_key)
        self.last_api_error = None
        env_pct = (os.getenv("LLM_MIN_CONFIDENCE_PCT") or "").strip()
        if min_confidence_pct is not None:
            self.min_confidence = float(min_confidence_pct)
        elif env_pct:
            self.min_confidence = float(env_pct)
        else:
            self.min_confidence = 65.0
        self.min_confidence = max(1.0, min(99.0, self.min_confidence))
        self.max_risk_pct = 1.5  # Maximum risk per trade
        self.default_rr_ratio = 2.0  # Default risk-reward ratio

        mc = int(round(self.min_confidence))
        self.trading_rules = f"""
        TRADING RULES (this session requires ≥{mc}% confidence to BUY or SELL):
        1. When trend, RSI zone, MACD, and volume clearly favour longs, output BUY with confidence ≥{mc}%.
        2. Use SELL only to close an existing long (see CURRENT POSITION). If flat with no position, do NOT output SELL for “bearish view”—use HOLD.
        3. Use HOLD only when the setup is genuinely mixed or low conviction—not when you describe a clear directional bias.
        4. If your reasoning supports a trade, action must be BUY or SELL as appropriate—not HOLD with a bullish/bearish essay.
        5. Use ATR for stop_loss distance; target at least ~2:1 reward vs risk for BUY.
        6. Avoid churning: respect “no trade” when indicators conflict.
        """
        
    def calculate_atr_stop_loss(self, atr: float, current_price: float, side: str) -> float:
        """
        Calculate ATR-based stop loss.
        
        Args:
            atr: Average True Range value
            current_price: Current market price
            side: Trade side (BUY/SELL)
            
        Returns:
            Stop loss price
        """
        atr_multiplier = 1.5
        stop_distance = atr * atr_multiplier
        
        if side == "BUY":
            return current_price - stop_distance
        else:  # SELL
            return current_price + stop_distance
    
    def calculate_target_price(self, entry_price: float, stop_loss: float, side: str) -> float:
        """
        Calculate target price based on risk-reward ratio.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            side: Trade side (BUY/SELL)
            
        Returns:
            Target price
        """
        risk = abs(entry_price - stop_loss)
        reward = risk * self.default_rr_ratio
        
        if side == "BUY":
            return entry_price + reward
        else:  # SELL
            return entry_price - reward
    
    def analyze_market_condition(self, indicators: Dict) -> str:
        """
        Analyze overall market condition from indicators.
        
        Args:
            indicators: Dictionary of technical indicators
            
        Returns:
            Market condition description
        """
        rsi = indicators.get('RSI', 50)
        macd = indicators.get('MACD', 0)
        trend = indicators.get('trend_strength', 0)
        volume_ratio = indicators.get('volume_ratio', 1.0)
        
        conditions = []
        
        # RSI analysis
        if rsi > 70:
            conditions.append("overbought")
        elif rsi < 30:
            conditions.append("oversold")
        else:
            conditions.append("neutral RSI")
        
        # Trend analysis
        if trend > 0.7:
            conditions.append("strong uptrend")
        elif trend < -0.7:
            conditions.append("strong downtrend")
        else:
            conditions.append("sideways market")
        
        # Volume analysis
        if volume_ratio > 1.5:
            conditions.append("high volume")
        elif volume_ratio < 0.7:
            conditions.append("low volume")
        
        return ", ".join(conditions)
    
    def create_trading_prompt(self, ohlc_data: Dict, indicators: Dict, position: Dict = None) -> str:
        """
        Create structured prompt for LLM decision making.
        
        Args:
            ohlc_data: Latest OHLC data
            indicators: Technical indicators
            position: Current position (if any)
            
        Returns:
            Structured prompt string
        """
        market_condition = self.analyze_market_condition(indicators)
        
        prompt = f"""
You are an expert MCX Silver futures trader. Analyze the following data and make a trading decision.

CURRENT MARKET DATA:
- Symbol: MCX Silver Futures
- Current Price: ₹{ohlc_data.get('close', 0):.2f}
- Open: ₹{ohlc_data.get('open', 0):.2f}
- High: ₹{ohlc_data.get('high', 0):.2f}
- Low: ₹{ohlc_data.get('low', 0):.2f}
- Volume: {ohlc_data.get('volume', 0):,}

TECHNICAL INDICATORS:
- RSI (14): {indicators.get('RSI', 0):.2f}
- MACD: {indicators.get('MACD', 0):.4f}
- ATR (14): ₹{indicators.get('ATR', 0):.2f}
- SMA (20): ₹{indicators.get('SMA_20', 0):.2f}
- EMA (12): ₹{indicators.get('EMA_12', 0):.2f}
- Volume Ratio: {indicators.get('volume_ratio', 0):.2f}
- Trend Strength: {indicators.get('trend_strength', 0):.2f}

MARKET CONDITION: {market_condition}

CURRENT POSITION: {position or 'None'}

{self.trading_rules}

DECISION REQUIREMENTS:
1. Prefer BUY when long setup is clear; prefer SELL when instructing exit and a position exists.
2. HOLD is for unclear/conflicting data only—do not use HOLD to mean “I would buy but being cautious”.
3. Set confidence to match how strong the edge is (must be ≥{int(round(self.min_confidence))}% for any BUY or SELL you output).

RESPONSE FORMAT (JSON only):
{{
    "action": "BUY" | "SELL" | "HOLD",
    "confidence": 0-100,
    "entry_price": {ohlc_data.get('close', 0):.2f},
    "stop_loss": calculated_based_on_ATR,
    "target": calculated_with_2:1_RR,
    "reason": "brief_technical_explanation"
}}

Provide ONLY the JSON response, no additional text.
"""
        return prompt
    
    def call_llm_api(self, prompt: str) -> Optional[str]:
        """
        Call LLM API for decision generation.
        
        Args:
            prompt: Structured trading prompt
            
        Returns:
            LLM response or None if failed
        """
        self.last_api_error = None
        if not self.api_key:
            require = str(os.getenv("REQUIRE_LLM_API_KEY", "false")).strip().lower() in ("1", "true", "yes")
            if require:
                raise RuntimeError("REQUIRE_LLM_API_KEY=true but LLM_API_KEY / OPENAI_API_KEY is not set.")
            logger.warning("LLM_API_KEY / OPENAI_API_KEY not set; returning HOLD decision.")
            return '''{
  "action": "HOLD",
  "confidence": 72,
  "entry_price": 0.0,
  "stop_loss": 0.0,
  "target": 0.0,
  "reason": "LLM API key missing; holding."
}'''

        # OpenAI-compatible JSON API (OpenAI official and OpenRouter both use /v1/chat/completions)
        raw_base = (os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "").strip()
        base_url = (raw_base or _default_openai_compatible_base()).rstrip("/")
        model = _normalize_llm_model(os.getenv("LLM_MODEL") or "gpt-4o-mini", base_url)
        temperature = float(os.getenv("LLM_TEMPERATURE") or "0.1")
        max_tokens = int(os.getenv("LLM_MAX_TOKENS") or "350")

        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if "openrouter.ai" in base_url.lower():
            headers["HTTP-Referer"] = os.getenv("LLM_APP_URL", "http://localhost:3000")
            headers["X-Title"] = os.getenv("LLM_APP_NAME", "MCX Trading Bot")

        payload_base = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return ONLY valid JSON that matches the required schema. No markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        use_completion_limit = _should_use_max_completion_tokens(model, base_url)
        if use_completion_limit:
            max_tokens = _floor_completion_budget(model, max_tokens)

        def _with_token_limit(completion: bool) -> dict:
            p = {**payload_base}
            p.pop("max_tokens", None)
            p.pop("max_completion_tokens", None)
            if completion:
                p["max_completion_tokens"] = max_tokens
            else:
                p["max_tokens"] = max_tokens
            return p

        logger.info("Calling LLM API for trading decision...")
        retry_statuses = {408, 409, 425, 429, 500, 502, 503, 504}
        bumped_for_empty_completion = False
        for attempt in range(3):
            payload = _with_token_limit(use_completion_limit)
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=25)
            except requests.RequestException as e:
                self.last_api_error = f"LLM request failed: {e}"
                logger.error(self.last_api_error)
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None

            if resp.status_code != 200:
                detail_raw = (resp.text or "").strip()
                detail = detail_raw.replace("\n", " ")[:300]
                self.last_api_error = f"LLM API HTTP {resp.status_code}: {detail or 'empty response'}"
                logger.error(self.last_api_error)
                dr_low = detail_raw.lower()
                if (
                    resp.status_code == 400
                    and not use_completion_limit
                    and "max_completion_tokens" in dr_low
                    and ("max_tokens" in dr_low or "unsupported_parameter" in dr_low)
                ):
                    use_completion_limit = True
                    logger.info("Retrying LLM call with max_completion_tokens (model rejected max_tokens).")
                    continue
                if resp.status_code in retry_statuses and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None

            try:
                data = resp.json()
            except ValueError:
                self.last_api_error = f"LLM API non-JSON response: {(resp.text or '')[:300]}"
                logger.error(self.last_api_error)
                return None

            choice0 = (data.get("choices") or [{}])[0]
            msg = choice0.get("message") or {}
            content = msg.get("content")
            finish_reason = str(choice0.get("finish_reason") or "")
            if isinstance(content, str):
                content = content.strip() or None
            if not content:
                # Often: max_completion_tokens too small on GPT-5 → reasoning consumes budget, content empty, length stop.
                if (
                    use_completion_limit
                    and finish_reason == "length"
                    and not bumped_for_empty_completion
                ):
                    bump_to = max(max_tokens * 3, 2048)
                    if bump_to > max_tokens:
                        logger.warning(
                            "LLM returned empty assistant text (finish_reason=length); retrying with max_completion_tokens=%s",
                            bump_to,
                        )
                        max_tokens = bump_to
                        bumped_for_empty_completion = True
                        continue
                self.last_api_error = f"LLM API response missing content: {str(data)[:300]}"
                logger.error(self.last_api_error)
                return None

            return content

        return None
    
    def create_ml_verify_prompt(
        self,
        ml_action: str,
        ml_confidence_pct: float,
        ohlc_data: Dict,
        indicators: Dict,
        position: Dict = None,
    ) -> str:
        """Prompt for second-pass verification of an ML-proposed trade."""
        market_condition = self.analyze_market_condition(indicators)
        return f"""
You verify a machine-learning trading proposal for MCX Silver futures before any order is placed.

ML PROPOSAL:
- Proposed action: {ml_action}
- ML estimated confidence: {ml_confidence_pct:.1f}%

CURRENT MARKET DATA:
- Current Price: ₹{ohlc_data.get('close', 0):.2f}
- Open: ₹{ohlc_data.get('open', 0):.2f}
- High: ₹{ohlc_data.get('high', 0):.2f}
- Low: ₹{ohlc_data.get('low', 0):.2f}
- Volume: {ohlc_data.get('volume', 0):,}

TECHNICAL INDICATORS:
- RSI (14): {indicators.get('RSI', 0):.2f}
- MACD: {indicators.get('MACD', 0):.4f}
- ATR (14): ₹{indicators.get('ATR', 0):.2f}
- SMA (20): ₹{indicators.get('SMA_20', 0):.2f}
- EMA (12): ₹{indicators.get('EMA_12', 0):.2f}
- Volume Ratio: {indicators.get('volume_ratio', 0):.2f}
- Trend Strength: {indicators.get('trend_strength', 0):.2f}

MARKET CONDITION: {market_condition}
CURRENT POSITION: {position or 'None'}

TASK:
1. Decide whether to AGREE or DISAGREE with the ML proposal.
2. If you AGREE, your "action" MUST be exactly "{ml_action}".
3. If you DISAGREE, set verdict to DISAGREE and choose action BUY / SELL / HOLD (usually HOLD).

Return ONLY valid JSON (no markdown):
{{
  "verdict": "AGREE" | "DISAGREE",
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0-100,
  "reason": "short explanation referencing risk and indicators"
}}
"""

    def parse_verify_response(self, response: str) -> Optional[Dict]:
        """Parse JSON from verify_ml_proposal LLM response."""
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:-3].strip()
            elif response.startswith("```"):
                response = response[3:-3].strip()
            data = json.loads(response)
            verdict = str(data.get("verdict", "")).upper()
            action = str(data.get("action", "HOLD")).upper()
            confidence = float(data.get("confidence", 0))
            reason = str(data.get("reason", ""))
            if verdict not in ("AGREE", "DISAGREE"):
                return None
            if action not in ("BUY", "SELL", "HOLD"):
                return None
            if not (0 <= confidence <= 100):
                return None
            return {
                "verdict": verdict,
                "action": action,
                "confidence": confidence,
                "reason": reason,
            }
        except Exception as e:
            logger.error(f"Verify response parse error: {e}")
            return None

    def verify_ml_proposal(
        self,
        ml_action: str,
        ml_confidence_pct: float,
        ohlc_data: Dict,
        indicators: Dict,
        position: Dict = None,
    ) -> Optional[Dict]:
        """
        Ask LLM to verify ML BUY/SELL. Returns dict with agree, confidence 0-100, reason, or None on failure.
        """
        ml_action = str(ml_action or "").upper()
        if ml_action not in ("BUY", "SELL"):
            return None
        prompt = self.create_ml_verify_prompt(
            ml_action, ml_confidence_pct, ohlc_data, indicators, position
        )
        raw = self.call_llm_api(prompt)
        if not raw:
            return None
        parsed = self.parse_verify_response(raw)
        if not parsed:
            return None
        # Normalize agree: strict match with ML proposal
        parsed["agree"] = (
            parsed["verdict"] == "AGREE"
            and parsed["action"] == ml_action
        )
        return parsed

    def parse_llm_response(
        self, response: str, reference_close: float = 0.0
    ) -> Optional[Dict]:
        """
        Parse LLM response and validate format.
        
        Args:
            response: Raw LLM response (may include markdown or prose around JSON)
            reference_close: Last close price — used when model returns HOLD with 0/omitted prices
            
        Returns:
            Parsed decision dictionary or None if invalid
        """
        try:
            raw = (response or "").strip()
            if not raw:
                return None
            # Strip common markdown fences (may be incomplete if model trails off)
            if raw.startswith("```json"):
                raw = raw[7:].strip()
            elif raw.startswith("```"):
                raw = raw[3:].strip()
            if raw.endswith("```"):
                raw = raw[:-3].strip()

            start = raw.find("{")
            if start < 0:
                logger.error("LLM response has no JSON object start")
                return None
            decoder = json.JSONDecoder()
            decision, _end = decoder.raw_decode(raw[start:])
            if not isinstance(decision, dict):
                return None

            action = str(decision.get("action", "HOLD")).strip().upper()
            if action not in ("BUY", "SELL", "HOLD"):
                logger.error("Invalid action: %s", decision.get("action"))
                return None

            confidence = float(decision.get("confidence", 0))
            # Some models return 0–1 instead of 0–100
            if 0 < confidence <= 1.0:
                confidence *= 100.0
            if not (0 <= confidence <= 100):
                logger.error("Invalid confidence: %s", confidence)
                return None

            ref = float(reference_close or 0.0)
            if ref <= 0:
                ref = 1.0

            if action == "HOLD":
                # Models often output zeros or omit prices for HOLD; do not treat as parse failure.
                entry_price = float(decision.get("entry_price") or 0)
                stop_loss = float(decision.get("stop_loss") or 0)
                target = float(decision.get("target") or 0)
                if entry_price <= 0:
                    entry_price = ref
                if stop_loss <= 0:
                    stop_loss = entry_price
                if target <= 0:
                    target = entry_price
            else:
                entry_price = float(decision.get("entry_price", 0))
                stop_loss = float(decision.get("stop_loss", 0))
                target = float(decision.get("target", 0))
                if entry_price <= 0 or stop_loss <= 0 or target <= 0:
                    logger.error("Invalid price values for %s", action)
                    return None

            reason = str(decision.get("reason") or "").strip() or "—"

            return {
                "action": action,
                "confidence": confidence,
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "target": target,
                "reason": reason,
            }

        except json.JSONDecodeError as e:
            logger.error(
                "JSON parsing error: %s | snippet: %s",
                e,
                ((response or "").strip()[:400]),
            )
            return None
        except Exception as e:
            logger.error("Response parsing error: %s", e)
            return None
    
    def generate_decision(self, ohlc_data: Dict, indicators: Dict, position: Dict = None) -> TradingDecision:
        """
        Generate LLM-based trading decision.
        
        Args:
            ohlc_data: Latest OHLC data
            indicators: Technical indicators
            position: Current position (if any)
            
        Returns:
            TradingDecision object
        """
        logger.info("Generating LLM trading decision...")
        
        # Create trading prompt
        prompt = self.create_trading_prompt(ohlc_data, indicators, position)
        
        # Call LLM API
        response = self.call_llm_api(prompt)
        
        if not response:
            logger.error("Failed to get LLM response")
            return self._create_hold_decision(self.last_api_error or "API Error")
        
        # Parse response
        ref_close = float(
            ohlc_data.get("close")
            or ohlc_data.get("Close")
            or 0.0
        )
        decision_dict = self.parse_llm_response(response, reference_close=ref_close)
        
        if not decision_dict:
            logger.error(
                "Failed to parse LLM response | head: %s",
                (response or "").strip()[:500],
            )
            return self._create_hold_decision("Parse Error")
        
        action = str(decision_dict.get("action") or "HOLD").upper()
        # Confidence gate applies only to actionable entries/exits.
        if action in ("BUY", "SELL") and decision_dict["confidence"] < self.min_confidence:
            logger.info(
                "Confidence too low: %s%% < %s%%",
                decision_dict["confidence"],
                self.min_confidence,
            )
            tail = (decision_dict.get("reason") or "").strip()
            msg = (
                f"Low confidence for {action} ({decision_dict['confidence']:.1f}% "
                f"< {self.min_confidence:.1f}%)"
            )
            if tail:
                msg = f"{msg}: {tail}"
            return self._create_hold_decision(msg)
        
        # Calculate risk-reward ratio
        entry_price = decision_dict['entry_price']
        stop_loss = decision_dict['stop_loss']
        target = decision_dict['target']
        
        risk = abs(entry_price - stop_loss)
        reward = abs(target - entry_price)
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        # Validate risk-reward ratio
        if risk_reward_ratio < 1.5:
            logger.warning(f"Low risk-reward ratio: {risk_reward_ratio:.2f}")
        
        # Create decision object
        decision = TradingDecision(
            action=action,
            confidence=decision_dict['confidence'],
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            reason=decision_dict['reason'],
            timestamp=datetime.now().isoformat(),
            risk_reward_ratio=risk_reward_ratio
        )
        
        logger.info(f"LLM Decision: {decision.action} @ ₹{decision.entry_price:.2f} "
                   f"(Confidence: {decision.confidence}%, R:R = {decision.risk_reward_ratio:.2f})")
        
        return decision
    
    def _create_hold_decision(self, reason: str) -> TradingDecision:
        """
        Create a default HOLD decision.
        
        Args:
            reason: Reason for holding
            
        Returns:
            HOLD TradingDecision
        """
        return TradingDecision(
            action="HOLD",
            confidence=0.0,
            entry_price=0.0,
            stop_loss=0.0,
            target=0.0,
            reason=reason,
            timestamp=datetime.now().isoformat(),
            risk_reward_ratio=0.0
        )
    
    def to_dict(self, decision: TradingDecision) -> Dict:
        """
        Convert TradingDecision to dictionary.
        
        Args:
            decision: TradingDecision object
            
        Returns:
            Dictionary representation
        """
        return asdict(decision)


# Example usage and testing
if __name__ == "__main__":
    # Test the LLM engine
    engine = LLMTradingEngine()
    
    # Sample data
    ohlc_data = {
        'open': 28100.0,
        'high': 28200.0,
        'low': 28050.0,
        'close': 28150.0,
        'volume': 1500
    }
    
    indicators = {
        'RSI': 55.5,
        'MACD': 12.3,
        'ATR': 85.5,
        'SMA_20': 28080.0,
        'EMA_12': 28120.0,
        'volume_ratio': 1.2,
        'trend_strength': 0.3
    }
    
    # Generate decision
    decision = engine.generate_decision(ohlc_data, indicators)
    
    print("=== LLM TRADING DECISION ===")
    print(f"Action: {decision.action}")
    print(f"Confidence: {decision.confidence}%")
    print(f"Entry: ₹{decision.entry_price:.2f}")
    print(f"Stop Loss: ₹{decision.stop_loss:.2f}")
    print(f"Target: ₹{decision.target:.2f}")
    print(f"Reason: {decision.reason}")
    print(f"Risk-Reward: {decision.risk_reward_ratio:.2f}")
    print("=" * 30)
