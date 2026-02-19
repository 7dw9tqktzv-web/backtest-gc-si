"""
MCP Server : IBKR Implied Volatility pour GC/SI
Connexion TWS via ib_insync, port 7497 (TWS live/paper).

Usage : configure dans .mcp.json
"""

import nest_asyncio
nest_asyncio.apply()

import shutil
from datetime import datetime, date as date_type
from pathlib import Path

import pandas as pd
from fastmcp import FastMCP
from ib_insync import IB, ContFuture, Future, FuturesOption

mcp = FastMCP("IBKR Volatility")

TWS_HOST = "127.0.0.1"
TWS_PORT = 7497
CLIENT_ID = 50  # ID dedie MCP, evite conflit avec autres clients
VOL_METRICS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "vol_metrics"


@mcp.tool
def ping() -> str:
    """Test de connectivite MCP. Retourne 'pong'."""
    return "pong"


@mcp.tool
def connect_tws() -> dict:
    """Connexion a TWS/Gateway et retourne le statut (compte, heure serveur)."""
    ib = IB()
    try:
        ib.connect(TWS_HOST, TWS_PORT, clientId=CLIENT_ID, timeout=10)
        account = ib.managedAccounts()[0] if ib.managedAccounts() else "unknown"
        account_masked = f"***{account[-4:]}" if len(account) > 4 else account
        server_time = str(ib.reqCurrentTime())
        result = {
            "status": "connected",
            "account": account_masked,
            "server_time": server_time,
            "host": TWS_HOST,
            "port": TWS_PORT,
        }
    except Exception as e:
        result = {
            "status": "error",
            "message": str(e) or repr(e),
            "error_type": type(e).__name__,
            "host": TWS_HOST,
            "port": TWS_PORT,
        }
    finally:
        if ib.isConnected():
            ib.disconnect()
    return result


