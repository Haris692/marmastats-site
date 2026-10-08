import sqlite3, json, os, sys, math, argparse, subprocess, datetime, statistics
from collections import Counter, defaultdict
import libelles
import radar
import ligue
import retenir
import catapult
RACINE = os.path.dirname(os.path.abspath(__file__))
WEB = RACINE
DATA = os.path.join(WEB, 'data')
BASE = os.path.join(RACINE, 'base.db')
NOTRE_EQUIPE = '{NOUS}'
TIERS = 70
W_TERRAIN = 68.0

def r2(v):
    return None if v is None else round(float(v), 1)

def possessions(actions_equipe, nous):
    par_instant = defaultdict(set)
    for a in actions_equipe:
        par_instant[a['mi_temps'], a['t_s']].add(a['equipe'])
    poss, cur = ([], None)
    for h, t in sorted(par_instant):
        eqs = par_instant[h, t]
        etat = 'nous' if eqs == {nous} else 'duel' if nous in eqs else 'eux'
        if etat == 'duel' and cur and (cur[0] == 'nous'):
            etat = 'nous'
        if not cur or cur[0] != etat or cur[1] != h:
            cur = [etat, h, t, t]
            poss.append(cur)
        else:
            cur[3] = t
    return [p for p in poss if p[0] == 'nous']

def reseau(actions_joueur, seqs):
    liens, liens_prog, chrono = (Counter(), Counter(), [])
    par_mt = defaultdict(list)
    for a in actions_joueur:
        par_mt[a['mi_temps']].append(a)
    for k in par_mt:
        par_mt[k].sort(key=lambda a: a['t_s'])
    for _, h, t0, t1 in seqs:
        L = [a for a in par_mt.get(h, []) if t0 <= a['t_s'] <= t1]
        for i, a in enumerate(L):
            if not (a['est_passe'] and a['reussie']):
                continue
            for b in L[i + 1:]:
                if b['numero'] == a['numero']:
                    continue
                if b['t_s'] - a['t_s'] > 8:
                    break
                liens[a['numero'], b['numero']] += 1
                chrono.append((h, a['t_s'], a['numero'], b['numero']))
                if a['progressive']:
                    liens_prog[a['numero'], b['numero']] += 1
                break
    return (liens, liens_prog, chrono)

