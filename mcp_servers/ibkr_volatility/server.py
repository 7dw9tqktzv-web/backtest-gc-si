"""
MCP Server : IBKR Implied Volatility pour GC/SI
Connexion TWS via ib_insync, port 7497 (TWS live/paper).

Usage : configure dans .mcp.json
"""

import nest_asyncio
nest_asyncio.apply()

from datetime import datetime
from pathlib import Path

import pandas as pd
from fastmcp import FastMCP
from ib_insync import IB, ContFuture, Future, Option

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
        server_time = str(ib.reqCurrentTime())
        result = {
            "status": "connected",
            "account": account,
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
    for exp_str in expirations:
        exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
        dte = (exp_date - today).days
        if dte < 1:
            continue
        diff = abs(dte - target_dte)
        if diff < best_diff:
            best_diff = diff
            best = exp_str
    return best


def _resolve_option_chain(ib: IB, symbol: str, exchange: str, opt_exchange: str,
                          target_dte: int = 30) -> dict:
    """Trouve le future, son prix, et la chaine d'options la plus proche de target_dte.

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
    for cd in sorted_contracts:
        candidate = cd.contract
        ib.qualifyContracts(candidate)
        chains = ib.reqSecDefOptParams(candidate.symbol, candidate.exchange,
                                       candidate.secType, candidate.conId)
        if chains:
            fut_contract = candidate
            break

    if fut_contract is None:
        return {"error": f"Aucun future avec options trouve pour {symbol}"}

    [ticker] = ib.reqTickers(fut_contract)
    fut_price = ticker.marketPrice()
    if fut_price != fut_price:
        fut_price = ticker.close
    if fut_price != fut_price:
        return {"error": f"Pas de prix pour {symbol}", "contract": fut_contract.localSymbol}

    chain = None
    for c in chains:
        if c.exchange == opt_exchange:
            chain = c
            break
    if chain is None:
        chain = chains[0]

    expiry = _find_nearest_expiry(list(chain.expirations), target_dte)
    if expiry is None:
        return {"error": "Aucune expiration valide trouvee", "expirations": list(chain.expirations)}

    dte = (datetime.strptime(expiry, "%Y%m%d").date() - datetime.now().date()).days
    strikes = sorted(chain.strikes)
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
    }


def _get_atm_iv(ib: IB, symbol: str, exchange: str, opt_exchange: str,
                opt_symbol: str, target_dte: int = 30) -> dict:
    """Recupere l'IV ATM pour un future : prix future, strike ATM, IV call+put."""
    info = _resolve_option_chain(ib, symbol, exchange, opt_exchange, target_dte)
    if "error" in info:
        return info

    fut_price = info["fut_price"]
    expiry = info["expiry"]
    dte = info["dte"]
    atm_strike = info["atm_strike"]

    call = Option(symbol=opt_symbol, lastTradeDateOrContractMonth=expiry,
                  strike=atm_strike, right="C", exchange=opt_exchange)
    put = Option(symbol=opt_symbol, lastTradeDateOrContractMonth=expiry,
                 strike=atm_strike, right="P", exchange=opt_exchange)
    qualified = ib.qualifyContracts(call, put)

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
        greeks = t.modelGreeks
        if greeks and greeks.impliedVol is not None and greeks.delta is not None:
            result[f"iv_{right}"] = round(float(greeks.impliedVol) * 100, 2)
            result[f"delta_{right}"] = round(float(greeks.delta), 4)
        else:
            result[f"iv_{right}"] = None
            result[f"delta_{right}"] = None

    return result


def _get_risk_reversal(ib: IB, symbol: str, exchange: str, opt_exchange: str,
                       opt_symbol: str, target_dte: int = 30) -> dict:
    """Calcule RR25 et RR10 pour un symbole via IV par delta."""
    info = _resolve_option_chain(ib, symbol, exchange, opt_exchange, target_dte)
    if "error" in info:
        return info

    fut_price = info["fut_price"]
    expiry = info["expiry"]
    dte = info["dte"]
    strikes = info["strikes"]
    atm_strike = info["atm_strike"]

    # Filtrer strikes dans +-20% autour du prix ATM
    lo = fut_price * 0.80
    hi = fut_price * 1.20
    nearby_strikes = [s for s in strikes if lo <= s <= hi]

    if not nearby_strikes:
        return {"error": f"Aucun strike dans +-20% de {fut_price}", "symbol": symbol}

    # Qualifier calls et puts en batch
    options = []
    for s in nearby_strikes:
        options.append(Option(symbol=opt_symbol, lastTradeDateOrContractMonth=expiry,
                              strike=s, right="C", exchange=opt_exchange))
        options.append(Option(symbol=opt_symbol, lastTradeDateOrContractMonth=expiry,
                              strike=s, right="P", exchange=opt_exchange))

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

    # Construire la table strike/right/delta/iv
    rows = []
    for t in tickers:
        g = t.modelGreeks
        if g and g.delta is not None and g.impliedVol is not None:
            rows.append({
                "strike": t.contract.strike,
                "right": t.contract.right,
                "delta": float(g.delta),
                "iv": float(g.impliedVol) * 100,
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

        if (best_call and best_put
                and abs(best_call["delta"] - target_delta) <= DELTA_TOLERANCE
                and abs(abs(best_put["delta"]) - target_delta) <= DELTA_TOLERANCE):
            rr_val = round(best_call["iv"] - best_put["iv"], 2)
            result[label] = rr_val
            result[f"{label}_call"] = {
                "strike": best_call["strike"],
                "delta": round(best_call["delta"], 4),
                "iv": round(best_call["iv"], 2),
            }
            result[f"{label}_put"] = {
                "strike": best_put["strike"],
                "delta": round(best_put["delta"], 4),
                "iv": round(best_put["iv"], 2),
            }
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
                                   opt_exchange="COMEX", opt_symbol="OG", target_dte=target_dte)
        si_rr = _get_risk_reversal(ib, symbol="SI", exchange="COMEX",
                                   opt_exchange="COMEX", opt_symbol="SO", target_dte=target_dte)

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
            d.get(f"iv_{r}") is not None
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
    df = df[(df["v30"] >= 0.05) & (df["v30"] <= 1.0)].reset_index(drop=True)
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