def _find_nearest_expiry(expirations: list[str], target_dte: int = 30) -> str:
    """Trouve l'expiration la plus proche de target_dte jours."""
    today = datetime.now().date()
    best = None
    best_diff = float("inf")
    min_dte = max(5, target_dte // 3)  # Au moins 5 jours, evite options quasi-expirees
    for exp_str in expirations:
        exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
        dte = (exp_date - today).days
        if dte < min_dte:
            continue
        diff = abs(dte - target_dte)
        if diff < best_diff:
            best_diff = diff
            best = exp_str
    return best


def _resolve_option_chain(ib: IB, symbol: str, exchange: str, opt_exchange: str,
                          opt_symbol: str = "", target_dte: int = 30) -> dict:
    """Trouve le future, son prix, et la chaine d'options la plus proche de target_dte.
    opt_symbol: tradingClass regulier (ex: 'OG', 'SO') — priorise sur les weeklies.

    Retourne dict avec keys: fut_contract, fut_price, chain, expiry, dte, strikes, atm_strike.
    Ou dict avec key 'error' si echec.
    """
    fut = Future(symbol=symbol, exchange=exchange)
    all_contracts = ib.reqContractDetails(fut)
    if not all_contracts:
        return {"error": f"Aucun contrat future trouve pour {symbol}"}

    sorted_contracts = sorted(all_contracts, key=lambda c: c.contract.lastTradeDateOrContractMonth)

    fut_contract = None
    chains = []
    min_dte = max(5, target_dte // 3)
    today = datetime.now().date()

    for cd in sorted_contracts:
        candidate = cd.contract
        ib.qualifyContracts(candidate)
        candidate_chains = ib.reqSecDefOptParams(candidate.symbol, candidate.exchange,
                                                  candidate.secType, candidate.conId)
        if not candidate_chains:
            continue
        # Merger toutes les expirations des chaines du bon exchange
        comex_chains = [ch for ch in candidate_chains if ch.exchange == opt_exchange]
        if not comex_chains:
            comex_chains = candidate_chains
        all_expirations = set()
        for ch in comex_chains:
            all_expirations.update(ch.expirations)
        has_valid = any(
            (datetime.strptime(exp_str, "%Y%m%d").date() - today).days >= min_dte
            for exp_str in all_expirations
        )
        if has_valid:
            chains = comex_chains
            fut_contract = candidate
            break

    if fut_contract is None:
        diag = []
        for cd in sorted_contracts[:4]:
            c = cd.contract
            ib.qualifyContracts(c)
            ch = ib.reqSecDefOptParams(c.symbol, c.exchange, c.secType, c.conId)
            exps = {}
            for x in ch:
                key = f"{x.exchange}/{x.tradingClass}"
                exps[key] = sorted(list(x.expirations))[:5]
            diag.append({"future": c.localSymbol, "expiry": c.lastTradeDateOrContractMonth,
                         "opt_chains": exps})
        return {"error": f"Aucun future avec options valides (min_dte={min_dte}) pour {symbol}",
                "diagnostic": diag}

    [ticker] = ib.reqTickers(fut_contract)
    fut_price = ticker.marketPrice()
    if fut_price != fut_price:
        fut_price = ticker.close
    if fut_price != fut_price:
        return {"error": f"Pas de prix pour {symbol}", "contract": fut_contract.localSymbol}

    # Prioriser la chaine reguliere (tradingClass == opt_symbol, ex: "OG", "SO")
    # Plus liquide que les weeklies. Fallback sur toutes les chaines si pas d'expiration valide.
    regular_chains = [ch for ch in chains if ch.tradingClass == opt_symbol]
    expiry = None
    best_chain = None

    # Essai 1 : chaine reguliere
    if regular_chains:
        reg_expirations = set()
        for ch in regular_chains:
            reg_expirations.update(ch.expirations)
        expiry = _find_nearest_expiry(list(reg_expirations), target_dte)
        if expiry is not None:
            for ch in regular_chains:
                if expiry in ch.expirations:
                    best_chain = ch
                    break

    # Essai 2 : fallback toutes les chaines COMEX
    if expiry is None:
        all_expirations = set()
        for ch in chains:
            all_expirations.update(ch.expirations)
        expiry = _find_nearest_expiry(list(all_expirations), target_dte)
        if expiry is not None:
            for ch in chains:
                if expiry in ch.expirations:
                    best_chain = ch
                    break

    if expiry is None or best_chain is None:
        all_exps = set()
        for ch in chains:
            all_exps.update(ch.expirations)
        return {"error": "Aucune expiration valide trouvee",
                "all_expirations": sorted(list(all_exps)),
                "chains": [{"tradingClass": ch.tradingClass, "expirations": sorted(list(ch.expirations))[:5]} for ch in chains]}

    dte = (datetime.strptime(expiry, "%Y%m%d").date() - datetime.now().date()).days
    strikes = sorted(best_chain.strikes)
    if not strikes:
        return {"error": f"Aucun strike disponible pour {symbol}", "expiry": expiry}
    atm_strike = min(strikes, key=lambda s: abs(s - fut_price))

    return {
        "fut_contract": fut_contract,
        "fut_price": fut_price,
        "expiry": expiry,
        "dte": dte,
        "strikes": strikes,
        "atm_strike": atm_strike,
        "tradingClass": best_chain.tradingClass,
    }


def _get_atm_iv(ib: IB, symbol: str, exchange: str, opt_exchange: str,
                opt_symbol: str, target_dte: int = 30) -> dict:
    """Recupere l'IV ATM pour un future : prix future, strike ATM, IV call+put."""
    info = _resolve_option_chain(ib, symbol, exchange, opt_exchange, opt_symbol, target_dte)
    if "error" in info:
        return info

    fut_price = info["fut_price"]
    expiry = info["expiry"]
    dte = info["dte"]
    atm_strike = info["atm_strike"]
    tc = info.get("tradingClass", opt_symbol)

    call = FuturesOption(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                  strike=atm_strike, right="C", exchange=opt_exchange,
                  tradingClass=tc)
    put = FuturesOption(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                 strike=atm_strike, right="P", exchange=opt_exchange,
                 tradingClass=tc)
    qualified = ib.qualifyContracts(call, put)
    qualified = [q for q in qualified if q.conId > 0]

    if not qualified:
        return {"error": f"qualifyContracts vide pour {symbol} (strike={atm_strike}, expiry={expiry})",
                "expiry": expiry, "atm_strike": atm_strike}

    tickers = ib.reqTickers(*qualified)
    if not tickers:
        return {"error": f"reqTickers vide pour {symbol}", "expiry": expiry}
    for _ in range(5):
        if not ib.isConnected():
            break
        ib.sleep(1)
        if all(t.modelGreeks for t in tickers):
            break

    result = {
        "symbol": symbol,
        "future_price": fut_price,
        "expiry": expiry,
        "dte": dte,
        "atm_strike": atm_strike,
    }

    for t, right in zip(tickers, ["call", "put"]):
        # Model IV (TWS proprietary model)
        greeks = t.modelGreeks
        if greeks and greeks.impliedVol is not None and greeks.delta is not None:
            result[f"model_iv_{right}"] = round(float(greeks.impliedVol) * 100, 2)
            result[f"delta_{right}"] = round(float(greeks.delta), 4)
        else:
            result[f"model_iv_{right}"] = None
            result[f"delta_{right}"] = None
        # Market IV (mid bid/ask greeks)
        bid_iv = ask_iv = None
        if t.bidGreeks and t.bidGreeks.impliedVol is not None:
            bid_iv = float(t.bidGreeks.impliedVol) * 100
        if t.askGreeks and t.askGreeks.impliedVol is not None:
            ask_iv = float(t.askGreeks.impliedVol) * 100
        if bid_iv is not None and ask_iv is not None:
            result[f"market_iv_{right}"] = round((bid_iv + ask_iv) / 2, 2)
        elif bid_iv is not None:
            result[f"market_iv_{right}"] = round(bid_iv, 2)
        elif ask_iv is not None:
            result[f"market_iv_{right}"] = round(ask_iv, 2)
        else:
            result[f"market_iv_{right}"] = None

    return result


def _get_risk_reversal(ib: IB, symbol: str, exchange: str, opt_exchange: str,
                       opt_symbol: str, target_dte: int = 30,
                       iv_spread_threshold: float = 4.0) -> dict:
    """Calcule RR25 et RR10 pour un symbole via IV par delta.
    iv_spread_threshold: seuil bid-ask IV spread pour confidence (4 pour OG, 8 pour SO)."""
    info = _resolve_option_chain(ib, symbol, exchange, opt_exchange, opt_symbol, target_dte)
    if "error" in info:
        return info

    fut_price = info["fut_price"]
    expiry = info["expiry"]
    dte = info["dte"]
    strikes = info["strikes"]
    atm_strike = info["atm_strike"]
    tc = info.get("tradingClass", opt_symbol)

    # Filtrer strikes dans +-20% autour du prix ATM
    lo = fut_price * 0.80
    hi = fut_price * 1.20
    nearby_strikes = [s for s in strikes if lo <= s <= hi]

    if not nearby_strikes:
        return {"error": f"Aucun strike dans +-20% de {fut_price}", "symbol": symbol}

    # Qualifier calls et puts en batch
    options = []
    for s in nearby_strikes:
        options.append(FuturesOption(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                              strike=s, right="C", exchange=opt_exchange,
                              tradingClass=tc))
        options.append(FuturesOption(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                              strike=s, right="P", exchange=opt_exchange,
                              tradingClass=tc))

    qualified = ib.qualifyContracts(*options)
    qualified = [q for q in qualified if q is not None]

    if not qualified:
        return {"error": "Aucune option qualifiee", "symbol": symbol}

    # Recuperer les Greeks en batch avec polling
    tickers = ib.reqTickers(*qualified)
    if not tickers:
        return {"error": f"reqTickers vide pour {symbol}", "strikes_analyzed": len(nearby_strikes)}
    for _ in range(5):
        if not ib.isConnected():
            break
        ib.sleep(1)
        if all(t.modelGreeks for t in tickers):
            break

    # Construire la table strike/right/delta/iv + bid/ask IV spread
    rows = []
    for t in tickers:
        g = t.modelGreeks
        if g and g.delta is not None and g.impliedVol is not None:
            bid_iv = float(t.bidGreeks.impliedVol) * 100 if (t.bidGreeks and t.bidGreeks.impliedVol is not None) else None
            ask_iv = float(t.askGreeks.impliedVol) * 100 if (t.askGreeks and t.askGreeks.impliedVol is not None) else None
            iv_spread = round(ask_iv - bid_iv, 2) if (bid_iv is not None and ask_iv is not None) else None
            rows.append({
                "strike": t.contract.strike,
                "right": t.contract.right,
                "delta": float(g.delta),
                "iv": float(g.impliedVol) * 100,
                "iv_spread": iv_spread,
            })

    market_open = len(rows) > 0

    result = {
        "symbol": symbol,
        "future_price": fut_price,
        "expiry": expiry,
        "dte": dte,
        "atm_strike": atm_strike,
        "strikes_analyzed": len(nearby_strikes),
        "market_open": market_open,
    }

    if not market_open:
        result["rr25"] = None
        result["rr10"] = None
        return result

    calls = [r for r in rows if r["right"] == "C"]
    puts = [r for r in rows if r["right"] == "P"]

    # Trouver les options les plus proches des deltas cibles
    DELTA_TOLERANCE = 0.05

    for label, target_delta in [("rr25", 0.25), ("rr10", 0.10)]:
        # Call : delta le plus proche de +target_delta
        best_call = min(calls, key=lambda r: abs(r["delta"] - target_delta)) if calls else None
        # Put : delta le plus proche de -target_delta (comparer en valeur absolue)
        best_put = min(puts, key=lambda r: abs(abs(r["delta"]) - target_delta)) if puts else None

        call_gap = abs(best_call["delta"] - target_delta) if best_call else 999
        put_gap = abs(abs(best_put["delta"]) - target_delta) if best_put else 999


        if (best_call and best_put
                and call_gap <= DELTA_TOLERANCE
                and put_gap <= DELTA_TOLERANCE):
            rr_val = round(best_call["iv"] - best_put["iv"], 2)
            result[label] = rr_val
            call_ivs = best_call.get("iv_spread")
            put_ivs = best_put.get("iv_spread")
            max_ivs = max(call_ivs or 0, put_ivs or 0)
            result[f"{label}_call"] = {
                "strike": best_call["strike"],
                "delta": round(best_call["delta"], 4),
                "iv": round(best_call["iv"], 2),
                "delta_gap": round(call_gap, 4),
                "iv_spread": call_ivs,
            }
            result[f"{label}_put"] = {
                "strike": best_put["strike"],
                "delta": round(best_put["delta"], 4),
                "iv": round(best_put["iv"], 2),
                "delta_gap": round(put_gap, 4),
                "iv_spread": put_ivs,
            }
            # Confidence basee sur le bid-ask IV spread (cause directe d'instabilite)
            if call_ivs is None or put_ivs is None:
                result[f"{label}_confidence"] = "N/A"
            elif max_ivs <= iv_spread_threshold * 0.5:
                result[f"{label}_confidence"] = "HIGH"
            elif max_ivs <= iv_spread_threshold:
                result[f"{label}_confidence"] = "MEDIUM"
            else:
                result[f"{label}_confidence"] = "LOW"
        else:
            result[label] = None
            result[f"{label}_reliable"] = False
            if best_call:
                result[f"{label}_call_nearest"] = {
                    "strike": best_call["strike"],
                    "delta": round(best_call["delta"], 4),
                    "delta_gap": round(abs(best_call["delta"] - target_delta), 4),
                }
            if best_put:
                result[f"{label}_put_nearest"] = {
                    "strike": best_put["strike"],
                    "delta": round(best_put["delta"], 4),
                    "delta_gap": round(abs(abs(best_put["delta"]) - target_delta), 4),
                }

    return result


@mcp.tool
def get_risk_reversal(target_dte: int = 30) -> dict:
    """RR25 et RR10 pour GC (OG) et SI (SO). Necessite marche ouvert pour les Greeks."""
    ib = IB()
    try:
        ib.connect(TWS_HOST, TWS_PORT, clientId=CLIENT_ID, timeout=10)

        gc_rr = _get_risk_reversal(ib, symbol="GC", exchange="COMEX",
                                   opt_exchange="COMEX", opt_symbol="OG",
                                   target_dte=target_dte, iv_spread_threshold=4.0)
        si_rr = _get_risk_reversal(ib, symbol="SI", exchange="COMEX",
                                   opt_exchange="COMEX", opt_symbol="SO",
                                   target_dte=target_dte, iv_spread_threshold=8.0)

        has_data = any(
            d.get("market_open", False) for d in [gc_rr, si_rr] if "error" not in d
        )

        server_time = str(ib.reqCurrentTime()) if ib.isConnected() else "N/A"
        return {
            "status": "ok",
            "market_open": has_data,
            "server_time": server_time,
            "GC": gc_rr,
            "SI": si_rr,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e) or repr(e),
            "error_type": type(e).__name__,
        }
    finally:
        if ib.isConnected():
            ib.disconnect()


@mcp.tool
def get_skew_signal(target_dte: int = 30) -> dict:
    """Signal de divergence skew GC vs SI. Compare RR25 des deux metaux. Necessite TWS + marche ouvert."""
    ib = IB()
    try:
        ib.connect(TWS_HOST, TWS_PORT, clientId=CLIENT_ID, timeout=10)

        gc_rr = _get_risk_reversal(ib, symbol="GC", exchange="COMEX",
                                   opt_exchange="COMEX", opt_symbol="OG",
                                   target_dte=target_dte, iv_spread_threshold=4.0)
        si_rr = _get_risk_reversal(ib, symbol="SI", exchange="COMEX",
                                   opt_exchange="COMEX", opt_symbol="SO",
                                   target_dte=target_dte, iv_spread_threshold=8.0)

        server_time = str(ib.reqCurrentTime()) if ib.isConnected() else "N/A"

        gc_rr25 = gc_rr.get("rr25") if "error" not in gc_rr else None
        si_rr25 = si_rr.get("rr25") if "error" not in si_rr else None
        gc_rr10 = gc_rr.get("rr10") if "error" not in gc_rr else None
        si_rr10 = si_rr.get("rr10") if "error" not in si_rr else None

        # Confidence : basee sur le bid-ask IV spread des legs RR25
        gc_conf = gc_rr.get("rr25_confidence", "N/A") if "error" not in gc_rr else "N/A"
        si_conf = si_rr.get("rr25_confidence", "N/A") if "error" not in si_rr else "N/A"
        # Confidence globale = la pire des deux
        conf_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "N/A": 0}
        overall_conf = min([gc_conf, si_conf], key=lambda c: conf_rank.get(c, 0))

        # Signal divergence : signes opposes sur RR25
        if gc_rr25 is not None and si_rr25 is not None:
            divergent = (gc_rr25 > 0) != (si_rr25 > 0)
            signal = "SKEW_DIVERGENT" if divergent else "SKEW_ALIGNED"
            signal_color = "ORANGE" if divergent else "GREEN"
            # Degrader si low confidence ou N/A (bidGreeks manquants)
            if overall_conf in ("LOW", "N/A"):
                signal = f"{signal} (LOW_CONF)"
                signal_color = "GRAY"
        else:
            divergent = None
            signal = "N/A"
            signal_color = "GRAY"

        return {
            "status": "ok",
            "server_time": server_time,
            "target_dte": target_dte,
            "skew": {
                "gc_rr25": gc_rr25,
                "si_rr25": si_rr25,
                "gc_rr10": gc_rr10,
                "si_rr10": si_rr10,
                "divergent": divergent,
                "signal": signal,
                "signal_color": signal_color,
                "confidence": overall_conf,
                "gc_confidence": gc_conf,
                "si_confidence": si_conf,
            },
            "details": {
                "GC": {
                    "expiry": gc_rr.get("expiry"),
                    "dte": gc_rr.get("dte"),
                    "future_price": gc_rr.get("future_price"),
                    "rr25_call": gc_rr.get("rr25_call"),
                    "rr25_put": gc_rr.get("rr25_put"),
                } if "error" not in gc_rr else {"error": gc_rr.get("error")},
                "SI": {
                    "expiry": si_rr.get("expiry"),
                    "dte": si_rr.get("dte"),
                    "future_price": si_rr.get("future_price"),
                    "rr25_call": si_rr.get("rr25_call"),
                    "rr25_put": si_rr.get("rr25_put"),
                } if "error" not in si_rr else {"error": si_rr.get("error")},
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e) or repr(e),
            "error_type": type(e).__name__,
        }
    finally:
        if ib.isConnected():
            ib.disconnect()


