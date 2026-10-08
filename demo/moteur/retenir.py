L_TERRAIN = 105.0

def nombre(v, dec, lang):
    s = ('%.' + str(dec) + 'f') % v
    return s.replace('.', ',') if lang == 'fr' else s

def rang_txt(r, n, lang):
    if lang == 'fr':
        return ('1er' if r == 1 else '%de' % r) + ' sur %d' % n
    if lang == 'en':
        suf = 'th' if 10 <= r % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(r % 10, 'th')
        return '%d%s of %d' % (r, suf, n)
    return 'المركز %d من %d' % (r, n)

def phrase(type_, cible, score, fr, en, ar):
    return dict(type=type_, cible=cible, score=score, fr=fr, en=en, ar=ar)

def rang(valeurs, v, plus_haut_meilleur=True):
    if plus_haut_meilleur:
        return 1 + sum((1 for x in valeurs if x > v))
    return 1 + sum((1 for x in valeurs if x < v))

def score_rang(r, n):
    if r == 1 or r == n:
        return 1.6
    if r == 2 or r == n - 1:
        return 1.2
    return 0

def choisit(cands, n=3, unique=True):
    cands = sorted([c for c in cands if c['score'] > 0], key=lambda c: -c['score'])
    pris, cartes = ([], set())
    for c in cands:
        if unique and c['cible'][0] in cartes:
            continue
        pris.append(c)
        cartes.add(c['cible'][0])
        if len(pris) == n:
            break
    if not any((c['type'] == 'faible' for c in pris)):
        faibles = [c for c in cands if c['type'] == 'faible' and c['cible'][0] not in cartes]
        if faibles and len(pris) == n:
            pris[-1] = faibles[0]
        elif faibles:
            pris.append(faibles[0])
    for c in pris:
        c.pop('score', None)
    return pris

