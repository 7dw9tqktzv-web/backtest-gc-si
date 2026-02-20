# Journal Vol Quotidien GC/SI

Ce fichier est consulte par Claude Code avant chaque analyse vol pour garder le contexte historique.
Mis a jour a chaque `collect_daily_snapshot`.

---

## 2026-02-20 (jeudi) — 08:33 CT
GC $5,071 | IV=29.7% HV=41.0% VRP=-12.7 (z=-1.14 YELLOW) | RR25=+1.38 (HIGH)
SI $81.54  | IV=71.4% HV=112.7% VRP=-49.9 (z=-2.42 RED)   | RR25=+5.08 (HIGH)
Ratio IV=0.451 (P95/20j, P85/60j) | Skew ALIGNED | DTE=34j (exp 26 mars)
- GC +$47 vs veille, SI +$2.93 — rally metaux continue
- VRP SI en zone rouge extreme (z=-2.42) : HV double l'IV, mouvements realises >>> anticipes
- VRP GC en jaune, meme dynamique moins prononcee
- Ratio IV en forte hausse (+53% sur 20j) = IV Gold monte vs Silver, convergence inhabituelle
- RR25 en hausse (GC 0.42->0.90->1.38, SI 3.88->3.93->5.08) = biais call qui se renforce
- Conditions mitigees pour mean reversion : regime OK mais VRP Silver warning

## 2026-02-19 (mercredi) — 08:57 CT
GC $5,028 | IV=29.4% HV=n/a VRP=n/a | RR25=+0.90 (HIGH)
SI $78.61  | IV=69.4% HV=n/a VRP=n/a | RR25=+3.93 (HIGH)
Ratio IV=n/a (V30 non collecte ce jour) | Skew ALIGNED | DTE=35j
- GC +$5 vs veille, SI +$0.50 — quasi flat
- V30/HV30 non disponibles (backfill pas encore lance ce jour-la)
- RR25 GC en hausse (0.42->0.90) = biais call qui se construit
- RR25 SI stable (~3.93)

## 2026-02-18 (mardi) — 09:18 CT — Premiere collecte
GC $5,023 | IV=28.3% HV=n/a VRP=n/a | RR25=+0.42 (HIGH)
SI $78.11  | IV=68.1% HV=n/a VRP=n/a | RR25=+3.88 (HIGH)
Ratio IV=0.440 | Skew ALIGNED | DTE=36j (exp 26 mars)
- Premiere collecte MCP operationnelle
- RR25 GC quasi neutre (+0.42), SI moderement call (+3.88)
- V30 GC=26.1%, SI=59.4% (depuis backfill historique)

---

## Tendances observees (3 jours)
- **Prix** : GC +$47 (+0.9%), SI +$3.43 (+4.4%) — Silver surperforme
- **IV ATM** : GC 28.3->29.7 (+1.4pt), SI 68.1->71.4 (+3.3pt) — IV monte avec les prix
- **RR25 GC** : 0.42 -> 0.90 -> 1.38 — biais call en acceleration
- **RR25 SI** : 3.88 -> 3.93 -> 5.08 — saut jour 3
- **Skew** : toujours ALIGNED — pas de divergence GC/SI
- **VRP** : seul jour 3 a les donnees. VRP SI extreme (RED), GC en YELLOW