@mcp.tool
def get_iv_snapshot(target_dte: int = 30) -> dict:
    """Snapshot IV ATM pour GC (Gold) et SI (Silver), expiration ~target_dte jours."""
    ib = IB()
    try:
        ib.connect(TWS_HOST, TWS_PORT, clientId=CLIENT_ID, timeout=10)

        gc_iv = _get_atm_iv(ib, symbol="GC", exchange="COMEX",
                            opt_exchange="COMEX", opt_symbol="OG", target_dte=target_dte)
        si_iv = _get_atm_iv(ib, symbol="SI", exchange="COMEX",
                            opt_exchange="COMEX", opt_symbol="SO", target_dte=target_dte)

        has_iv = any(
            d.get(f"model_iv_{r}") is not None
            for d in [gc_iv, si_iv] if "error" not in d
            for r in ["call", "put"]
        )

        server_time = str(ib.reqCurrentTime()) if ib.isConnected() else "N/A"
        return {
            "status": "ok",
            "market_open": has_iv,
            "server_time": server_time,
            "GC": gc_iv,
            "SI": si_iv,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e) or repr(e),
            "error_type": type(e).__name__,
        }
    finally:
        if ib.isConnected():
            ib.disconnect()


def _collect_symbol_metrics(ib: IB, symbol: str, exchange: str, opt_exchange: str,
                            opt_symbol: str, target_dte: int = 30,
                            iv_spread_threshold: float = 4.0) -> dict:
    """Collecte IV ATM + RR25/RR10 pour un symbole avec UNE seule resolution de chaine.
    Retourne un dict avec toutes les metriques pour le daily snapshot."""
    info = _resolve_option_chain(ib, symbol, exchange, opt_exchange, opt_symbol, target_dte)
    if "error" in info:
        return {"error": info["error"], "symbol": symbol}

    fut_price = info["fut_price"]
    expiry = info["expiry"]
    dte = info["dte"]
    atm_strike = info["atm_strike"]
    strikes = info["strikes"]
    tc = info.get("tradingClass", opt_symbol)

    # --- IV ATM (call + put ATM) ---
    call = FuturesOption(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                         strike=atm_strike, right="C", exchange=opt_exchange,
                         tradingClass=tc)
    put = FuturesOption(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                        strike=atm_strike, right="P", exchange=opt_exchange,
                        tradingClass=tc)
    qualified_atm = [q for q in ib.qualifyContracts(call, put) if q.conId > 0]

    model_iv_call = model_iv_put = market_iv_call = market_iv_put = None
    if qualified_atm:
        atm_tickers = ib.reqTickers(*qualified_atm)
        for _ in range(5):
            if not ib.isConnected():
                break
            ib.sleep(1)
            if all(t.modelGreeks for t in atm_tickers):
                break
        for t, right in zip(atm_tickers, ["call", "put"]):
            g = t.modelGreeks
            if g and g.impliedVol is not None:
                if right == "call":
                    model_iv_call = round(float(g.impliedVol) * 100, 2)
                else:
                    model_iv_put = round(float(g.impliedVol) * 100, 2)
            bid_iv = float(t.bidGreeks.impliedVol) * 100 if (t.bidGreeks and t.bidGreeks.impliedVol is not None) else None
            ask_iv = float(t.askGreeks.impliedVol) * 100 if (t.askGreeks and t.askGreeks.impliedVol is not None) else None
            mid_iv = round((bid_iv + ask_iv) / 2, 2) if (bid_iv is not None and ask_iv is not None) else (
                round(bid_iv, 2) if bid_iv is not None else (round(ask_iv, 2) if ask_iv is not None else None))
            if right == "call":
                market_iv_call = mid_iv
            else:
                market_iv_put = mid_iv

    # Moyenne call/put
    model_iv_atm = round((model_iv_call + model_iv_put) / 2, 2) if (model_iv_call is not None and model_iv_put is not None) else (model_iv_call or model_iv_put)
    market_iv_atm = round((market_iv_call + market_iv_put) / 2, 2) if (market_iv_call is not None and market_iv_put is not None) else (market_iv_call or market_iv_put)

    # --- RR25/RR10 (reutilise les memes strikes de la chaine) ---
    lo = fut_price * 0.80
    hi = fut_price * 1.20
    nearby_strikes = [s for s in strikes if lo <= s <= hi]

    rr25 = rr10 = rr25_confidence = None
    rr25_iv_spread = None
    rr_data = {}

    if nearby_strikes:
        options = []
        for s in nearby_strikes:
            options.append(FuturesOption(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                                        strike=s, right="C", exchange=opt_exchange, tradingClass=tc))
            options.append(FuturesOption(symbol=symbol, lastTradeDateOrContractMonth=expiry,
                                        strike=s, right="P", exchange=opt_exchange, tradingClass=tc))
        qualified_rr = [q for q in ib.qualifyContracts(*options) if q is not None]
        if qualified_rr:
            rr_tickers = ib.reqTickers(*qualified_rr)
            for _ in range(5):
                if not ib.isConnected():
                    break
                ib.sleep(1)
                if all(t.modelGreeks for t in rr_tickers):
                    break

            rows = []
            for t in rr_tickers:
                g = t.modelGreeks
                if g and g.delta is not None and g.impliedVol is not None:
                    bid_iv = float(t.bidGreeks.impliedVol) * 100 if (t.bidGreeks and t.bidGreeks.impliedVol is not None) else None
                    ask_iv = float(t.askGreeks.impliedVol) * 100 if (t.askGreeks and t.askGreeks.impliedVol is not None) else None
                    iv_sp = round(ask_iv - bid_iv, 2) if (bid_iv is not None and ask_iv is not None) else None
                    rows.append({"strike": t.contract.strike, "right": t.contract.right,
                                 "delta": float(g.delta), "iv": float(g.impliedVol) * 100, "iv_spread": iv_sp})

            calls_rr = [r for r in rows if r["right"] == "C"]
            puts_rr = [r for r in rows if r["right"] == "P"]
            DELTA_TOL = 0.05

            for label, target_d in [("rr25", 0.25), ("rr10", 0.10)]:
                bc = min(calls_rr, key=lambda r: abs(r["delta"] - target_d)) if calls_rr else None
                bp = min(puts_rr, key=lambda r: abs(abs(r["delta"]) - target_d)) if puts_rr else None
                cg = abs(bc["delta"] - target_d) if bc else 999
                pg = abs(abs(bp["delta"]) - target_d) if bp else 999
                if bc and bp and cg <= DELTA_TOL and pg <= DELTA_TOL:
                    rr_val = round(bc["iv"] - bp["iv"], 2)
                    c_ivs = bc.get("iv_spread")
                    p_ivs = bp.get("iv_spread")
                    max_ivs = max(c_ivs or 0, p_ivs or 0)
                    if c_ivs is None or p_ivs is None:
                        conf = "N/A"
                    elif max_ivs <= iv_spread_threshold * 0.5:
                        conf = "HIGH"
                    elif max_ivs <= iv_spread_threshold:
                        conf = "MEDIUM"
                    else:
                        conf = "LOW"
                    rr_data[label] = rr_val
                    rr_data[f"{label}_confidence"] = conf
                    rr_data[f"{label}_iv_spread"] = round(max_ivs, 2) if max_ivs else None

    return {
        "symbol": symbol,
        "future_price": fut_price,
        "expiry": expiry,
        "dte": dte,
        "model_iv_atm": model_iv_atm,
        "market_iv_atm": market_iv_atm,
        "rr25": rr_data.get("rr25"),
        "rr25_confidence": rr_data.get("rr25_confidence"),
        "rr25_iv_spread": rr_data.get("rr25_iv_spread"),
        "rr10": rr_data.get("rr10"),
    }