def club(e, equipes, matchs):
    if not e.get('mj') or not e.get('tac'):
        return []
    tac, mj, n = (e['tac'], e['mj'], len(equipes))
    autres = [x for x in equipes if x.get('mj') and x.get('tac')]
    pm = lambda x, k: (x['tac'].get(k) or 0) / x['mj']
    moy = lambda vals: sum(vals) / len(vals) if vals else 0
    C = []
    ks = ['att_g', 'att_c', 'att_d']

    def parts(x):
        t = sum((x['tac'].get(k) or 0 for k in ks))
        return [(x['tac'].get(k) or 0) / t for k in ks] if t else None
    p = parts(e)
    if p:
        lig = [parts(x) for x in autres if parts(x)]
        lm = [moy([v[i] for v in lig]) for i in range(3)]
        i = max(range(3), key=lambda i: p[i] - lm[i])
        ecart = p[i] - lm[i]
        if ecart >= 0.06:
            cote = [('par son côté gauche', 'down its left', 'من جهته اليسرى'), ("par l'axe", 'through the middle', 'من العمق'), ('par son côté droit', 'down its right', 'من جهته اليمنى')][i]
            P, Q = (round(100 * p[i]), round(100 * lm[i]))
            C.append(phrase('style', ['an-couloirs'], ecart / 0.06, 'Attaque surtout %s : %d %% de ses attaques (moyenne de la ligue %d %%).' % (cote[0], P, Q), 'Attacks mostly %s: %d %% of its attacks (league average %d %%).' % (cote[1], P, Q), 'يهاجم غالبًا %s: %d٪ من هجماته (متوسط الدوري %d٪).' % (cote[2], P, Q)))
    v, lm = (pm(e, 'contres'), moy([pm(x, 'contres') for x in autres]))
    if lm:
        r = v / lm
        if r >= 1.3 or r <= 0.6:
            haut = r >= 1.3
            C.append(phrase('style', ['an-types'], abs(r - 1) / 0.3, ('Joue beaucoup en contre-attaque' if haut else 'Contre-attaque peu') + ' : %s par match, contre %s en moyenne.' % (nombre(v, 1, 'fr'), nombre(lm, 1, 'fr')), ('Counter-attacks a lot' if haut else 'Rarely counter-attacks') + ': %s per match, against %s on average.' % (nombre(v, 1, 'en'), nombre(lm, 1, 'en')), ('يعتمد كثيرًا على الهجمات المرتدة' if haut else 'نادرًا ما يلجأ إلى الهجمات المرتدة') + ': %s في المباراة مقابل %s في المتوسط.' % (nombre(v, 1, 'ar'), nombre(lm, 1, 'ar'))))
    cpa = lambda x: pm(x, 'corners_tir') + pm(x, 'cf_tir')
    v, lm = (cpa(e), moy([cpa(x) for x in autres]))
    if lm and v / lm >= 1.4:
        C.append(phrase('fort', ['an-types'], (v / lm - 1) / 0.3, 'Dangereux sur coups de pied arrêtés : %s tirs par match après un corner ou un coup franc (%s en moyenne).' % (nombre(v, 1, 'fr'), nombre(lm, 1, 'fr')), 'Dangerous from set pieces: %s shots per match after a corner or free kick (%s on average).' % (nombre(v, 1, 'en'), nombre(lm, 1, 'en')), 'خطير في الكرات الثابتة: %s تسديدة في المباراة بعد ركنية أو ركلة حرة (%s في المتوسط).' % (nombre(v, 1, 'ar'), nombre(lm, 1, 'ar'))))

    def ppda(cid):
        vals = [m[c]['ppda'] for m in matchs for c in ('dom', 'ext') if m[c]['id'] == cid and m[c].get('ppda') is not None]
        return sum(vals) / len(vals) if vals else None
    tous = {x['id']: ppda(x['id']) for x in autres}
    tous = {k: v for k, v in tous.items() if v is not None}
    if tous.get(e['id']) is not None:
        v, nn = (tous[e['id']], len(tous))
        r = rang(list(tous.values()), v, plus_haut_meilleur=False)
        s = score_rang(r, nn)
        if s and r <= 2:
            C.append(phrase('style', ['lg-style'], s, 'Presse très haut : PPDA de %s, le pressing %s.' % (nombre(v, 1, 'fr'), 'le plus intense de la ligue' if r == 1 else 'le 2e plus intense de la ligue'), "Presses very high: PPDA of %s, the league's %s pressing." % (nombre(v, 1, 'en'), 'most intense' if r == 1 else '2nd most intense'), 'يضغط عاليًا جدًا: PPDA قدره %s، %s.' % (nombre(v, 1, 'ar'), 'الأكثر ضغطًا في الدوري' if r == 1 else 'ثاني أكثر الفرق ضغطًا')))
        elif s:
            C.append(phrase('style', ['lg-style'], s, "Presse peu et attend : PPDA de %s, %s pour l'intensité du pressing." % (nombre(v, 1, 'fr'), rang_txt(r, nn, 'fr')), 'Sits off rather than presses: PPDA of %s, %s for pressing intensity.' % (nombre(v, 1, 'en'), rang_txt(r, nn, 'en')), 'يتراجع ولا يضغط كثيرًا: PPDA قدره %s، %s في شدة الضغط.' % (nombre(v, 1, 'ar'), rang_txt(r, nn, 'ar'))))
    ks = ['rel_courte', 'rel_moy', 'rel_longue']

    def rel(x):
        t = sum((x['tac'].get(k) or 0 for k in ks))
        return [(x['tac'].get(k) or 0) / t for k in ks] if t else None
    p = rel(e)
    if p:
        lig = [rel(x) for x in autres if rel(x)]
        for i, (fr, en, ar) in ((2, ('long', 'long', 'طويلة')), (0, ('court', 'short', 'قصيرة'))):
            lm = moy([v[i] for v in lig])
            if p[i] - lm >= 0.15:
                P, Q = (round(100 * p[i]), round(100 * lm))
                borne = 'plus de 40 m' if i == 2 else 'moins de 15 m'
                C.append(phrase('style', ['anRel'], (p[i] - lm) / 0.12, 'Le gardien relance %s : %d %% de ses dégagements font %s (ligue %d %%).' % (fr, P, borne, Q), 'The goalkeeper goes %s: %d %% of goal kicks are %s (league %d %%).' % (en, P, 'over 40 m' if i == 2 else 'under 15 m', Q), 'الحارس يلعب كرات %s: %d٪ من ركلاته %s (الدوري %d٪).' % (ar, P, 'تتجاوز 40 م' if i == 2 else 'أقل من 15 م', Q)))
    for k, cible, plus, txt in (('xgc', ['lg-profil', 'pr-face'], False, (('Défense solide', 'Solid defence', 'دفاع صلب'), ("Concède beaucoup d'occasions", 'Concedes a lot of chances', 'يسمح بالكثير من الفرص'), ('xG concédé par match', 'xG conceded per match', 'xG مستقبلة في المباراة'))), ('xg', ['lg-profil', 'pr-face'], True, (("Se crée beaucoup d'occasions", 'Creates a lot of chances', 'يصنع الكثير من الفرص'), ("Se crée peu d'occasions", 'Creates few chances', 'يصنع فرصًا قليلة'), ('xG créé par match', 'xG created per match', 'xG مصنوعة في المباراة')))):
        vals = [x[k] / x['mj'] for x in autres if x.get(k) is not None]
        if e.get(k) is None:
            continue
        v = e[k] / mj
        r = rang(vals, v, plus)
        s = score_rang(r, len(vals))
        if not s:
            continue
        bon = r <= 2
        t0 = txt[0] if bon else txt[1]
        C.append(phrase('fort' if bon else 'faible', cible, s, '%s : %s %s, %s.' % (t0[0], nombre(v, 2, 'fr'), txt[2][0], rang_txt(r, len(vals), 'fr')), '%s: %s %s, %s.' % (t0[1], nombre(v, 2, 'en'), txt[2][1], rang_txt(r, len(vals), 'en')), '%s: %s %s، %s.' % (t0[2], nombre(v, 2, 'ar'), txt[2][2], rang_txt(r, len(vals), 'ar'))))
    vals = [x['aerien_pct'] for x in autres if x.get('aerien_pct') is not None]
    if e.get('aerien_pct') is not None and vals:
        v = e['aerien_pct']
        r = rang(vals, v)
        s = score_rang(r, len(vals))
        if s:
            bon = r <= 2
            C.append(phrase('fort' if bon else 'faible', ['lg-profil', 'pr-face'], s * 0.9, '%s dans les airs : %d %% de duels aériens gagnés, %s.' % ('Fort' if bon else 'Fragile', round(100 * v), rang_txt(r, len(vals), 'fr')), '%s in the air: %d %% of aerial duels won, %s.' % ('Strong' if bon else 'Weak', round(100 * v), rang_txt(r, len(vals), 'en')), '%s في الكرات الهوائية: يفوز بـ %d٪ من الالتحامات الهوائية، %s.' % ('قوي' if bon else 'ضعيف', round(100 * v), rang_txt(r, len(vals), 'ar'))))
    vals = [x['pertes_bas'] / x['mj'] for x in autres if x.get('pertes_bas') is not None]
    if e.get('pertes_bas') is not None and vals:
        v = e['pertes_bas'] / mj
        r = rang(vals, v, plus_haut_meilleur=False)
        if r >= len(vals) - 1:
            C.append(phrase('faible', ['lg-profil', 'pr-face'], score_rang(r, len(vals)), 'Perd beaucoup de ballons dans son camp : %s par match, %s.' % (nombre(v, 1, 'fr'), rang_txt(r, len(vals), 'fr')), 'Loses the ball often in its own half: %s per match, %s.' % (nombre(v, 1, 'en'), rang_txt(r, len(vals), 'en')), 'يفقد الكرة كثيرًا في نصف ملعبه: %s في المباراة، %s.' % (nombre(v, 1, 'ar'), rang_txt(r, len(vals), 'ar'))))
    if tac.get('dist_recup') is not None:
        h = L_TERRAIN - tac['dist_recup']
        lm = moy([L_TERRAIN - x['tac']['dist_recup'] for x in autres if x['tac'].get('dist_recup') is not None])
        if abs(h - lm) >= 4:
            haut = h > lm
            C.append(phrase('style', ['an-haut'], abs(h - lm) / 4, 'Récupère le ballon %s : à %d m de son but en moyenne (ligue %d m).' % ('haut' if haut else 'bas', round(h), round(lm)), 'Wins the ball back %s: %d m from its own goal on average (league %d m).' % ('high' if haut else 'deep', round(h), round(lm)), 'يستعيد الكرة في %s: على بعد %d م من مرماه في المتوسط (الدوري %d م).' % ('مناطق متقدمة' if haut else 'مناطق متأخرة', round(h), round(lm))))
    return choisit(C)
