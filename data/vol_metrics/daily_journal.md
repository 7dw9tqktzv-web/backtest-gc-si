# Journal Vol Quotidien GC/SI

Ce fichier est consulte par Claude Code avant chaque analyse vol pour garder le contexte historique.
Mis a jour a chaque `collect_daily_snapshot`.

---

## 2026-02-27 (jeudi) — 09:07 CT [BACKFILL REFRESH]
GC $5,243 | IV=30.5% V30=29.1% HV=38.4% VRP=-9.3 (z=-0.76 GREEN) | RR25=+1.51 (HIGH)
SI $92.78  | IV=79.4% V30=75.0% HV=105.5% VRP=-30.6 (z=-1.16 YELLOW) | RR25=+7.22 (HIGH)
Ratio IV=0.387 (P20/5j, P70/20j, P55/60j, z=0.16) | Skew ALIGNED (conf HIGH) | DTE=27j (exp 26 mars)
- GC +$61 vs 26 fev (+1.2%), SI +$5.53 (+6.3%) — rebond apres pullback, Silver surperforme
- **BACKFILL CHANGE** : V30 mis a jour au 26 fev (GC 30.8->29.1%, SI 88.2->75.0%)
- V30 SI chute de -13.2pts en 1j — normalisation apres le pic du rally
- VRP SI passe de GREEN (z=-0.71) a **YELLOW (z=-1.16)** — HV(105%) >> V30(75%), ecart de 30pts
- VRP GC se deteriore legerement : z=-0.21->z=-0.76 mais reste GREEN
- Ratio IV remonte : 0.349->0.387 (V30 SI a chute plus que V30 GC)
- RR25 GC remonte : 0.59->1.51 (+0.92pt) — biais call revient au niveau du 25 fev
- RR25 SI bondit : 4.66->7.22/8.53 (+2.6/3.9pts) — biais call tres agressif, proche du pic
- IV ATM vs V30 : GC IV(30.5%) > V30(29.1%), SI IV(79.4%) > V30(75.0%) — IV ATM au-dessus du V30
- Skew detail : GC call 5590 IV=31.92% vs put 4990 IV=30.41% (diff=+1.51)
- Skew detail : SI call 111.50 IV=86.10% vs put 82.45 IV=78.89% (diff=+7.22)
- GC RR10=+2.77% (call 5950/34.95% vs put 4715/32.18%) — biais call persiste en ailes
- **4/5 signaux GREEN, VRP SI YELLOW** — conditions favorables avec bemol Silver

## 2026-02-26 (mercredi) — 09:12 CT [BACKFILL REFRESH]
GC $5,182 | IV=28.8% V30=30.8% HV=39.0% VRP=-8.2 (z=-0.21 GREEN) | RR25=+0.59 (HIGH)
SI $87.25  | IV=74.0% V30=88.2% HV=109.5% VRP=-21.4 (z=-0.71 GREEN) | RR25=+4.66 (HIGH)
Ratio IV=0.349 (P0/5j, P70/20j, P55/60j, z=0.17) | Skew ALIGNED (conf HIGH) | DTE=28j (exp 26 mars)
- GC -$9 vs 25 fev (-0.2%), SI -$3.51 (-3.9%) — pullback apres le rally
- **BACKFILL CHANGE** : V30 mis a jour (GC 28.3->30.8%, SI 62.8->88.2%) — les anciens VRP etaient faux
- VRP GC passe de YELLOW (z=-1.14) a GREEN (z=-0.21) — normalise
- VRP SI passe de RED (z=-2.42) a GREEN (z=-0.71) — l'IV a rattrape la HV
- Ratio IV chute de 0.451 a 0.349 — le V30 SI a bondi (+40%), Gold stable
- IV ATM vs V30 : GC IV_ATM(28.8%) < V30(30.8%), SI IV_ATM(74.0%) < V30(88.2%)
- RR25 GC degonfle : 1.51->0.59 (-0.92pt), RR25 SI : 8.29->4.66 (-3.63pts)
- Skew detail : GC call 5495 IV=29.82% vs put 4920 IV=29.26% (diff=+0.56)
- Skew detail : SI call 103.10 IV=79.09% vs put 77.20 IV=73.75% (diff=+5.34)
- **TOUS SIGNAUX GREEN** — premiere fois depuis debut des collectes
- Environnement FAVORABLE pour mean reversion selon le dashboard

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

## Tendances observees (6 snapshots, 18-27 fev)
- **Prix** : GC $5,023->$5,191->$5,182->$5,243 (+4.4%), SI $78.11->$90.76->$87.25->$92.78 (+18.8%) — rally Silver reprend apres pullback 1j
- **IV ATM** : GC 28.3->31.9->28.8->30.5 (+2.2pt net), SI 68.1->82.4->74.0->79.4 (+11.3pt net) — rebond IV avec prix
- **V30** : GC 30.8->29.1% (-1.7pt), SI 88.2->75.0% (-13.2pt) — forte correction V30 SI (backfill 26 fev)
- **RR25 GC** : 0.42 -> 0.90 -> 1.38 -> 1.51 -> 0.59 -> 1.51 — forme en V, retour au pic
- **RR25 SI** : 3.88 -> 3.93 -> 5.08 -> 8.29 -> 4.66 -> 7.22 — rebond agressif, proche du pic
- **Skew** : toujours ALIGNED — jamais de divergence GC/SI sur 6 snapshots
- **VRP** : GC GREEN (z=-0.76), SI **YELLOW** (z=-1.16) — HV Silver toujours >> V30, ecart 30pts
- **Ratio IV** : 0.387 (P20/5j, P70/20j), stable sur 1j (+0.4%), hausse sur 20j (+29.6%)
- **Pattern** : rally 7j (18-25), pullback 1j (26), rebond (27) — Silver mene les oscillations
- **26 fev tous GREEN, 27 fev VRP SI passe YELLOW** — le backfill revele la realite V30 SI