def _compute_signals_summary(row: dict, history_df: pd.DataFrame | None) -> dict:
    """Calcule les 5 signaux du daily snapshot avec code couleur."""
    signals = {}

    # --- REGIME : ratio_iv z-score 60d ---
    if history_df is not None and len(history_df) >= 60 and row.get("ratio_iv") is not None:
        ratio_60 = history_df["ratio_iv"].iloc[-60:]
        z = (row["ratio_iv"] - float(ratio_60.mean())) / float(ratio_60.std()) if ratio_60.std() > 0 else 0.0
        z = round(z, 2)
        if abs(z) > 2.0:
            color = "RED"
        elif abs(z) > 1.5:
            color = "ORANGE"
        elif abs(z) > 1.0:
            color = "YELLOW"
        else:
            color = "GREEN"
        signals["REGIME"] = {"color": color, "detail": f"ratio_iv z={z}"}
    else:
        signals["REGIME"] = {"color": "GRAY", "detail": "N/A, pas d'historique"}

    # --- VRP_GC et VRP_SI : z-score 60d ---
    for sym in ["GC", "SI"]:
        col = f"vrp_{sym.lower()}"
        sig_name = f"VRP_{sym}"
        if history_df is not None and len(history_df) >= 60 and col in history_df.columns:
            vrp_60 = history_df[col].iloc[-60:]
            vrp_now = float(vrp_60.iloc[-1])
            z = (vrp_now - float(vrp_60.mean())) / float(vrp_60.std()) if vrp_60.std() > 0 else 0.0
            z = round(z, 2)
            if pd.isna(z):
                signals[sig_name] = {"color": "GRAY", "detail": "VRP z=NaN (donnees manquantes)"}
                continue
            if abs(z) > 2.0:
                color = "RED"
            elif abs(z) > 1.5:
                color = "ORANGE"
            elif abs(z) > 1.0:
                color = "YELLOW"
            else:
                color = "GREEN"
            signals[sig_name] = {"color": color, "detail": f"VRP z={z}"}
        else:
            signals[sig_name] = {"color": "GRAY", "detail": "N/A, pas d'historique"}

    # --- SKEW : RR25 GC vs SI sign + confidence ---
    gc_rr25 = row.get("gc_rr25")
    si_rr25 = row.get("si_rr25")
    gc_conf = row.get("gc_rr25_confidence", "N/A")
    si_conf = row.get("si_rr25_confidence", "N/A")
    conf_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "N/A": 0}
    worst_conf = min([gc_conf, si_conf], key=lambda c: conf_rank.get(c, 0))

    if gc_rr25 is not None and si_rr25 is not None:
        divergent = (gc_rr25 > 0) != (si_rr25 > 0)
        if divergent and worst_conf == "HIGH":
            color = "RED"
        elif divergent or worst_conf in ("LOW", "N/A"):
            color = "ORANGE"
        elif worst_conf == "MEDIUM":
            color = "YELLOW"
        else:
            color = "GREEN"
        label = "DIVERGENT" if divergent else "ALIGNED"
        signals["SKEW"] = {"color": color, "detail": f"SKEW_{label}, worst_conf={worst_conf}"}
    else:
        signals["SKEW"] = {"color": "GRAY", "detail": "N/A, RR25 manquant"}

    # --- DATA : qualite de la collecte ---
    dq = row.get("data_quality", "OK")
    if dq == "OK":
        signals["DATA"] = {"color": "GREEN", "detail": "all metrics collected"}
    elif dq == "PARTIAL":
        signals["DATA"] = {"color": "YELLOW", "detail": "some metrics missing"}
    else:
        signals["DATA"] = {"color": "ORANGE", "detail": f"data_quality={dq}"}

    return signals