SAISON_LIGNES = [('buts', 0, 'Buts marqués', 'Goals scored', 'الأهداف المسجلة'), ('xg', 0, 'Buts attendus (xG)', 'Expected goals (xG)', 'الأهداف المتوقعة (xG)'), ('tirs', 0, 'Tirs', 'Shots', 'التسديدات'), ('surface', 0, 'Entrées dans la surface adverse', "Entries into the opponent's box", 'الدخول إلى منطقة جزاء الخصم'), ('poss', 1, 'Possession', 'Possession', 'الاستحواذ'), ('passes_pct', 1, 'Passes réussies', 'Pass accuracy', 'دقة التمرير'), ('prog', 1, 'Passes progressives', 'Progressive passes', 'التمريرات التقدمية'), ('t3', 1, 'Entrées dans le dernier tiers', 'Final third entries', 'الدخول إلى الثلث الأخير'), ('bc', 2, 'Buts encaissés', 'Goals conceded', 'الأهداف المستقبلة'), ('xgc', 2, 'Buts attendus concédés (xG)', 'Expected goals conceded (xG)', 'الأهداف المتوقعة ضده (xG)'), ('recup_haut', 2, 'Ballons récupérés dans le camp adverse', "Recoveries in the opponent's half", 'استعادة الكرة في نصف الخصم'), ('duels_pct', 2, 'Duels gagnés', 'Duels won', 'الالتحامات المكسوبة')]

