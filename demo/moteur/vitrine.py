import os, re, json, glob, shutil, sqlite3, collections, datetime, zipfile
import xml.etree.ElementTree as ET
import charge_instat, publie, radar, libelles
MOTIF_EQUIPE = re.compile('^(.*?)\\s+\\((\\d+)\\)\\s+-\\s+(.*)$')
MOTIF_JOUEUR = re.compile('^(\\d+)\\.\\s+(.*?)\\s+\\((\\d+)\\)\\s+-\\s+(.*)$')
SURFACE = 16.5

def _alerte(code, **k):
    return dict(code=code, **k)

def deballe(dossier):
    for k, z in enumerate(sorted(glob.glob(os.path.join(dossier, '*.zip')))):
        sous = os.path.join(dossier, '_zip%d' % k)
        try:
            with zipfile.ZipFile(z) as f:
                for n in f.namelist():
                    if n.lower().endswith('.xml') and '__MACOSX' not in n:
                        os.makedirs(sous, exist_ok=True)
                        with open(os.path.join(sous, os.path.basename(n)), 'wb') as o:
                            o.write(f.read(n))
        except zipfile.BadZipFile:
            pass

def lit_fichier(chemin):
    r = ET.parse(chemin).getroot()
    equipes, eq_joueurs, buts, tags = ([], collections.Counter(), collections.defaultdict(set), set())
    joueurs = set()
    for i in r.findall('.//instance'):
        code = i.findtext('code') or ''
        lab = {l.findtext('group'): l.findtext('text') for l in i.findall('label')}
        mj = MOTIF_JOUEUR.match(code)
        if mj:
            joueurs.add(int(mj.group(3)))
            eq = (lab.get('Team') or '').split(' (')[0]
            if eq and eq != 'None':
                eq_joueurs[eq] += 1
            tags.add(mj.group(4).strip())
            continue
        me = MOTIF_EQUIPE.match(code)
        if me:
            eq = me.group(1)
            if eq not in equipes:
                equipes.append(eq)
            tag = libelles.canon(me.group(3).strip())
            tags.add(tag)
            if tag == 'Buts':
                buts[eq].add((lab.get('Half'), i.findtext('start')))
    ordre = {}
    for row in r.findall('.//ROWS/row'):
        me = re.match('^(.*?)\\s+\\((\\d+)\\)$', row.findtext('code') or '')
        if me and (not re.match('^\\d+\\.\\s', row.findtext('code') or '')):
            try:
                ordre[me.group(1)] = int(row.findtext('sort_order') or 0)
            except ValueError:
                pass
    equipes.sort(key=lambda e: ordre.get(e, 99))
    gardien = bool(joueurs) and len(joueurs) == 1 and bool(tags & libelles.GARDIEN_SEUL)
    niveau = 'joueur' if joueurs else 'equipe' if len(equipes) >= 2 else 'une' if equipes else None
    return dict(niveau=niveau, equipes=equipes, buts={e: len(buts[e]) for e in equipes}, equipe_joueurs=eq_joueurs.most_common(1)[0][0] if eq_joueurs else None, gardien=gardien, n_joueurs=len(joueurs), tags=tags)

def inventaire(dossier):
    deballe(dossier)
    alertes, lus = ([], [])
    for f in sorted(glob.glob(os.path.join(dossier, '**', '*.xml'), recursive=True)):
        nom = os.path.basename(f)
        try:
            d = lit_fichier(f)
        except ET.ParseError:
            alertes.append(_alerte('illisible', fichier=nom))
            continue
        if not d['niveau']:
            alertes.append(_alerte('pas_instat', fichier=nom))
            continue
        d['chemin'], d['fichier'] = (f, nom)
        d['info'] = charge_instat.infos_match(nom)
        lus.append(d)
    matchs = collections.OrderedDict()
    for d in lus:
        if d['info']:
            m = matchs.setdefault(d['info'][0], dict(info=d['info'], fichiers=[]))
            m['fichiers'].append(d)
    for d in lus:
        if d['info'] or d['niveau'] != 'equipe':
            continue
        dom, ext = d['equipes'][:2]
        cle = next((k for k, m in matchs.items() if (m['info'][2], m['info'][3]) == (dom, ext)), None)
        if cle is None:
            date = datetime.date.today().isoformat()
            info = ('%s_%s_%s' % (date, dom.replace(' ', ''), ext.replace(' ', '')), date, dom, ext, d['buts'].get(dom, 0), d['buts'].get(ext, 0))
            cle = info[0]
            matchs[cle] = dict(info=info, fichiers=[], date_inconnue=True)
            alertes.append(_alerte('date_inconnue', fichier=d['fichier']))
        matchs[cle]['fichiers'].append(d)
    for d in lus:
        if d['info'] or d['niveau'] == 'equipe':
            continue
        eq = d['equipe_joueurs'] or (d['equipes'][0] if d['equipes'] else None)
        cands = [k for k, m in matchs.items() if eq in (m['info'][2], m['info'][3])]
        if len(cands) == 1:
            matchs[cands[0]]['fichiers'].append(d)
        else:
            alertes.append(_alerte('sans_match', fichier=d['fichier']))
    sortie, equipes = ([], collections.Counter())
    for cle, m in matchs.items():
        mid, date, dom, ext, sd, se = m['info']
        niv = [f['niveau'] for f in m['fichiers']]
        if 'equipe' not in niv:
            alertes.append(_alerte('sans_fichier_equipe', match='%s %d-%d %s' % (dom, sd, se, ext)))
        eqj = [f['equipe_joueurs'] for f in m['fichiers'] if f['niveau'] == 'joueur' and f['equipe_joueurs']]
        for e in set(eqj):
            equipes[e] += 1
        sortie.append(dict(cle=cle, date=date, domicile=dom, exterieur=ext, score=[sd, se], date_inconnue=bool(m.get('date_inconnue')), analysable='equipe' in niv, equipe_joueurs=eqj[0] if eqj else None, fichiers=[dict(nom=f['fichier'], niveau=f['niveau'], gardien=f['gardien']) for f in m['fichiers']]))
    proposee = equipes.most_common(1)[0][0] if equipes else None
    toutes = []
    for m in sortie:
        for e in (m['domicile'], m['exterieur']):
            if e not in toutes:
                toutes.append(e)
    return (dict(matchs=sortie, equipes=toutes, proposee=proposee, alertes=alertes), matchs)