@mcp.tool
def collect_daily_snapshot(target_dte: int = 30) -> dict:
    """Collecte quotidienne IV ATM + RR25/RR10 + V30 pour GC et SI. Sauvegarde en Parquet."""
    ib = IB()
    try:
        ib.connect(TWS_HOST, TWS_PORT, clientId=CLIENT_ID, timeout=10)
        VOL_METRICS_DIR.mkdir(parents=True, exist_ok=True)
        collection_time = datetime.now(tz=__import__('datetime').timezone.utc)
        today = collection_time.date()

        # --- Collecte live via shared chain (1 resolve par symbole) ---
        gc = _collect_symbol_metrics(ib, symbol="GC", exchange="COMEX",
                                     opt_exchange="COMEX", opt_symbol="OG",
                                     target_dte=target_dte, iv_spread_threshold=4.0)
        si = _collect_symbol_metrics(ib, symbol="SI", exchange="COMEX",
                                     opt_exchange="COMEX", opt_symbol="SO",
                                     target_dte=target_dte, iv_spread_threshold=8.0)

        server_time = str(ib.reqCurrentTime()) if ib.isConnected() else "N/A"

    except Exception as e:
        return {"status": "error", "message": str(e) or repr(e), "error_type": type(e).__name__}
    finally:
        if ib.isConnected():
            ib.disconnect()

    # Verifier qu'on a au moins des donnees de prix
    if "error" in gc and "error" in si:
        return {"status": "error", "message": f"GC: {gc['error']}, SI: {si['error']}"}

    # --- V30 depuis parquets existants ---
    gc_v30 = si_v30 = ratio_iv = None
    v30_date = None
    v30_stale = False
    gc_path = VOL_METRICS_DIR / "iv_history_GC.parquet"
    si_path = VOL_METRICS_DIR / "iv_history_SI.parquet"
    history_df = None

    if gc_path.exists() and si_path.exists():
        try:
            df_gc = pd.read_parquet(gc_path)
            df_si = pd.read_parquet(si_path)
            if not df_gc.empty and not df_si.empty:
                gc_v30 = round(float(df_gc["v30"].iloc[-1]) * 100, 2)
                si_v30 = round(float(df_si["v30"].iloc[-1]) * 100, 2)
                v30_date_raw = df_gc["date"].iloc[-1]
                v30_date = v30_date_raw.date() if hasattr(v30_date_raw, "date") else v30_date_raw
                # Check V30 staleness (> 5 jours)
                if hasattr(v30_date, "toordinal"):
                    v30_stale = (today - v30_date).days > 5
                if gc_v30 and si_v30 and si_v30 > 0:
                    ratio_iv = round(gc_v30 / si_v30, 4)
                # Construire history_df pour signaux
                history_df = df_gc[["date", "v30", "hv30", "vrp"]].merge(
                    df_si[["date", "v30", "hv30", "vrp"]],
                    on="date", suffixes=("_gc", "_si"),
                ).sort_values("date").reset_index(drop=True)
                history_df["ratio_iv"] = history_df["v30_gc"] / history_df["v30_si"]
        except Exception:
            pass  # V30 non dispo, on continue sans

    # --- Construire la row ---
    row = {
        "date": today,
        "collection_time": collection_time,
        "gc_future_price": gc.get("future_price") if "error" not in gc else None,
        "si_future_price": si.get("future_price") if "error" not in si else None,
        "gc_model_iv_atm": gc.get("model_iv_atm") if "error" not in gc else None,
        "si_model_iv_atm": si.get("model_iv_atm") if "error" not in si else None,
        "gc_market_iv_atm": gc.get("market_iv_atm") if "error" not in gc else None,
        "si_market_iv_atm": si.get("market_iv_atm") if "error" not in si else None,
        "gc_iv_expiry": gc.get("expiry") if "error" not in gc else None,
        "si_iv_expiry": si.get("expiry") if "error" not in si else None,
        "gc_dte": gc.get("dte") if "error" not in gc else None,
        "si_dte": si.get("dte") if "error" not in si else None,
        "gc_rr25": gc.get("rr25") if "error" not in gc else None,
        "si_rr25": si.get("rr25") if "error" not in si else None,
        "gc_rr25_confidence": gc.get("rr25_confidence") if "error" not in gc else None,
        "si_rr25_confidence": si.get("rr25_confidence") if "error" not in si else None,
        "gc_rr25_iv_spread": gc.get("rr25_iv_spread") if "error" not in gc else None,
        "si_rr25_iv_spread": si.get("rr25_iv_spread") if "error" not in si else None,
        "gc_rr10": gc.get("rr10") if "error" not in gc else None,
        "si_rr10": si.get("rr10") if "error" not in si else None,
        "gc_v30": gc_v30,
        "si_v30": si_v30,
        "ratio_iv": ratio_iv,
    }

    # --- Skew signal ---
    gc_rr25 = row["gc_rr25"]
    si_rr25 = row["si_rr25"]
    if gc_rr25 is not None and si_rr25 is not None:
        divergent = (gc_rr25 > 0) != (si_rr25 > 0)
        row["skew_signal"] = "SKEW_DIVERGENT" if divergent else "SKEW_ALIGNED"
    else:
        row["skew_signal"] = "N/A"

    # --- Data quality ---
    data_quality = "OK"
    # Check IV outliers
    for iv_col in ["gc_model_iv_atm", "si_model_iv_atm"]:
        v = row.get(iv_col)
        if v is not None and (v < 0 or v > 200):
            data_quality = "OUTLIER"
    # Check RR25 outliers
    for rr_col in ["gc_rr25", "si_rr25"]:
        v = row.get(rr_col)
        if v is not None and abs(v) > 15:
            data_quality = "OUTLIER"
    # Check partial data
    if data_quality == "OK":
        partial_checks = [
            row["gc_future_price"] is None,
            row["si_future_price"] is None,
            row["gc_rr25_confidence"] in (None, "N/A"),
            row["si_rr25_confidence"] in (None, "N/A"),
            v30_stale,
        ]
        if any(partial_checks):
            data_quality = "PARTIAL"
    row["data_quality"] = data_quality

    # --- Signaux summary ---
    signals = _compute_signals_summary(row, history_df)

    # --- Sauvegarde parquet ---
    snapshot_path = VOL_METRICS_DIR / "daily_snapshots.parquet"
    new_df = pd.DataFrame([row])

    if snapshot_path.exists():
        # Backup
        shutil.copy2(snapshot_path, VOL_METRICS_DIR / "daily_snapshots.bak.parquet")
        existing = pd.read_parquet(snapshot_path)
        # Upsert sur date : garder meilleure qualite
        dq_rank = {"OK": 3, "PARTIAL": 2, "OUTLIER": 1}
        existing_today = existing[existing["date"] == today]
        if not existing_today.empty:
            old_dq = existing_today.iloc[0].get("data_quality", "OUTLIER")
            if dq_rank.get(data_quality, 0) >= dq_rank.get(old_dq, 0):
                existing = existing[existing["date"] != today]
            else:
                # Ancienne row est meilleure, on ne remplace pas
                return {
                    "status": "ok",
                    "action": "skipped",
                    "reason": f"Existing row has better quality ({old_dq} vs {data_quality})",
                    "server_time": server_time,
                }
        final_df = pd.concat([existing, new_df], ignore_index=True).sort_values("date").reset_index(drop=True)
    else:
        final_df = new_df

    final_df.to_parquet(snapshot_path, index=False)

    # --- Summary lines ---
    gc_price = f"${row['gc_future_price']:,.0f}" if row["gc_future_price"] else "N/A"
    si_price = f"${row['si_future_price']:.2f}" if row["si_future_price"] else "N/A"
    gc_iv = f"{row['gc_model_iv_atm']:.1f}%" if row["gc_model_iv_atm"] else "N/A"
    si_iv = f"{row['si_model_iv_atm']:.1f}%" if row["si_model_iv_atm"] else "N/A"
    gc_rr_str = f"{row['gc_rr25']:+.2f}%({row['gc_rr25_confidence']})" if row["gc_rr25"] is not None else "N/A"
    si_rr_str = f"{row['si_rr25']:+.2f}%({row['si_rr25_confidence']})" if row["si_rr25"] is not None else "N/A"

    sig_line = " | ".join(f"{k} {v['color']}" for k, v in signals.items())
    summary_line = f"{today} {collection_time.strftime('%H:%M')} UTC | {sig_line}"
    detail_line = f"GC: {gc_price} IV={gc_iv} RR25={gc_rr_str} | SI: {si_price} IV={si_iv} RR25={si_rr_str}"

    # Interpretation
    colors = [v["color"] for v in signals.values()]
    if all(c == "GREEN" for c in colors):
        interpretation = "Environnement FAVORABLE, tous les signaux au vert"
    elif any(c == "RED" for c in colors):
        red_sigs = [k for k, v in signals.items() if v["color"] == "RED"]
        interpretation = f"ATTENTION: {', '.join(red_sigs)} en zone rouge"
    elif any(c == "ORANGE" for c in colors):
        orange_sigs = [k for k, v in signals.items() if v["color"] == "ORANGE"]
        interpretation = f"PRUDENCE: {', '.join(orange_sigs)} en zone orange"
    elif any(c == "GRAY" for c in colors):
        interpretation = "Donnees incompletes, signaux partiels"
    else:
        interpretation = "Conditions normales, pas de signal extreme"

    return {
        "status": "ok",
        "summary_line": summary_line,
        "detail_line": detail_line,
        "interpretation": interpretation,
        "signals": signals,
        "row": {k: (str(v) if isinstance(v, (datetime, date_type)) else v) for k, v in row.items()},
        "parquet_path": str(snapshot_path),
        "total_rows": len(final_df),
        "server_time": server_time,
        "v30_date": str(v30_date) if v30_date else None,
        "v30_stale": v30_stale,
    }