def nb_court(x, dec, lang):
    r = round(x, dec)
    return '%d' % r if r == int(r) else nombre(r, dec, lang)

def saison_valeurs(lig, k):
    if k == 'bc':
        return {c['id']: c['bc'] / c['j'] for c in lig.get('classement') or [] if c.get('j')}
    nat = next((d['n'] for d in lig['defs_equipe'] if d['k'] == k), 'n')
    out = {}
    for e in lig['equipes']:
        v = e.get(k)
        if v is None or not e.get('mj'):
            continue
        out[e['id']] = v / e['mj'] if nat in ('n', 'x') else v
    return out

def saison(lig, nous):
    moi = next((e for e in lig.get('equipes', []) if e['nom'] == nous), None)
    if not moi:
        return []
    sens = {d['k']: d['s'] for d in lig.get('defs_equipe', [])}
    sens['bc'] = -1
    C = []
    for k, theme, fr, en, ar in SAISON_LIGNES:
        vals = saison_valeurs(lig, k)
        if moi['id'] not in vals or len(vals) < 4:
            continue
        v, tous = (vals[moi['id']], list(vals.values()))
        s = sens.get(k, 0)
        n = len(tous)
        moy = sum(tous) / n
        et = (sum(((x - moy) ** 2 for x in tous)) / n) ** 0.5
        r = rang(tous, v, plus_haut_meilleur=s >= 0)
        sc = score_rang(r, n)
        if not sc:
            continue
        if s:
            bon = r <= 2
            if (v - moy) * s * (1 if bon else -1) <= 0.5 * et:
                continue
            type_ = 'fort' if bon else 'faible'
        else:
            type_ = 'style'
            sc *= 0.8
        sc += min(abs(v - moy) / et, 3) / 10 if et else 0
        pct = k.endswith('_pct') or k == 'poss'
        dec = 2 if k in ('xg', 'xgc') else 1

        def val(x, l):
            return '%d' % round(100 * x) if pct else nb_court(x, dec, l)
        txt = {}
        for l, lib in (('fr', fr), ('en', en), ('ar', ar)):
            a, m, rt = (val(v, l), val(moy, l), rang_txt(r, n, l))
            if l == 'fr':
                txt[l] = '%s : %s, %s (moyenne de la ligue : %s).' % (lib, a + ' %' if pct else a + ' par match', rt, m + ' %' if pct else m)
            elif l == 'en':
                txt[l] = '%s: %s, %s (league average: %s).' % (lib, a + ' %' if pct else a + ' per match', rt, m + ' %' if pct else m)
            else:
                txt[l] = '%s: %s، %s (متوسط الدوري: %s).' % (lib, a + '٪' if pct else a + ' في المباراة', rt, m + '٪' if pct else m)
        c = phrase(type_, ['ac-l-' + k, 'ac-ligue'], sc, txt['fr'], txt['en'], txt['ar'])
        c['theme'] = theme
        C.append(c)
    C.sort(key=lambda c: -c['score'])
    pris = []
    for c in C:
        if len(pris) < 3 and all((c['theme'] != p['theme'] for p in pris)):
            pris.append(c)
    for c in C:
        if len(pris) < 3 and c not in pris:
            pris.append(c)
    faibles = [c for c in C if c['type'] == 'faible']
    if faibles and (not any((c['type'] == 'faible' for c in pris))):
        if len(pris) == 3:
            pris.pop()
        pris.append(faibles[0])
    pris.sort(key=lambda c: c['theme'])
    for c in pris:
        c.pop('score', None)
        c.pop('theme', None)
    return pris

