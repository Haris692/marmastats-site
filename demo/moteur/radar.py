import collections
NOTRE_EQUIPE = '{NOUS}'
POSTES = {}
GARDIEN = 'GK'
LIGNES = {'LCB': 'axe', 'RCB': 'axe', 'LB': 'lateral', 'RB': 'lateral', 'LCDM': 'milieu', 'RCDM': 'milieu', 'RCM': 'milieu', 'CAM': 'offensif', 'LCAM': 'offensif', 'RCAM': 'offensif', 'LAM': 'ailier', 'RAM': 'ailier', 'CF': 'attaque'}
MESURES = {'volume': ['Passes réussies', 'Passes non-réussies'], 'precision': None, 'progression': ['Passes progressives réussies'], 'avant': ["Passes vers l'avant réussies"], 'longue': ['Passes longues'], 'centre': ['Centres réussis'], 'surface': ['Passes dans la surface de réparation réussies'], 'creation': ['Passes clés réussies', 'Occasions créées', 'Passes décisives'], 'tir': ['Tirs cadrés', 'Tirs hors cadre', 'Tir sur le poteau / sur la barre'], 'dribble': ['Dribbles réussis'], 'duel': ['Duels gangés'], 'aerien': ['Duels aériens gagnés'], 'tacle': ['Tacles réussis'], 'recuperation': ['Récupérations de balle'], 'recup_haute': ['Récupérations dans le camp adverse'], 't3': 'TIERS'}
AXES_PAR_LIGNE = {'axe': ['volume', 'precision', 'progression', 'longue', 'aerien', 'duel', 'tacle', 'recuperation'], 'lateral': ['volume', 'precision', 'progression', 'centre', 'dribble', 'duel', 'recuperation', 't3'], 'milieu': ['volume', 'precision', 'progression', 'avant', 'creation', 'duel', 'recuperation', 'recup_haute'], 'offensif': ['precision', 'progression', 'creation', 'surface', 'dribble', 'tir', 't3', 'duel'], 'ailier': ['precision', 'progression', 'centre', 'creation', 'dribble', 'tir', 't3', 'duel'], 'attaque': ['precision', 'creation', 'surface', 'dribble', 'tir', 'aerien', 'duel', 't3']}
DEFAUT = ['volume', 'precision', 'progression', 'creation', 'tir', 'dribble', 'duel', 'recuperation']
HORS_AXE = [('pertes', ['Pertes de ballons']), ('passes_ratees', ['Passes non-réussies']), ('duels_perdus', ['Duels perdus'])]
MIN_MINUTES = 80.0
MIN_MATCH = 45.0

def temps_de_jeu(cx, match_id):
    fin = cx.execute('SELECT MAX(t_s) FROM action WHERE match_id=?', (match_id,)).fetchone()[0]
    js = [dict(numero=r[0], t1=r[1], t2=r[2], nom=r[3]) for r in cx.execute('SELECT numero, MIN(t_s), MAX(t_s), MAX(joueur) FROM action\n           WHERE match_id=? AND equipe LIKE ? AND numero IS NOT NULL\n           GROUP BY numero', (match_id, '%' + NOTRE_EQUIPE + '%'))]
    gk = {j['numero'] for j in js if POSTES.get(j['nom']) == GARDIEN}
    js = [j for j in js if j['numero'] not in gk]
    for j in js:
        j['debut'] = 0.0 if j['t1'] / fin < 0.11 else None
        j['fin'] = fin if j['t2'] / fin > 0.94 else None
    sorties = [j for j in js if j['fin'] is None]
    for e in sorted([j for j in js if j['debut'] is None], key=lambda j: j['t1']):
        libres = [s for s in sorties if not s.get('_pris') and s['t2'] <= e['t1']]
        if libres:
            s = max(libres, key=lambda s: s['t2'])
            instant = (s['t2'] + e['t1']) / 2
            s['_pris'] = True
            s['fin'] = instant
            e['debut'] = instant
        else:
            e['debut'] = e['t1']
    for s in sorties:
        if s['fin'] is None:
            s['fin'] = s['t2']
    out = {j['numero']: (j['fin'] - j['debut']) / fin * 90 for j in js}
    out.update({n: 90.0 for n in gk})
    return out