def _prepare(matchs, travail):
    dossiers = []
    for i, (cle, m) in enumerate(matchs.items()):
        mid, date, dom, ext, sd, se = m['info']
        d = os.path.join(travail, 'm%02d' % i)
        os.makedirs(d, exist_ok=True)
        a, mo, j = date.split('-')
        for k, f in enumerate(m['fichiers']):
            nom = f['fichier'] if f['info'] else '%s %d-%d %s %s.%s.%s, fichier %d.xml' % (dom, sd, se, ext, j, mo, a, k + 1)
            shutil.copyfile(f['chemin'], os.path.join(d, nom))
        dossiers.append((d, m))
    return dossiers

def gardiens(cx, equipe, dossiers):
    noms = set()
    for d, m in dossiers:
        for f in m['fichiers']:
            if f['gardien']:
                r = ET.parse(f['chemin']).getroot()
                for i in r.findall('.//instance'):
                    mj = MOTIF_JOUEUR.match(i.findtext('code') or '')
                    if mj:
                        noms.add(mj.group(2))
                        break
    xs = collections.defaultdict(list)
    for nom, x in cx.execute("SELECT a.joueur, a.x FROM action a WHERE a.niveau='joueur' AND a.equipe=? AND a.x IS NOT NULL AND EXISTS (SELECT 1 FROM action_tag t WHERE t.action_id=a.action_id AND t.nature='action')", (equipe,)):
        xs[nom].append(x)
    for nom, L in xs.items():
        L.sort()
        if len(L) >= 5 and L[len(L) // 2] < SURFACE:
            noms.add(nom)
    return noms

def analyse(dossier, travail, equipe=None, postes=None, ligue_json=None):
    resume, matchs = inventaire(dossier)
    alertes = list(resume['alertes'])
    equipe = equipe or resume['proposee']
    if not equipe:
        raise ValueError('equipe')
    shutil.rmtree(travail, ignore_errors=True)
    os.makedirs(travail)
    utiles = collections.OrderedDict(((k, m) for k, m in matchs.items() if any((f['niveau'] == 'equipe' for f in m['fichiers'])) and equipe in (m['info'][2], m['info'][3])))
    for k, m in matchs.items():
        if k not in utiles and any((f['niveau'] == 'equipe' for f in m['fichiers'])):
            alertes.append(_alerte('equipe_absente', match='%s - %s' % (m['info'][2], m['info'][3])))
    for k, m in utiles.items():
        if not any((f['niveau'] == 'joueur' and (not f['gardien']) for f in m['fichiers'])):
            alertes.append(_alerte('sans_joueurs', match='%s - %s' % (m['info'][2], m['info'][3])))
    if not utiles:
        return ({}, alertes)
    dossiers = _prepare(utiles, os.path.join(travail, 'matchs'))
    base = os.path.join(travail, 'base.db')
    cx = sqlite3.connect(base)
    cx.executescript(charge_instat.SCHEMA)
    for d, _ in dossiers:
        charge_instat.charge_match(cx, d)
    cx.executescript(charge_instat.VUES)
    cx.commit()
    inconnues = libelles.inconnues({r[0] for r in cx.execute('SELECT DISTINCT tag FROM action_tag')})
    if inconnues:
        alertes.append(_alerte('etiquettes_inconnues', etiquettes=inconnues))
    gk = gardiens(cx, equipe, dossiers)
    cx.close()
    radar.POSTES = dict(postes or {})
    for n in gk:
        radar.POSTES.setdefault(n, radar.GARDIEN)
    publie.NOTRE_EQUIPE = radar.NOTRE_EQUIPE = equipe
    publie.BASE = base
    publie.DATA = os.path.join(travail, 'data')
    os.makedirs(publie.DATA)
    if ligue_json:
        with open(os.path.join(publie.DATA, 'ligue.json'), 'w', encoding='utf-8') as f:
            f.write(ligue_json)
    publie.main()
    nous = json.dumps(equipe, ensure_ascii=False)[1:-1]
    sortie = {}
    for f in sorted(os.listdir(publie.DATA)):
        if f.endswith('.json'):
            with open(os.path.join(publie.DATA, f), encoding='utf-8') as h:
                sortie[f] = h.read().replace('{NOUS_AR}', '\u2066' + nous + '\u2069').replace('{NOUS}', nous)
    return (sortie, alertes)

def analyse_json(dossier, travail, equipe=None):
    try:
        sortie, alertes = analyse(dossier, travail, equipe or None)
        return json.dumps(dict(ok=True, fichiers=sortie, alertes=alertes), ensure_ascii=False)
    except ValueError as e:
        return json.dumps(dict(ok=False, erreur=str(e)), ensure_ascii=False)

def inventaire_json(dossier):
    resume, _ = inventaire(dossier)
    return json.dumps(resume, ensure_ascii=False)