def _minute(m, mt1):
    if m <= mt1:
        a = int(m) + 1
        return '45+%d' % (a - 45) if a > 45 else str(a)
    b = 45 + int(m - mt1) + 1
    return '90+%d' % (b - 90) if b > 90 else str(b)

def _temps_fort(bins, qui, mt1):
    autre = 'eux' if qui == 'nous' else 'nous'
    meilleur = None
    for i in range(len(bins)):
        for lg in (2, 3, 4):
            S = bins[i:i + lg]
            if len(S) < lg or S[0]['m0'] < mt1 <= S[-1]['m0']:
                continue
            n, m = (sum((b[qui] for b in S)), sum((b[autre] for b in S)))
            cle = (n - m, -lg)
            if meilleur is None or cle > meilleur[0]:
                meilleur = (cle, S, n, m)
    if not meilleur:
        return None
    _, S, n, m = meilleur
    if n - m < 6 or n < 1.5 * max(m, 1):
        return None
    return dict(de=_minute(S[0]['m0'], mt1), a=_minute(S[-1]['m1'] - 0.01, mt1), n=n, m=m)

def _de(nom):
    return ("d'" if nom[:1].upper() in 'AEIOUY' else 'de ') + nom

def _ord_fr(minute):
    return '1re' if minute == '1' else minute + 'e'