def _compte(cx, match_id, numero, tags):
    q = 'SELECT COUNT(DISTINCT a.action_id) FROM action a JOIN action_tag t USING(action_id) WHERE a.match_id=? AND a.numero=? AND a.equipe LIKE ? AND t.tag IN (%s)' % ','.join('?' * len(tags))
    return cx.execute(q, [match_id, numero, '%' + NOTRE_EQUIPE + '%'] + tags).fetchone()[0]

def _centile(valeurs, v):
    n = len(valeurs)
    dessous = sum((1 for x in valeurs if x < v))
    egaux = sum((1 for x in valeurs if x == v))
    return round((dessous + egaux / 2.0) / n * 100)

def _compte_tiers(cx, match_id, numero):
    return cx.execute('SELECT COUNT(*) FROM action WHERE match_id=? AND numero=? AND equipe LIKE ? AND x >= 70', (match_id, numero, '%' + NOTRE_EQUIPE + '%')).fetchone()[0]

def profils(cx, matchs, seuil=None):
    seuil = MIN_MINUTES if seuil is None else seuil
    brut = collections.defaultdict(lambda: collections.defaultdict(float))
    minutes = collections.defaultdict(float)
    noms = {}
    for m in matchs:
        mid = m['match_id']
        tps = temps_de_jeu(cx, mid)
        for numero, mn in tps.items():
            minutes[numero] += mn
            for nom, tags in list(MESURES.items()) + HORS_AXE:
                if tags == 'TIERS':
                    brut[numero][nom] += _compte_tiers(cx, mid, numero)
                elif tags:
                    brut[numero][nom] += _compte(cx, mid, numero, tags)
        for numero, nom in cx.execute('SELECT DISTINCT numero, joueur FROM action WHERE match_id=? AND equipe LIKE ? AND numero IS NOT NULL', (mid, '%' + NOTRE_EQUIPE + '%')):
            if nom:
                noms[numero] = nom
    gardiens = {n for n, nom in noms.items() if POSTES.get(nom) == GARDIEN}
    taux = {}
    for numero, v in brut.items():
        mn = minutes[numero]
        if mn <= 0 or numero in gardiens:
            continue
        t = {nom: v[nom] / mn * 90 for nom, tags in list(MESURES.items()) + HORS_AXE if tags}
        total_p = v['volume']
        t['precision'] = 100.0 * (total_p - v['passes_ratees']) / total_p if total_p else 0.0
        duels = v['duel'] + v['duels_perdus']
        t['pct_duels'] = 100.0 * v['duel'] / duels if duels else 0.0
        taux[numero] = t
    base = [n for n in taux if minutes[n] >= seuil]
    if len(base) < 4:
        base = list(taux)
    out = {}
    for numero, t in taux.items():
        poste = POSTES.get(noms.get(numero))
        ligne = LIGNES.get(poste)
        axes = []
        for nom in AXES_PAR_LIGNE.get(ligne, DEFAUT):
            vals = [taux[b][nom] for b in base]
            tries = sorted(vals, reverse=True)
            v = t[nom]
            axes.append(dict(cle=nom, valeur=round(v, 1), centile=_centile(vals, v), rang=sum((1 for x in tries if x > v)) + 1, sur=len(base)))
        out[numero] = dict(numero=numero, poste=poste, ligne=ligne, minutes=round(minutes[numero]), reference=numero in base, axes=axes, hors_axe=dict(pertes=round(t['pertes'], 1), pct_duels=round(t['pct_duels'])))
    for numero in gardiens:
        if minutes[numero] > 0:
            out[numero] = dict(numero=numero, poste=GARDIEN, ligne='gardien', minutes=round(minutes[numero]), reference=False, axes=[], hors_axe={})
    return dict(effectif=len(base), min_minutes=seuil, joueurs=out)