def film(eq, jo, chrono, nous):
    t0, fin = ({}, {})
    for a in eq:
        h = a['mi_temps']
        t0[h] = min(t0.get(h, a['t_s']), a['t_s'])
        fin[h] = max(fin.get(h, a['t_s']), a['t_s'])
    if 1 not in t0 or 2 not in t0:
        return None
    mt1 = (fin[1] - t0[1]) / 60.0

    def m(h, t):
        return round((t - t0[h]) / 60.0 + (mt1 if h == 2 else 0), 2)
    vus = set()
    buts = []
    for a in eq:
        cle = (a['mi_temps'], a['t_s'], a['equipe'])
        if a['but'] and cle not in vus:
            vus.add(cle)
            buts.append([m(a['mi_temps'], a['t_s']), 1 if a['equipe'] == nous else 0])
    momentum = []
    for h in (1, 2):
        dur = (fin[h] - t0[h]) / 60.0
        bornes = [b for b in range(0, int(dur // 5) * 5 + 5, 5) if b < dur]
        if len(bornes) > 1 and dur - bornes[-1] < 2:
            bornes.pop()
        base = mt1 if h == 2 else 0
        tr = [dict(m0=round(base + b, 2), m1=round(base + (bornes[i + 1] if i + 1 < len(bornes) else dur), 2), nous=0, eux=0, tn=0, te=0) for i, b in enumerate(bornes)]
        for a in eq:
            if a['mi_temps'] != h or a['x'] is None:
                continue
            b_ = tr[min(int((a['t_s'] - t0[h]) / 60.0 // 5), len(tr) - 1)]
            cote = 'nous' if a['equipe'] == nous else 'eux'
            if a['x'] >= TIERS:
                b_[cote] += 1
            if a['tir']:
                b_['tn' if cote == 'nous' else 'te'] += 1
        momentum += tr
    inv, noms = (Counter(), {})
    for a in jo:
        if a['numero'] is not None and a['est_passe']:
            inv[a['numero']] += 1
            noms[a['numero']] = a['joueur']
    for _, _, _, nb in chrono:
        inv[nb] += 1
    tot = sum(inv.values()) or 1
    implication = [[n, str(noms.get(n, n)).split(' ')[-1], round(100 * c / tot)] for n, c in inv.most_common(5)]
    return dict(momentum=momentum, implication=implication, mt1=round(mt1, 2), fin=m(2, fin[2]), touches=[[m(a['mi_temps'], a['t_s']), a['numero'], r2(a['x']), r2(a['y'])] for a in jo if a['numero'] is not None and a['x'] is not None], passes=[[m(h, t), na, nb] for h, t, na, nb in chrono], buts=sorted(buts))

def charge(cx, match_id):
    cols = 'action_id, mi_temps, t_s, equipe, joueur_id, numero, joueur, x, y, est_passe, reussie, vers_avant, progressive, passe_cle, longue, centre, tir, cadre, but, poteau, contre, dribble, duel, duel_gagne, recuperation, perte'

    def lire(niveau):
        cur = cx.execute('SELECT %s FROM v_action WHERE match_id=? AND niveau=? ORDER BY mi_temps, t_s' % cols, (match_id, niveau))
        noms = [d[0] for d in cur.description]
        return [dict(zip(noms, r)) for r in cur.fetchall()]
    return (lire('equipe'), lire('joueur'))

def tags_equipe(cx, match_id):
    d = defaultdict(dict)
    for eq, tag, n in cx.execute("SELECT a.equipe, t.tag, COUNT(*) FROM action a JOIN action_tag t USING(action_id) WHERE a.match_id=? AND a.niveau='equipe' GROUP BY a.equipe, t.tag", (match_id,)):
        d[eq][tag] = n
    return d

def tags_joueur(cx, match_id):
    d = defaultdict(dict)
    for num, tag, n in cx.execute("SELECT a.numero, t.tag, COUNT(*) FROM action a JOIN action_tag t USING(action_id) WHERE a.match_id=? AND a.niveau='joueur' AND a.numero IS NOT NULL GROUP BY a.numero, t.tag", (match_id,)):
        d[num][tag] = n
    return d

def issue_tir(a):
    if a['but']:
        return 'but'
    if a['cadre']:
        return 'cadre'
    if a['poteau']:
        return 'poteau'
    if a['contre']:
        return 'contre'
    return 'hors'

def stats_bloc(actions, e):
    d = [a for a in actions if a['equipe'] == e]
    p = [a for a in d if a['est_passe']]
    pr = [a for a in p if a['progressive']]
    t3 = [a for a in d if a['x'] is not None and a['x'] >= TIERS]
    t3p = [a for a in t3 if a['est_passe']]
    som = lambda k, src=d: int(sum((1 for a in src if a[k])))
    return dict(passes=len(p), passes_ok=sum((1 for a in p if a['reussie'])), avant=sum((1 for a in p if a['vers_avant'])), prog=len(pr), prog_ok=sum((1 for a in pr if a['reussie'])), prog_depart=r2(sorted((a['x'] for a in pr if a['x'] is not None))[len(pr) // 2]) if pr else None, tirs=som('tir'), buts=som('but'), passes_cles=som('passe_cle'), centres=som('centre'), dribbles=som('dribble'), duels=som('duel'), duels_ok=som('duel_gagne'), recup=som('recuperation'), pertes=som('perte'), t3_actions=len(t3), t3_passes=len(t3p), t3_ok=sum((1 for a in t3p if a['reussie'])), t3_tirs=sum((1 for a in t3 if a['tir'])))
LONGUEUR = {'Coups de pied de but courts (0-10 m.)': 'c', 'Coups de pied de but moyens (15-40 m.)': 'm', 'Coups de pied de but longs (40+ m.)': 'l'}
VOL = 15.0
LIEN_MAX = 8
FUSION = ('est_passe', 'reussie', 'vers_avant', 'progressive', 'tir', 'but', 'cadre', 'poteau', 'contre')

def secteur(dx, dy):
    return int((math.degrees(math.atan2(dy, dx)) + 22.5) % 360 // 45)

def douteux_de(cx, match_id):
    q = ','.join('?' * len(catapult.RETOURNEES))
    return {r[0] for r in cx.execute('SELECT DISTINCT a.action_id FROM action a JOIN action_tag t USING(action_id) WHERE a.match_id=? AND t.tag IN (%s)' % q, (match_id,) + tuple(catapult.RETOURNEES))}

def longueurs(cx, match_id):
    q = ','.join('?' * len(LONGUEUR))
    return {(h, t, e): LONGUEUR[tag] for h, t, e, tag in cx.execute("SELECT a.mi_temps, a.t_s, a.equipe, t.tag FROM action a JOIN action_tag t USING(action_id) WHERE a.match_id=? AND a.niveau='equipe' AND t.tag IN (%s)" % q, (match_id,) + tuple(LONGUEUR))}

def instants(eq, e, douteux):
    out = {}
    for a in eq:
        if a['equipe'] != e:
            continue
        k = (a['mi_temps'], a['t_s'])
        o = out.get(k)
        if o is None:
            o = out[k] = dict(a, dout=False)
        else:
            for f in FUSION:
                o[f] = o[f] or a[f]
            if o['x'] is None:
                o['x'], o['y'] = (a['x'], a['y'])
        if a['action_id'] in douteux:
            o['dout'] = True
    return sorted(out.values(), key=lambda a: (a['mi_temps'], a['t_s']))

def par_possession(I, seqs):
    par_mt = defaultdict(list)
    for a in I:
        par_mt[a['mi_temps']].append(a)
    for _, h, t0, t1 in seqs:
        yield [a for a in par_mt.get(h, []) if t0 <= a['t_s'] <= t1]

def sure(a):
    return a['x'] is not None and (not a['dout'])

def profil_passes(I, seqs, lg, e):
    rose, gain, placees = ([0] * 8, 0.0, 0)
    for L in par_possession(I, seqs):
        for a, b in zip(L, L[1:]):
            if not (a['est_passe'] and a['reussie'] and sure(a) and sure(b)) or b['t_s'] - a['t_s'] > LIEN_MAX:
                continue
            dx, dy = (b['x'] - a['x'], b['y'] - a['y'])
            if math.hypot(dx, dy) < 1:
                continue
            rose[secteur(dx, dy)] += 1
            gain += max(0.0, dx)
            placees += 1
    lgs = {k: [0, 0] for k in 'cml'}
    for a in I:
        k = lg.get((a['mi_temps'], a['t_s'], e))
        if a['est_passe'] and k:
            lgs[k][1] += 1
            lgs[k][0] += int(bool(a['reussie']))
    return dict(rose=rose, gain=int(round(gain)), placees=placees, lg=lgs)

def liens_joueurs(jo, seqs):
    par_mt = defaultdict(list)
    for a in jo:
        par_mt[a['mi_temps']].append(a)
    for k in par_mt:
        par_mt[k].sort(key=lambda a: a['t_s'])
    for _, h, t0, t1 in seqs:
        L = [a for a in par_mt.get(h, []) if t0 <= a['t_s'] <= t1]
        for i, a in enumerate(L):
            if not (a['est_passe'] and a['reussie']) or a['numero'] is None:
                continue
            for b in L[i + 1:]:
                if b['numero'] == a['numero']:
                    continue
                if b['t_s'] - a['t_s'] > LIEN_MAX:
                    break
                yield (a, b)
                break

def reception(tr, a, b, depart, douteux):
    h, t = (a['mi_temps'], a['t_s'])
    p0 = catapult.position(tr, h, b['numero'], t)
    if p0 is not None:
        vol = min(math.hypot(p0[0] - depart[0], p0[1] - depart[1]) / VOL, 3.0)
        return (catapult.position(tr, h, b['numero'], t + vol) or p0, 'g')
    if b['x'] is not None and b['action_id'] not in douteux:
        return ((b['x'], b['y']), 'i')
    return (None, '')

def roses_joueurs(jo, seqs, tr, douteux):
    out = {}
    for a, b in liens_joueurs(jo, seqs):
        pa = catapult.position(tr, a['mi_temps'], a['numero'], a['t_s'])
        if pa is None:
            if a['x'] is None or a['action_id'] in douteux:
                continue
            pa = (a['x'], a['y'])
        pb, m = reception(tr, a, b, pa, douteux)
        if pb is None:
            continue
        dx, dy = (pb[0] - pa[0], pb[1] - pa[1])
        if math.hypot(dx, dy) < 1:
            continue
        o = out.setdefault(str(a['numero']), dict(rose=[0] * 8, gps=0))
        o['rose'][secteur(dx, dy)] += 1
        o['gps'] += int(m == 'g')
    return out

def zone(x, y):
    ti = 0 if x < 35 else 1 if x < TIERS else 2
    co = 0 if y >= 2 * W_TERRAIN / 3 else 1 if y >= W_TERRAIN / 3 else 2
    return 3 * ti + co

def dans_surface(a):
    return a['x'] >= 105 - 16.5 and 13.84 <= a['y'] <= W_TERRAIN - 13.84

def circuits(I, seqs, garder=4):
    grp, n_t3 = (defaultdict(list), 0)
    for L in par_possession(I, seqs):
        L = [a for a in L if sure(a)]
        if len(L) < 2 or L[-1]['x'] < TIERS:
            continue
        n_t3 += 1
        grp[zone(L[0]['x'], L[0]['y']), zone(L[-1]['x'], L[-1]['y'])].append(L)
    routes = []
    for (z0, z1), P in grp.items():
        if len(P) < 2:
            continue
        med = [statistics.median((L[i][k] for L in P)) for i in (0, -1) for k in ('x', 'y')]
        n_med = statistics.median((len(L) for L in P))
        ex = min(P, key=lambda L: math.hypot(L[0]['x'] - med[0], L[0]['y'] - med[1]) + math.hypot(L[-1]['x'] - med[2], L[-1]['y'] - med[3]) + 4 * abs(len(L) - min(n_med, 12)))
        fin = ex[-1]
        code = issue_tir(fin) if fin['tir'] else 'ko' if fin['est_passe'] and (not fin['reussie']) else ''
        routes.append(dict(de=z0, a=z1, n=len(P), tirs=sum((1 for L in P if any((a['tir'] for a in L)))), buts=sum((1 for L in P if any((a['but'] for a in L)))), surface=sum((1 for L in P if any((dans_surface(a) for a in L)))), actions=r2(sum((len(L) for L in P)) / len(P)), gain=r2(sum((L[-1]['x'] - L[0]['x'] for L in P)) / len(P)), ex=[[r2(a['x']), r2(a['y'])] for a in ex], fin=code))
    routes.sort(key=lambda r: (-r['n'], -r['tirs'], -r['surface']))
    tete, reste = (routes[:garder - 1], routes[garder - 1:])
    danger = sorted(reste, key=lambda r: (-r['tirs'], -r['surface'], -r['n']))
    if danger and danger[0]['tirs']:
        danger[0]['danger'] = 1
        tete.append(danger[0])
    else:
        tete += reste[:1]
    return dict(possessions=n_t3, routes=tete)

def relance(jo, I, seqs, tr, gk, lg, douteux, nous, eux):
    recus = {(a['mi_temps'], a['t_s']): b for a, b in liens_joueurs(jo, seqs) if a['numero'] == gk}
    suite = defaultdict(list)
    for e in (nous, eux):
        for c in I[e]:
            suite[c['mi_temps']].append(c)
    out = []
    for a in sorted((a for a in jo if a['numero'] == gk and a['est_passe'] and (a['x'] is not None)), key=lambda a: (a['mi_temps'], a['t_s'])):
        h, t = (a['mi_temps'], a['t_s'])
        fin, m = (None, '')
        if a['reussie']:
            b = recus.get((h, t))
            if b is not None:
                fin, m = reception(tr, a, b, (a['x'], a['y']), douteux)
        else:
            apres = [c for c in suite[h] if t < c['t_s'] <= t + 5]
            if apres:
                t1 = min((c['t_s'] for c in apres))
                c = next((c for c in apres if c['t_s'] == t1 and sure(c)), None)
                if c is not None:
                    fin = (c['x'], c['y']) if c['equipe'] == nous else (105 - c['x'], W_TERRAIN - c['y'])
                    m = 'a'
        k = lg.get((h, t, nous))
        if k is None and fin is not None:
            d_ = math.hypot(fin[0] - a['x'], fin[1] - a['y'])
            k = 'c' if d_ < 15 else 'm' if d_ < 40 else 'l'
        out.append([r2(a['x']), r2(a['y']), r2(fin[0]) if fin else None, r2(fin[1]) if fin else None, int(bool(a['reussie'])), k, m])
    return out

def construit_match(cx, m):
    match_id = m['match_id']
    eq, jo = charge(cx, match_id)
    tg_eq, tg_jo = (tags_equipe(cx, match_id), tags_joueur(cx, match_id))
    A, B = (m['domicile'], m['exterieur'])
    seqs = possessions(eq, NOTRE_EQUIPE)
    liens, liens_prog, chrono = reseau(jo, seqs)
    env, reus = (Counter(), Counter())
    for (na, nb), n in liens.items():
        env[na] += n
    for a in jo:
        if a['est_passe'] and a['reussie']:
            reus[a['numero']] += 1
    couverture = {str(n): round(100 * env[n] / reus[n]) for n in reus if reus[n]}
    ZC, ZL = (6, 3)
    pts_j = {}
    joueurs = {}
    for a in jo:
        n = a['numero']
        if n is None:
            continue
        q = pts_j.setdefault(n, dict(tirs=[], prog=[], recup=[], pertes=[], zones=[0] * (ZC * ZL), couloirs=dict(act=[0, 0, 0], t3=[0, 0, 0], prog=[0, 0, 0])))
        if a['x'] is not None:
            x, y = (r2(a['x']), r2(a['y']))
            col = min(ZC - 1, max(0, int(a['x'] / 105.0 * ZC)))
            lig = min(ZL - 1, max(0, int(a['y'] / 68.0 * ZL)))
            q['zones'][lig * ZC + col] += 1
            cou = 0 if a['y'] >= 2 * W_TERRAIN / 3 else 1 if a['y'] >= W_TERRAIN / 3 else 2
            q['couloirs']['act'][cou] += 1
            if a['x'] >= TIERS:
                q['couloirs']['t3'][cou] += 1
            if a['progressive']:
                q['couloirs']['prog'][cou] += 1
            if a['tir']:
                q['tirs'].append([x, y, 3 if a['but'] else 2 if a['cadre'] else 1 if a['poteau'] else 0, int(a['t_s'] // 60)])
            if a['progressive']:
                q['prog'].append([x, y, int(bool(a['reussie']))])
            if a['recuperation']:
                q['recup'].append([x, y])
            if a['perte']:
                q['pertes'].append([x, y])
        j = joueurs.setdefault(n, dict(numero=n, nom=a['joueur'], joueur_id=a['joueur_id'], actions=0, passes=0, passes_ok=0, avant=0, prog=0, cles=0, tirs=0, buts=0, dribbles=0, duels=0, duels_ok=0, recup=0, pertes=0, t3=0, t3_passes=0, t3_ok=0, xs=[], ys=[]))
        j['actions'] += 1
        j['tags'] = tg_jo.get(n, {})
        for k, c in [('passes', 'est_passe'), ('avant', 'vers_avant'), ('prog', 'progressive'), ('cles', 'passe_cle'), ('tirs', 'tir'), ('buts', 'but'), ('dribbles', 'dribble'), ('duels', 'duel'), ('duels_ok', 'duel_gagne'), ('recup', 'recuperation'), ('pertes', 'perte')]:
            j[k] += int(bool(a[c]))
        if a['est_passe'] and a['reussie']:
            j['passes_ok'] += 1
        if a['x'] is not None:
            j['xs'].append(r2(a['x']))
            j['ys'].append(r2(a['y']))
            if a['x'] >= TIERS:
                j['t3'] += 1
                if a['est_passe']:
                    j['t3_passes'] += 1
                    j['t3_ok'] += int(bool(a['reussie']))
    for j in joueurs.values():
        xs = sorted(j['xs'])
        ys = sorted(j['ys'])
        j['x_med'] = xs[len(xs) // 2] if xs else None
        j['y_med'] = ys[len(ys) // 2] if ys else None
        del j['xs'], j['ys']
    gardiens = {n for n, j in joueurs.items() if radar.POSTES.get(j['nom']) == radar.GARDIEN}
    subis = [[r2(105 - a['x']), r2(W_TERRAIN - a['y']), 'but' if a['but'] else 'arret' if a['cadre'] else issue_tir(a), int(a['t_s'] // 60)] for a in eq if a['equipe'] != NOTRE_EQUIPE and a['tir'] and (a['x'] is not None)]
    for n in gardiens:
        joueurs[n]['gardien'] = 1
        if n in pts_j:
            pts_j[n]['subis'] = subis
    pts = lambda src: [[r2(a['x']), r2(a['y']), int(bool(a['reussie']))] for a in src if a['x'] is not None]
    BANDE = W_TERRAIN / 3.0

    def couloir(y):
        return 0 if y >= 2 * BANDE else 1 if y >= BANDE else 2

    def repartition(src):
        c = dict(n=[0, 0, 0], ok=[0, 0, 0], passes=[0, 0, 0])
        for a in src:
            if a['y'] is None:
                continue
            i = couloir(a['y'])
            c['n'][i] += 1
            if a['est_passe']:
                c['passes'][i] += 1
                c['ok'][i] += int(bool(a['reussie']))
        return c
    couloirs = {}
    for e in (A, B):
        de = [a for a in eq if a['equipe'] == e]
        couloirs[e] = dict(t3=repartition([a for a in de if a['x'] is not None and a['x'] >= TIERS]), prog=repartition([a for a in de if a['progressive']]), tirs=repartition([a for a in de if a['tir']])['n'])
    tr = catapult.traces(match_id)
    dout = douteux_de(cx, match_id)
    lg = longueurs(cx, match_id)
    eux = B if A == NOTRE_EQUIPE else A
    I = {e: instants(eq, e, dout) for e in (A, B)}
    poss = {e: seqs if e == NOTRE_EQUIPE else possessions(eq, e) for e in (A, B)}
    gk = next(iter(sorted(gardiens)), None)
    directions = dict(gps=int(tr is not None), equipes={e: profil_passes(I[e], poss[e], lg, e) for e in (A, B)}, joueurs=roses_joueurs(jo, seqs, tr, dout))
    relances = relance(jo, I, seqs, tr, gk, lg, dout, NOTRE_EQUIPE, eux) if gk is not None else []
    return dict(match_id=match_id, date=m['date'], domicile=A, exterieur=B, score=[m['score_dom'], m['score_ext']], equipes={A: stats_bloc(eq, A), B: stats_bloc(eq, B)}, tags={A: tg_eq.get(A, {}), B: tg_eq.get(B, {})}, tirs=[dict(equipe=a['equipe'], mt=a['mi_temps'], min=int(a['t_s'] // 60), x=r2(a['x']), y=r2(a['y']), but=int(bool(a['but'])), issue=issue_tir(a)) for a in eq if a['tir'] and a['x'] is not None], prog={e: pts([a for a in eq if a['equipe'] == e and a['progressive']]) for e in (A, B)}, tiers={e: pts([a for a in eq if a['equipe'] == e and a['est_passe'] and (a['x'] is not None) and (a['x'] >= TIERS)]) for e in (A, B)}, joueurs=sorted(joueurs.values(), key=lambda j: -j['actions']), couloirs=couloirs, pts_joueurs=pts_j, reseau=[[a, b, n] for (a, b), n in liens.items()], reseau_prog=[[a, b, n] for (a, b), n in liens_prog.items()], couverture=couverture, film=film(eq, jo, chrono, NOTRE_EQUIPE), directions=directions, circuits={e: circuits(I[e], poss[e]) for e in (A, B)}, relance=dict(numero=gk, passes=relances) if relances else None)
LIEUX = {'dom': True, 'domicile': True, 'home': True, 'd': True, 'ext': False, 'exterieur': False, 'extérieur': False, 'away': False, 'e': False}

def calendrier(equipes, aujourdhui=None):
    chemin = os.path.join(RACINE, 'calendrier.csv')
    if not os.path.exists(chemin):
        return ([], [])
    aujourdhui = aujourdhui or datetime.date.today()
    par_nom = {}
    for e in equipes:
        par_nom[e['nom'].lower()] = e
        par_nom[ligue.slug(e['nom'])] = e
    out, alertes = ([], [])
    for i, ligne in enumerate(open(chemin, encoding='utf-8-sig'), 1):
        ligne = ligne.strip()
        if not ligne or ligne.startswith('#'):
            continue
        champs = [c.strip() for c in (ligne.split(';') if ';' in ligne else ligne.split(','))]
        if len(champs) < 3:
            alertes.append('!! calendrier.csv ligne %d : il faut date ; adversaire ; dom ou ext' % i)
            continue
        date_txt, adv, lieu = (champs[0], champs[1], champs[2].lower())
        heure = champs[3] if len(champs) > 3 and champs[3] else None
        try:
            if '/' in date_txt:
                j_, m_, a_ = date_txt.split('/')
                date = datetime.date(int(a_), int(m_), int(j_))
            else:
                date = datetime.date.fromisoformat(date_txt)
        except ValueError:
            alertes.append('!! calendrier.csv ligne %d : date illisible « %s »' % (i, date_txt))
            continue
        if lieu not in LIEUX:
            alertes.append("!! calendrier.csv ligne %d : « %s » n'est ni dom ni ext" % (i, champs[2]))
            continue
        if date < aujourdhui:
            continue
        e = par_nom.get(adv.lower()) or par_nom.get(ligue.slug(adv))
        if e is None:
            alertes.append("   calendrier.csv ligne %d : « %s » n'est pas dans les classeurs de la ligue (pas de fiche d'avant-match)" % (i, adv))
        out.append(dict(date=date.isoformat(), heure=heure, adversaire=e['nom'] if e else adv, id=e['id'] if e else None, domicile=LIEUX[lieu]))
    out.sort(key=lambda m: (m['date'], m['heure'] or ''))
    return (out, alertes)

def cumul_physique(L):
    T = [x['tot'] for x in L if 'tot' in x]
    if not T:
        return None
    s = dict(matchs=len(T), min=round(sum((x['min'] for x in T)), 1), vmax=max((x['vmax'] for x in T)))
    for k in ('d', 'hsr1', 'hsr2', 'spr', 'nspr', 'pl'):
        s[k] = sum((x[k] for x in T))
    O = [x for x in T if 'acc' in x]
    if O:
        s['min_of'] = round(sum((x['min'] for x in O)), 1)
        for k in ('acc', 'accf', 'dec', 'decf'):
            s[k] = sum((x[k] for x in O))
    R = [x for x in T if 'ri' in x and x.get('rip')]
    if R:
        s['rip'] = sum((x['rip'] for x in R))
        s['ri'] = round(sum((x['ri'] * x['rip'] for x in R)) / s['rip'], 2)
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--push', action='store_true', help='commit et push apres generation')
    a = ap.parse_args([])
    os.makedirs(DATA, exist_ok=True)
    try:
        COMPET = json.load(open(os.path.join(RACINE, 'competitions.json'), encoding='utf-8'))
    except FileNotFoundError:
        COMPET = {'defaut': 'championnat', 'matchs': {}}
    COMPET.setdefault('defaut', 'championnat')
    COMPET.setdefault('matchs', {})
    cx = sqlite3.connect(BASE)
    cx.row_factory = sqlite3.Row
    matchs = [dict(r) for r in cx.execute('SELECT * FROM match ORDER BY date')]
    nom_ligue, alertes_ligue = ligue.publie(DATA)
    try:
        LIG = json.load(open(os.path.join(DATA, 'ligue.json'), encoding='utf-8'))
    except FileNotFoundError:
        LIG = {}
    LM = LIG.get('matchs', [])
    index, saison, fiches, cartes = ([], Counter(), {}, {})
    for m in matchs:
        d = construit_match(cx, m)
        lm_ = next((x for x in LM if x['date'] == m['date'] and NOTRE_EQUIPE in (x['dom']['nom'], x['ext']['nom'])), None)
        d['retenir'] = retenir.match(d, d.get('film'), lm_, NOTRE_EQUIPE)
        d['xg'] = [lm_['dom']['xg'], lm_['ext']['xg']] if lm_ else None
        d['physique'] = catapult.pour_match(cx, m['match_id'])
        if d['physique']:
            d['physique']['retenir'] = retenir.physique(d['physique'], {j['numero']: j['nom'] for j in d['joueurs']})
        adv = d['exterieur'] if d['domicile'] == NOTRE_EQUIPE else d['domicile']
        nous = d['equipes'].get(NOTRE_EQUIPE)
        if nous is None:
            print('  ! %s : pas de %s dans ce match, ignore' % (m['match_id'], NOTRE_EQUIPE))
            continue
        pts_m = d.pop('pts_joueurs', {})
        rad_m = radar.profils(cx, [m], seuil=radar.MIN_MATCH)['joueurs']
        for n, q in pts_m.items():
            c_ = cartes.setdefault(n, dict(matchs=[], tirs=[], prog=[], recup=[], pertes=[], zones=[0] * len(q['zones']), zones_m={}, couloirs=dict(act=[0, 0, 0], t3=[0, 0, 0], prog=[0, 0, 0]), couloirs_m={}, tags_m={}, radar_m={}))
            i_ = len(c_['matchs'])
            c_['matchs'].append(dict(match_id=m['match_id'], date=m['date'], adversaire=adv))
            for k in ('tirs', 'prog', 'recup', 'pertes'):
                c_[k] += [p + [i_] for p in q[k]]
            if 'subis' in q:
                c_.setdefault('subis', [])
                c_['subis'] += [p + [i_] for p in q['subis']]
            c_['zones'] = [x + y for x, y in zip(c_['zones'], q['zones'])]
            c_['zones_m'][m['match_id']] = q['zones']
            c_['couloirs_m'][m['match_id']] = q['couloirs']
            for k_ in ('act', 't3', 'prog'):
                c_['couloirs'][k_] = [x + y for x, y in zip(c_['couloirs'][k_], q['couloirs'][k_])]
            c_['radar_m'][m['match_id']] = rad_m.get(int(n))
        for j_ in d['joueurs']:
            c_ = cartes.get(j_['numero'])
            if c_ is not None:
                c_['tags_m'][m['match_id']] = j_.get('tags') or {}
        if d['physique']:
            avec = {j_['n'] for j_ in d['physique']['joueurs']}
            for j_ in d['physique']['joueurs']:
                c_ = cartes.get(j_['n'])
                if c_ is not None:
                    c_.setdefault('physique', []).append(dict(match_id=m['match_id'], date=m['date'], adversaire=adv, tot=j_['tot'], mt=j_['mt']))
            for n_ in sorted({n_ for n_, _ in d['physique'].get('sans_gps', [])} - avec):
                c_ = cartes.get(n_)
                if c_ is not None:
                    c_.setdefault('physique', []).append(dict(match_id=m['match_id'], date=m['date'], adversaire=adv, sans=1))
        with open(os.path.join(DATA, 'match_%s.json' % m['match_id']), 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, separators=(',', ':'))
        index.append(dict(match_id=m['match_id'], date=m['date'], adversaire=adv, domicile=d['domicile'] == NOTRE_EQUIPE, competition=COMPET['matchs'].get(m['match_id'], COMPET['defaut']), score=d['score'], xg=d['xg'], retenir=d['retenir'], resume=nous))
        for k, v in nous.items():
            if isinstance(v, (int, float)) and k != 'prog_depart':
                saison[k] += v
        for j in d['joueurs']:
            f_ = fiches.setdefault(j['numero'], dict(numero=j['numero'], nom=j['nom'], joueur_id=j['joueur_id'], matchs=[], total=Counter()))
            ligne = {k: j[k] for k in j if k not in ('nom', 'joueur_id', 'x_med', 'y_med', 'tags', 'gardien')}
            ligne['match_id'] = m['match_id']
            ligne['date'] = m['date']
            ligne['adversaire'] = adv
            ligne['x_med'], ligne['y_med'] = (j['x_med'], j['y_med'])
            f_['matchs'].append(ligne)
            if j.get('gardien'):
                f_['gardien'] = 1
            for k, v in j.items():
                if isinstance(v, int) and k not in ('numero', 'joueur_id', 'gardien'):
                    f_['total'][k] += v
            f_.setdefault('tags', Counter())
            for t_, n_ in (j.get('tags') or {}).items():
                f_['tags'][t_] += n_
        print('  %s  %s %d-%d  (%d joueurs)' % (m['date'], adv, d['score'][0], d['score'][1], len(d['joueurs'])))
    sien = "AND EXISTS (SELECT 1 FROM action_tag t WHERE t.action_id = a.action_id AND t.nature <> 'gardien')"
    for num, f_ in fiches.items():
        xs = [r[0] for r in cx.execute('SELECT x FROM action a WHERE numero=? AND equipe LIKE ? AND x IS NOT NULL ' + sien + ' ORDER BY x', (num, '%' + NOTRE_EQUIPE + '%'))]
        ys = [r[0] for r in cx.execute('SELECT y FROM action a WHERE numero=? AND equipe LIKE ? AND y IS NOT NULL ' + sien + ' ORDER BY y', (num, '%' + NOTRE_EQUIPE + '%'))]
        f_['x_med'] = r2(xs[len(xs) // 2]) if xs else None
        f_['y_med'] = r2(ys[len(ys) // 2]) if ys else None
    for f_ in fiches.values():
        f_['total'] = dict(f_['total'])
        f_['tags'] = dict(f_.get('tags', {}))
    phys = {str(n): s for n, s in ((n, cumul_physique(c_.get('physique', []))) for n, c_ in cartes.items()) if s}
    for n, c_ in cartes.items():
        if c_.get('physique'):
            c_['physique_retenir'] = retenir.physique_joueur(int(n), phys, c_['physique'])
    cal, alertes_cal = calendrier(LIG.get('equipes', []))
    for al in alertes_cal:
        print('  ' + al)
    with open(os.path.join(DATA, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(equipe=NOTRE_EQUIPE, maj=datetime.date.today().isoformat(), libelles=libelles.table(), retenir=retenir.saison(LIG, NOTRE_EQUIPE) if LIG else [], calendrier=cal, matchs=index, saison=dict(saison), radars=radar.profils(cx, matchs), physique=phys, joueurs=sorted(fiches.values(), key=lambda j: -j['total']['actions'])), f, ensure_ascii=False, separators=(',', ':'))
    for n, c_ in cartes.items():
        with open(os.path.join(DATA, 'joueur_%s.json' % n), 'w', encoding='utf-8') as f:
            json.dump(c_, f, ensure_ascii=False, separators=(',', ':'))
    ETRANGERS = {'matchs_video.json'}
    for al in alertes_ligue:
        print('  ' + al)
    if nom_ligue:
        ETRANGERS = ETRANGERS | {nom_ligue}
    elif os.path.exists(os.path.join(DATA, 'ligue.json')):
        ETRANGERS = ETRANGERS | {'ligue.json'}
    gardes = {'match_%s.json' % m['match_id'] for m in index} | {'joueur_%s.json' % n for n in cartes} | {'index.json'} | ETRANGERS
    for f in os.listdir(DATA):
        if f.endswith('.json') and f not in gardes:
            os.remove(os.path.join(DATA, f))
            print('  - %s retire (match absent de la base)' % f)
    poids = sum((os.path.getsize(os.path.join(DATA, f)) for f in os.listdir(DATA)))
    print('\n%d matchs, %d joueurs, %d Ko de JSON dans %s' % (len(index), len(fiches), poids // 1024, DATA))
    if a.push:
        for cmd in (['git', 'add', '-A'], ['git', 'commit', '-m', 'Donnees a jour : %d matchs' % len(index)], ['git', 'push']):
            p = subprocess.run(cmd, cwd=WEB, capture_output=True, text=True)
            if p.returncode and 'nothing to commit' not in p.stdout + p.stderr:
                print('  ! %s : %s' % (' '.join(cmd), (p.stderr or p.stdout).strip()[:200]))
                return 1
        print('  pousse sur GitHub -> Cloudflare redeploie le site')
    return 0
