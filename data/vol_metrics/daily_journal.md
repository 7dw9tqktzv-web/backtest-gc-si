# Journal Vol Quotidien GC/SI

Ce fichier est consulte par Claude Code avant chaque analyse vol pour garder le contexte historique.
Mis a jour a chaque `collect_daily_snapshot`.

---

## 2026-02-25 (mercredi) — 05:48 CT
GC $5,191 | IV=31.9% HV=41.0% VRP=-12.7 (z=-1.14 YELLOW) | RR25=+1.51 (HIGH)
SI $90.76  | IV=82.4% HV=112.7% VRP=-49.9 (z=-2.42 RED)   | RR25=+8.29 (HIGH)
Ratio IV=0.451 (P95/20j, P85/60j, z=0.93) | Skew ALIGNED | DTE=29j (exp 26 mars)
- GC +$120 vs 20 fev (+2.4%), SI +$9.22 (+11.3%) — Silver surperforme massivement
- IV Silver bondit de 11pts (71.4->82.4%), IV Gold +2.2pts (29.7->31.9%)
- RR25 SI accelere : 5.08->8.29 (+3.21pts) = biais call tres agressif
- RR25 GC stable : 1.38->1.51 (+0.13pt)
- VRP SI toujours RED extreme (z=-2.42), HV30 quasi double de V30
- VRP GC stable en YELLOW (z=-1.14)
- Ratio IV au P95/20j = convergence IV Gold/Silver inhabituelle
- V30 stale (18 fev) — backfill recommande
- Conditions mitigees : regime GREEN mais VRP Silver en zone de danger

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

## Tendances observees (4 snapshots, 18-25 fev)
- **Prix** : GC $5,023->$5,191 (+3.3%), SI $78.11->$90.76 (+16.2%) — Silver rally massif
- **IV ATM** : GC 28.3->31.9 (+3.6pt), SI 68.1->82.4 (+14.3pt) — IV Silver explose avec le prix
- **RR25 GC** : 0.42 -> 0.90 -> 1.38 -> 1.51 — biais call en construction progressive
- **RR25 SI** : 3.88 -> 3.93 -> 5.08 -> 8.29 — acceleration forte, biais call agressif
- **Skew** : toujours ALIGNED — pas de divergence GC/SI
- **VRP** : VRP SI en RED persistant (z=-2.42), GC YELLOW stable (z=-1.14)
- **Ratio IV** : stable a 0.451, P95 sur 20j — convergence IV inhabituelle