def _fetch_vol_history(ib: IB, symbol: str, duration: str = "2 Y") -> pd.DataFrame:
    """Telecharge V30 + HV30 daily pour un future continu."""
    contract = ContFuture(symbol=symbol, exchange="COMEX")
    ib.qualifyContracts(contract)

    bars_iv = ib.reqHistoricalData(
        contract, endDateTime="", durationStr=duration,
        barSizeSetting="1 day", whatToShow="OPTION_IMPLIED_VOLATILITY",
        useRTH=True, formatDate=1,
    )
    bars_hv = ib.reqHistoricalData(
        contract, endDateTime="", durationStr=duration,
        barSizeSetting="1 day", whatToShow="HISTORICAL_VOLATILITY",
        useRTH=True, formatDate=1,
    )

    if not bars_iv and not bars_hv:
        return pd.DataFrame()

    df_iv = pd.DataFrame([{"date": b.date, "v30": b.close} for b in bars_iv])
    df_hv = pd.DataFrame([{"date": b.date, "hv30": b.close} for b in bars_hv])

    if df_iv.empty:
        return pd.DataFrame()

    df = df_iv.merge(df_hv, on="date", how="outer").sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    df["symbol"] = symbol

    # Filtre outliers ContFuture : V30 doit etre entre 5% et 100% (HV30 peut depasser 100% legitimement)
    raw_len = len(df)
    df = pd.DataFrame(df[(df["v30"] >= 0.05) & (df["v30"] <= 1.0)]).reset_index(drop=True)
    # Drop trailing rows where HV30 is NaN (intraday: IBKR hasn't computed HV30 yet)
    hv30_notna = df["hv30"].notna()
    if bool(hv30_notna.any()):
        last_valid_pos: int = int(hv30_notna[hv30_notna].index[-1])  # type: ignore[index]
        df = pd.DataFrame(df.iloc[: last_valid_pos + 1]).reset_index(drop=True)
    df["vrp"] = df["v30"] - df["hv30"]
    df.attrs["rows_filtered"] = raw_len - len(df)
    return df