def match(d, film, ligue_m, nous):
    adv = d['exterieur'] if d['domicile'] == nous else d['domicile']
    C = []
    mo = (film or {}).get('momentum')
    if mo:
        for qui, nom, type_ in (('nous', nous, 'fort'), ('eux', adv, 'faible')):
            tf = _temps_fort(mo, qui, film['mt1'])
            if tf:
                C.append(phrase(type_, ['m-momentum'], 2 if qui == 'nous' else 1.9, 'Temps fort %s de la %s à la %s minute : %d actions dans le dernier tiers adverse, contre %d.' % (_de(nom), _ord_fr(tf['de']), _ord_fr(tf['a']), tf['n'], tf['m']), "%s's best spell, minutes %s to %s: %d actions in the final third, against %d." % (nom, tf['de'], tf['a'], tf['n'], tf['m']), 'أفضل فترات %s من الدقيقة %s إلى %s: %d لعبة في الثلث الأخير مقابل %d.' % ('{NOUS_AR}' if nom == nous else nom, tf['de'], tf['a'], tf['n'], tf['m'])))
    if ligue_m:
        cote = 'dom' if ligue_m['dom']['nom'] == nous else 'ext'
        x_n, x_e = (ligue_m[cote]['xg'], ligue_m['ext' if cote == 'dom' else 'dom']['xg'])
        b_n, b_e = (ligue_m[cote]['buts'], ligue_m['ext' if cote == 'dom' else 'dom']['buts'])
        if x_n is not None and x_e is not None:
            xs = {l: (nombre(x_n, 2, l), nombre(x_e, 2, l)) for l in ('fr', 'en', 'ar')}
            diff = x_n - x_e
            if b_n > b_e and diff < -0.3:
                t = ('fort', "{NOUS} a gagné en se créant moins d'occasions que l'adversaire : xG %s contre %s.", '{NOUS} won while creating fewer chances than the opponent: xG %s to %s.', 'فاز {NOUS_AR} رغم أنه صنع فرصًا أقل من المنافس: xG %s مقابل %s.')
            elif b_n < b_e and diff > 0.3:
                t = ('faible', "{NOUS} a perdu en se créant plus d'occasions que l'adversaire : xG %s contre %s.", '{NOUS} lost despite creating more chances than the opponent: xG %s to %s.', 'خسر {NOUS_AR} رغم أنه صنع فرصًا أكثر من المنافس: xG %s مقابل %s.')
            elif b_n == b_e and abs(diff) >= 0.8:
                t = ('faible' if diff > 0 else 'fort', "Match nul alors que %s s'est créé nettement plus d'occasions : xG %%s contre %%s." % ('{NOUS}' if diff > 0 else "l'adversaire"), 'A draw although %s created far more chances: xG %%s to %%s.' % ('{NOUS}' if diff > 0 else 'the opponent'), 'تعادل رغم أن %s صنع فرصًا أكثر بكثير: xG %%s مقابل %%s.' % ('{NOUS_AR}' if diff > 0 else 'المنافس'))
            else:
                t = ('style', "Le score suit les occasions : xG %s pour {NOUS}, %s pour l'adversaire.", 'The score reflects the chances: xG %s for {NOUS}, %s for the opponent.', 'النتيجة تعكس الفرص: xG %s لـ{NOUS_AR} و%s للمنافس.')
            C.append(phrase(t[0], ['m-momentum'], 1.8, t[1] % xs['fr'], t[2] % xs['en'], t[3] % xs['ar']))
    impl = (film or {}).get('implication')
    if impl and len(impl) >= 2:
        (n1, nom1, p1), (n2, nom2, p2) = (impl[0], impl[1])
        C.append(phrase('style', ['m-schema'], 1.5, "Le jeu passe par %s (%d %% des ballons joués par l'équipe), puis %s (%d %%)." % (nom1, p1, nom2, p2), "Play runs through %s (%d %% of the team's involvements), then %s (%d %%)." % (nom1, p1, nom2, p2), 'اللعب يمر عبر %s (%d٪ من مشاركات الفريق)، ثم %s (%d٪).' % (nom1, p1, nom2, p2)))
    c = (d.get('couloirs') or {}).get(nous, {}).get('t3', {}).get('n')
    if c and sum(c) >= 20:
        tot = sum(c)
        i = max(range(3), key=lambda i: c[i])
        if c[i] / tot >= 0.42:
            cote = [('la gauche', 'the left', 'اليسار'), ("l'axe", 'the middle', 'العمق'), ('la droite', 'the right', 'اليمين')][i]
            P = round(100 * c[i] / tot)
            C.append(phrase('style', ['m-couloirs'], 1.2, '{NOUS} a surtout attaqué par %s : %d %% de ses actions dans le dernier tiers.' % (cote[0], P), '{NOUS} attacked mostly down %s: %d %% of its final-third actions.' % (cote[1], P), 'هاجم {NOUS_AR} غالبًا من %s: %d٪ من لعباته في الثلث الأخير.' % (cote[2], P)))
    return choisit(C, n=4, unique=False)
ARRET = 60

