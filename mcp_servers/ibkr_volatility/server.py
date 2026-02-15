"""
MCP Server : IBKR Implied Volatility pour GC/SI
Connexion TWS via ib_insync, port 7497 (TWS live/paper).

Usage : configure dans .mcp.json
"""

import nest_asyncio
nest_asyncio.apply()

from datetime import datetime
from fastmcp import FastMCP
from ib_insync import IB, Future, Option

mcp = FastMCP("IBKR Volatility")

TWS_HOST = "127.0.0.1"
TWS_PORT = 7497
CLIENT_ID = 50  # ID dedie MCP, evite conflit avec autres clients


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


def _get_atm_iv(ib: IB, symbol: str, exchange: str, opt_exchange: str,
                opt_symbol: str, target_dte: int = 30) -> dict:
    """Recupere l'IV ATM pour un future : prix future, strike ATM, IV call+put."""
    # 1. Trouver le premier future qui a une chaine d'options
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

    # 2. Prix du future
    [ticker] = ib.reqTickers(fut_contract)
    fut_price = ticker.marketPrice()
    if fut_price != fut_price:  # NaN check
        fut_price = ticker.close
    if fut_price != fut_price:
        return {"error": f"Pas de prix pour {symbol}", "contract": fut_contract.localSymbol}

    # Trouver la chaine sur le bon exchange
    chain = None
    for c in chains:
        if c.exchange == opt_exchange:
            chain = c
            break
    if chain is None:
        chain = chains[0]  # fallback

    # 4. Expiration la plus proche de target_dte
    expiry = _find_nearest_expiry(list(chain.expirations), target_dte)
    if expiry is None:
        return {"error": "Aucune expiration valide trouvee", "expirations": list(chain.expirations)}

    dte = (datetime.strptime(expiry, "%Y%m%d").date() - datetime.now().date()).days

    # 5. Strike ATM (le plus proche du prix future)
    strikes = sorted(chain.strikes)
    atm_strike = min(strikes, key=lambda s: abs(s - fut_price))

    # 6. Qualifier call et put ATM
    call = Option(symbol=opt_symbol, lastTradeDateOrContractMonth=expiry,
                  strike=atm_strike, right="C", exchange=opt_exchange)
    put = Option(symbol=opt_symbol, lastTradeDateOrContractMonth=expiry,
                 strike=atm_strike, right="P", exchange=opt_exchange)
    qualified = ib.qualifyContracts(call, put)

    # 7. Recuperer les tickers (IV via model greeks, mis a jour in-place)
    tickers = ib.reqTickers(*qualified)
    for _ in range(5):
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

        return {
            "status": "ok",
            "market_open": has_iv,
            "server_time": str(ib.reqCurrentTime()),
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


if __name__ == "__main__":
    mcp.run()