@mcp.tool
def backfill_iv_history(duration: str = "2 Y") -> dict:
    """Backfill historique V30/HV30 pour GC et SI. Sauvegarde en Parquet."""
    ib = IB()
    try:
        ib.connect(TWS_HOST, TWS_PORT, clientId=CLIENT_ID, timeout=10)
        VOL_METRICS_DIR.mkdir(parents=True, exist_ok=True)

        results = {}
        for symbol in ["GC", "SI"]:
            df = _fetch_vol_history(ib, symbol, duration)
            if df.empty:
                results[symbol] = {"status": "error", "message": "Aucune donnee retournee"}
                continue

            path = VOL_METRICS_DIR / f"iv_history_{symbol}.parquet"
            df.to_parquet(path, index=False)
            results[symbol] = {
                "status": "ok",
                "bars": len(df),
                "rows_filtered": df.attrs.get("rows_filtered", 0),
                "date_start": str(df["date"].min().date()),
                "date_end": str(df["date"].max().date()),
                "v30_last": round(float(df["v30"].iloc[-1]) * 100, 2),
                "hv30_last": round(float(df["hv30"].iloc[-1]) * 100, 2),
                "vrp_last": round(float(df["vrp"].iloc[-1]) * 100, 2),
                "path": str(path),
            }

        server_time = str(ib.reqCurrentTime()) if ib.isConnected() else "N/A"
        return {"status": "ok", "server_time": server_time, **results}
    except Exception as e:
        return {"status": "error", "message": str(e) or repr(e), "error_type": type(e).__name__}
    finally:
        if ib.isConnected():
            ib.disconnect()