def physique(p, noms):

    def nom(n):
        return str(noms.get(n, n)).split(' ')[-1]

    def nom_ar(n):
        return '\u2066' + nom(n) + '\u2069'
    J = [j for j in p.get('joueurs', []) if j['tot']['min'] >= 30 and (not j['tot'].get('partiel'))]
    C = []
    if J:
        j = max(J, key=lambda j: j['tot']['d'])
        km = {l: nombre(j['tot']['d'] / 1000.0, 1, l) for l in ('fr', 'en', 'ar')}
        x = phrase('style', ['m-phys-graphes'], 2, "C'est %s qui a le plus couru : %s km." % (nom(j['n']), km['fr']), '%s covered the most ground: %s km.' % (nom(j['n']), km['en']), '%s هو من ركض أكثر: %s كم.' % (nom_ar(j['n']), km['ar']))
        x['m'] = 'd'
        C.append(x)
        h = max(J, key=lambda j: j['tot']['hsr2'] + j['tot']['spr'])
        if h['n'] != j['n']:
            hi = h['tot']['hsr2'] + h['tot']['spr']
            x = phrase('style', ['m-phys-graphes'], 1.6, 'Le plus de courses rapides : %s, %d m à plus de 19,8 km/h.' % (nom(h['n']), hi), 'Most high-speed running: %s, %d m above 19.8 km/h.' % (nom(h['n']), hi), 'أكثر جري سريع: %s، %d م بسرعة تفوق 19.8 كم/س.' % (nom_ar(h['n']), hi))
            x['m'] = 'hi'
        else:
            v = max(J, key=lambda j: j['tot']['vmax'])
            vs = {l: nombre(v['tot']['vmax'], 1, l) for l in ('fr', 'en', 'ar')}
            x = phrase('style', ['m-phys-graphes'], 1.6, 'Le plus rapide du match : %s, %s km/h.' % (nom(v['n']), vs['fr']), 'Fastest in the match: %s, %s km/h.' % (nom(v['n']), vs['en']), 'الأسرع في المباراة: %s، %s كم/س.' % (nom_ar(v['n']), vs['ar']))
            x['m'] = 'vmax'
        C.append(x)
    T = p.get('tranches') or []
    ecartees = [t for t in T if t['min'] and t['d'] / t['min'] < ARRET]

    def mpm_mt(h):
        L = [t for t in T if t['mt'] == h and t not in ecartees]
        mn = sum((t['min'] for t in L))
        return sum((t['d'] for t in L)) / mn if mn else None
    a, b = (mpm_mt(1), mpm_mt(2))
    if a and b:
        hors = {'fr': ' (arrêts de jeu exclus)', 'en': ' (stoppages left out)', 'ar': ' (دون فترات توقف اللعب)'} if ecartees else {'fr': '', 'en': '', 'ar': ''}
        e = round(100 * (b - a) / a)
        if abs(e) >= 3:
            fr = "En 2e mi-temps, l'équipe a couru %d %% de %s qu'en 1re%s." % (abs(e), 'moins' if e < 0 else 'plus', hors['fr'])
            en = 'In the second half, the team ran %d %% %s than in the first%s.' % (abs(e), 'less' if e < 0 else 'more', hors['en'])
            ar = 'في الشوط الثاني، ركض الفريق %s بنسبة %d٪ من الشوط الأول%s.' % ('أقل' if e < 0 else 'أكثر', abs(e), hors['ar'])
        else:
            fr = "L'équipe a couru autant dans les deux mi-temps%s." % hors['fr']
            en = 'The team ran as much in both halves%s.' % hors['en']
            ar = 'ركض الفريق بالقدر نفسه في الشوطين%s.' % hors['ar']
        C.append(phrase('style', ['m-intensite'], 1.8, fr, en, ar))
    return choisit(C, n=3, unique=False)
MIN_PHYS = 90
PHYS_MESURES = [('d', lambda s: s['d'] * 90.0 / s['min'], ('la distance parcourue', 'distance covered', 'المسافة المقطوعة'), lambda v, l: {'fr': '%s km sur 90 minutes', 'en': '%s km per 90 minutes', 'ar': '%s كم لكل 90 دقيقة'}[l] % nombre(v / 1000.0, 1, l)), ('hi', lambda s: (s['hsr2'] + s['spr']) * 90.0 / s['min'], ('les courses rapides', 'high-speed running', 'الجري السريع'), lambda v, l: {'fr': '%d m à plus de 19,8 km/h sur 90 minutes', 'en': '%d m above 19.8 km/h per 90 minutes', 'ar': '%d م بسرعة تفوق 19.8 كم/س لكل 90 دقيقة'}[l] % round(v)), ('nspr', lambda s: s['nspr'] * 90.0 / s['min'], ('les sprints', 'sprints', 'الانطلاقات'), lambda v, l: {'fr': '%s sprints sur 90 minutes', 'en': '%s sprints per 90 minutes', 'ar': '%s انطلاقة لكل 90 دقيقة'}[l] % nombre(v, 1, l)), ('acc', lambda s: s['acc'] * 90.0 / s['min_of'] if s.get('min_of') else None, ('les accélérations', 'accelerations', 'التسارعات'), lambda v, l: {'fr': '%d accélérations sur 90 minutes', 'en': '%d accelerations per 90 minutes', 'ar': '%d تسارعًا لكل 90 دقيقة'}[l] % round(v)), ('dec', lambda s: s['dec'] * 90.0 / s['min_of'] if s.get('min_of') else None, ('les freinages', 'decelerations', 'التباطؤات'), lambda v, l: {'fr': '%d freinages sur 90 minutes', 'en': '%d decelerations per 90 minutes', 'ar': '%d تباطؤًا لكل 90 دقيقة'}[l] % round(v)), ('vmax', lambda s: s['vmax'], ('la vitesse de pointe', 'top speed', 'السرعة القصوى'), lambda v, l: '%s km/h' % nombre(v, 1, l) if l != 'ar' else '%s كم/س' % nombre(v, 1, l))]
PHYS_RANGS = {'1': ('1er', '1st', 'الأول'), '2': ('2e', '2nd', 'الثاني'), '-2': ('Avant-dernier', 'Second to last', 'قبل الأخير'), '-1': ('Dernier', 'Last', 'الأخير')}

def physique_joueur(n, saisons, lignes):
    moi = saisons.get(str(n))
    if not moi:
        return []
    G = {k: s for k, s in saisons.items() if s['min'] >= MIN_PHYS}
    C = []
    for cle, valeur_de, quoi, ecrit in PHYS_MESURES:
        V = {k: valeur_de(s) for k, s in G.items()}
        V = {k: v for k, v in V.items() if v is not None}
        if str(n) not in V or len(V) < 5:
            continue
        v = V[str(n)]
        r, tot = (rang(list(V.values()), v), len(V))
        sc = score_rang(r, tot)
        if not sc:
            continue
        place = '1' if r == 1 else '2' if r == 2 else '-1' if r == tot else '-2'
        rg = PHYS_RANGS[place]
        if cle == 'vmax' and r == 1:
            fr, en, ar = ("Le plus rapide de l'équipe : %s." % ecrit(v, 'fr'), 'The fastest in the team: %s.' % ecrit(v, 'en'), 'الأسرع في الفريق: %s.' % ecrit(v, 'ar'))
        else:
            fr = "%s de l'équipe pour %s : %s." % (rg[0], quoi[0], ecrit(v, 'fr'))
            en = '%s in the team for %s: %s.' % (rg[1], quoi[1], ecrit(v, 'en'))
            ar = '%s في الفريق في %s: %s.' % (rg[2], quoi[2], ecrit(v, 'ar'))
        p = phrase('style', ['j-phys-graphes'], sc, fr, en, ar)
        p['m'] = cle
        C.append(p)
    R = [x['tot']['ri'] for x in lignes if 'tot' in x and 'ri' in x['tot']]
    if len(R) >= 2 and (all((r < 0 for r in R)) or all((r > 0 for r in R))):
        m = sum(R) / len(R)
        if abs(m) >= 2:
            g = m < 0
            C.append(phrase('style', ['j-phys-equilibre'], 1.7, "En courant, la jambe %s travaille plus que l'autre : %s %% d'écart en moyenne, à chacun des %d matchs." % ('gauche' if g else 'droite', nombre(abs(m), 1, 'fr'), len(R)), 'When running, the %s leg works harder than the other: a %s %% gap on average, in each of the %d matches.' % ('left' if g else 'right', nombre(abs(m), 1, 'en'), len(R)), 'أثناء الجري، تعمل الساق %s أكثر من الأخرى: فارق %s٪ في المتوسط، في كل مباراة من المباريات الـ%d.' % ('اليسرى' if g else 'اليمنى', nombre(abs(m), 1, 'ar'), len(R))))
    return choisit(C, n=3, unique=False)