def _percentile_rank(series: pd.Series, value: float) -> float:
    """Rang percentile de value dans series (0-100)."""
    return float((series < value).sum() / len(series) * 100)


@mcp.tool
def get_regime_dashboard() -> dict:
    """Tableau de regime spread GC/SI base sur V30, HV30, VRP et ratio IV.

    Lit les Parquet locaux (backfill_iv_history doit avoir ete lance au prealable).
    Retourne metriques courantes, percentiles historiques et signaux de regime.
    """
    gc_path = VOL_METRICS_DIR / "iv_history_GC.parquet"
    si_path = VOL_METRICS_DIR / "iv_history_SI.parquet"

    if not gc_path.exists() or not si_path.exists():
        return {
            "status": "error",
            "message": "Parquet manquant. Lancer backfill_iv_history d'abord.",
        }

    try:
        df_gc = pd.read_parquet(gc_path)
        df_si = pd.read_parquet(si_path)

        # Merge sur date
        df = df_gc[["date", "v30", "hv30", "vrp"]].merge(
            df_si[["date", "v30", "hv30", "vrp"]],
            on="date", suffixes=("_gc", "_si"),
        ).sort_values("date").reset_index(drop=True)

        if len(df) < 60:
            return {"status": "error", "message": f"Pas assez de donnees ({len(df)} bars, min 60)"}

        # Ratio IV = V30(GC) / V30(SI)
        df["ratio_iv"] = df["v30_gc"] / df["v30_si"]

        # Valeurs courantes (derniere ligne)
        last = df.iloc[-1]
        ratio_now = float(last["ratio_iv"])

        # Deltas jour/jour et semaine/semaine
        ratio_series = df["ratio_iv"]
        deltas = {}
        for offset, label in [(1, "1d"), (5, "5d"), (20, "20d")]:
            if len(ratio_series) > offset:
                prev = float(ratio_series.iloc[-(offset + 1)])
                deltas[label] = {
                    "abs": round(ratio_now - prev, 4),
                    "pct": round((ratio_now - prev) / prev * 100, 1) if prev != 0 else None,
                }
            else:
                deltas[label] = None

        # Percentiles du ratio IV sur differentes fenetres
        percentiles = {}
        for window, label in [(5, "5d"), (20, "20d"), (60, "60d")]:
            window_data = ratio_series.iloc[-window:]
            percentiles[label] = {
                "percentile": round(_percentile_rank(window_data, ratio_now), 1),
                "mean": round(float(window_data.mean()), 4),
                "std": round(float(window_data.std()), 4),
                "min": round(float(window_data.min()), 4),
                "max": round(float(window_data.max()), 4),
                "zscore": round(
                    (ratio_now - float(window_data.mean())) / float(window_data.std())
                    if window_data.std() > 0 else 0.0, 2
                ),
            }

        # Signaux de regime
        signals = []
        zscore_60d = percentiles["60d"]["zscore"]

        # 1. Ratio IV : RED >2 sigma, ORANGE >1.5 sigma
        if abs(zscore_60d) > 2.0:
            signals.append({
                "signal": "RATIO_IV_EXTREME",
                "severity": "RED",
                "detail": f"Ratio IV z-score={zscore_60d} vs 60d",
            })
        elif abs(zscore_60d) > 1.5:
            signals.append({
                "signal": "RATIO_IV_ELEVATED",
                "severity": "ORANGE",
                "detail": f"Ratio IV z-score={zscore_60d} vs 60d",
            })

        # 2. VRP : RED >2 sigma, ORANGE >1.5 sigma (les deux symboles)
        vrp_gc_60 = df["vrp_gc"].iloc[-60:]
        vrp_si_60 = df["vrp_si"].iloc[-60:]
        vrp_gc_now = float(last["vrp_gc"])
        vrp_si_now = float(last["vrp_si"])

        vrp_zscores = {}
        for sym, vrp_series, vrp_now in [("GC", vrp_gc_60, vrp_gc_now), ("SI", vrp_si_60, vrp_si_now)]:
            vrp_z = (vrp_now - float(vrp_series.mean())) / float(vrp_series.std()) if vrp_series.std() > 0 else 0.0
            vrp_zscores[sym] = round(vrp_z, 2)
            if abs(vrp_z) > 2.0:
                signals.append({
                    "signal": f"VRP_SPIKE_{sym}",
                    "severity": "RED",
                    "detail": f"VRP({sym}) z-score={round(vrp_z, 2)} vs 60d",
                })
            elif abs(vrp_z) > 1.5:
                signals.append({
                    "signal": f"VRP_ELEVATED_{sym}",
                    "severity": "ORANGE",
                    "detail": f"VRP({sym}) z-score={round(vrp_z, 2)} vs 60d",
                })

        # 3. Environnement favorable (ratio stable, pas de spike)
        if abs(zscore_60d) < 1.0 and not any(s["signal"].startswith("VRP_SPIKE") for s in signals):
            signals.append({
                "signal": "FAVORABLE",
                "severity": "GREEN",
                "detail": f"Ratio IV stable (z={zscore_60d}), pas de VRP spike",
            })

        # Si aucun signal
        if not signals:
            signals.append({
                "signal": "NEUTRAL",
                "severity": "YELLOW",
                "detail": "Aucun signal extreme detecte",
            })

        return {
            "status": "ok",
            "date": str(last["date"].date()) if hasattr(last["date"], "date") else str(last["date"]),
            "data_bars": len(df),
            "data_quality": "filtered_contfuture",
            "GC": {
                "v30": round(float(last["v30_gc"]) * 100, 2),
                "hv30": round(float(last["hv30_gc"]) * 100, 2),
                "vrp": round(float(last["vrp_gc"]) * 100, 2),
                "vrp_zscore_60d": vrp_zscores.get("GC", 0.0),
            },
            "SI": {
                "v30": round(float(last["v30_si"]) * 100, 2),
                "hv30": round(float(last["hv30_si"]) * 100, 2),
                "vrp": round(float(last["vrp_si"]) * 100, 2),
                "vrp_zscore_60d": vrp_zscores.get("SI", 0.0),
            },
            "ratio_iv": round(ratio_now, 4),
            "ratio_iv_deltas": deltas,
            "percentiles": percentiles,
            "signals": signals,
        }

    except Exception as e:
        return {"status": "error", "message": str(e) or repr(e), "error_type": type(e).__name__}


if __name__ == "__main__":
    mcp.run()
