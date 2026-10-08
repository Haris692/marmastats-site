import sqlite3, re, sys, glob, os, collections
import libelles
import xml.etree.ElementTree as ET
RACINE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(RACINE, 'base.db')
DOSSIERS = 'entree'
SCHEMA = "\nCREATE TABLE IF NOT EXISTS match (\n  match_id    TEXT PRIMARY KEY,\n  date        TEXT,\n  domicile    TEXT,\n  exterieur   TEXT,\n  score_dom   INTEGER,\n  score_ext   INTEGER\n);\nCREATE TABLE IF NOT EXISTS joueur (\n  joueur_id INTEGER PRIMARY KEY,\n  nom       TEXT,\n  equipe    TEXT\n);\nCREATE TABLE IF NOT EXISTS action (\n  action_id INTEGER PRIMARY KEY,\n  match_id  TEXT NOT NULL,\n  niveau    TEXT NOT NULL,\n  mi_temps  INTEGER,\n  t_s       REAL,\n  equipe    TEXT,\n  joueur_id INTEGER,\n  numero    INTEGER,\n  joueur    TEXT,\n  x REAL, y REAL\n);\nCREATE TABLE IF NOT EXISTS action_tag (\n  action_id INTEGER NOT NULL,\n  tag       TEXT NOT NULL,\n  nature    TEXT NOT NULL,\n  PRIMARY KEY (action_id, tag)\n);\n\n\n\nCREATE UNIQUE INDEX IF NOT EXISTS u_action ON action(\n  match_id, niveau, mi_temps, t_s, COALESCE(equipe,''), COALESCE(joueur_id,-1));\nCREATE INDEX IF NOT EXISTS i_action_match  ON action(match_id, equipe);\nCREATE INDEX IF NOT EXISTS i_action_joueur ON action(joueur_id);\nCREATE INDEX IF NOT EXISTS i_tag           ON action_tag(tag);\n"
VUES = "\nDROP VIEW IF EXISTS v_action;\nCREATE VIEW v_action AS\nSELECT a.action_id, a.match_id, m.date, a.niveau, a.mi_temps, a.t_s,\n       a.equipe, a.joueur_id, a.numero, a.joueur, a.x, a.y,\n\n\n       MAX(CASE WHEN t.tag LIKE 'Passes%' THEN 1 ELSE 0 END)                               AS est_passe,\n       MAX(CASE WHEN t.tag = 'Passes réussies' THEN 1 ELSE 0 END)                          AS reussie,\n       MAX(CASE WHEN t.tag LIKE 'Passes vers l''avant%' THEN 1 ELSE 0 END)                 AS vers_avant,\n       MAX(CASE WHEN t.tag LIKE 'Passes progressives%' THEN 1 ELSE 0 END)                  AS progressive,\n       MAX(CASE WHEN t.tag LIKE 'Passes clés%' THEN 1 ELSE 0 END)                          AS passe_cle,\n       MAX(CASE WHEN t.tag LIKE 'Passes longues%' THEN 1 ELSE 0 END)                       AS longue,\n       MAX(CASE WHEN t.tag LIKE 'Centres%' THEN 1 ELSE 0 END)                              AS centre,\n\n\n       MAX(CASE WHEN t.tag IN ('Tirs','Tirs cadrés','Tirs hors cadre','Tirs contrés',\n                               'Tir sur le poteau / sur la barre') THEN 1 ELSE 0 END)      AS tir,\n       MAX(CASE WHEN t.tag = 'Tirs cadrés' THEN 1 ELSE 0 END)                              AS cadre,\n       MAX(CASE WHEN t.tag = 'Buts' THEN 1 ELSE 0 END)                                     AS but,\n       MAX(CASE WHEN t.tag = 'Tir sur le poteau / sur la barre' THEN 1 ELSE 0 END)         AS poteau,\n       MAX(CASE WHEN t.tag = 'Tirs contrés' THEN 1 ELSE 0 END)                             AS contre,\n       MAX(CASE WHEN t.tag LIKE 'Dribbles%' THEN 1 ELSE 0 END)                             AS dribble,\n\n\n       MAX(CASE WHEN t.tag LIKE 'Duels%' THEN 1 ELSE 0 END)                                AS duel,\n       MAX(CASE WHEN t.tag IN ('Duels gangés','Duels aériens gagnés') THEN 1 ELSE 0 END)   AS duel_gagne,\n       MAX(CASE WHEN t.tag LIKE 'Récupérations%' THEN 1 ELSE 0 END)                        AS recuperation,\n       MAX(CASE WHEN t.tag LIKE 'Pertes%' THEN 1 ELSE 0 END)                               AS perte\nFROM action a\nJOIN match m USING (match_id)\nJOIN action_tag t USING (action_id)\nWHERE t.nature = 'action'\nGROUP BY a.action_id;\n\nDROP VIEW IF EXISTS v_passe;\nCREATE VIEW v_passe AS SELECT * FROM v_action WHERE est_passe = 1;\n"
SEQUENCE = {'Attaques placées', 'Attaques placées avec des tirs', 'Contre attaques', 'Attaques sur corner', 'Attaques sur coup franc', 'Attaques sur touche'}

def nature(tag):
    if tag.startswith('Participation') or tag.startswith('Jeu en attaques'):
        return 'participation'
    if tag in SEQUENCE:
        return 'sequence'
    if tag in libelles.EVENEMENTS_SUBIS:
        return 'gardien'
    return 'action'

def infos_match(nom_fichier):
    m = re.match('^(.+?)\\s+(\\d+)-(\\d+)\\s+(.+?)\\s+(\\d{2})\\.(\\d{2})\\.(\\d{4})', nom_fichier)
    if not m:
        return None
    dom, sd, se, ext, j, mo, a = m.groups()
    date = '%s-%s-%s' % (a, mo, j)
    return ('%s_%s_%s' % (date, dom.replace(' ', ''), ext.replace(' ', '')), date, dom.strip(), ext.strip(), int(sd), int(se))

def lit(fichier, gardien=False):
    r = ET.parse(fichier).getroot()
    out = []
    canonique = libelles.canon_gardien if gardien else libelles.canon
    for i in r.findall('.//instance'):
        code = i.find('code').text or ''
        lab = {l.find('group').text: l.find('text').text for l in i.findall('label')}
        mj = re.match('^(\\d+)\\.\\s+(.*?)\\s+\\((\\d+)\\)\\s+-\\s+(.*)$', code)
        me = re.match('^(.*?)\\s+\\((\\d+)\\)\\s+-\\s+(.*)$', code)
        if mj:
            num, nom, jid, tag = (int(mj.group(1)), mj.group(2), int(mj.group(3)), mj.group(4))
            eq = (lab.get('Team') or '').split(' (')[0] or None
        elif me:
            num = nom = jid = None
            eq, tag = (me.group(1), me.group(3))
        else:
            continue

        def f(v):
            return None if v in (None, 'None', '') else float(v)
        tg, x, y = (canonique(tag), f(lab.get('pos_x')), f(lab.get('pos_y')))
        if gardien and tg in libelles.EVENEMENTS_SUBIS and (x is not None) and (y is not None):
            x, y = (round(105.0 - x, 2), round(68.0 - y, 2))
        out.append((int(lab.get('Half', 0)), round(float(i.find('start').text), 2), eq, jid, num, nom, x, y, tg))
    return out

def joueurs_du_fichier(fichier):
    r = ET.parse(fichier).getroot()
    out = set()
    for i in r.findall('.//instance'):
        m = re.match('^\\d+\\.\\s+.*?\\s+\\((\\d+)\\)\\s+-\\s+', i.find('code').text or '')
        if m:
            out.add(int(m.group(1)))
    return out

def est_fichier_gardien(fichier):
    r = ET.parse(fichier).getroot()
    tags = set()
    for i in r.findall('.//instance'):
        code = i.find('code').text or ''
        if re.match('^\\d+\\.\\s', code) and ' - ' in code:
            tags.add(code.split(' - ', 1)[1].strip())
    return len(joueurs_du_fichier(fichier)) == 1 and bool(tags & libelles.GARDIEN_SEUL)

def niveau_du_fichier(fichier):
    r = ET.parse(fichier).getroot()
    for i in r.findall('.//instance')[:400]:
        if re.match('^\\d+\\.\\s', i.find('code').text or ''):
            return 'joueur'
    return 'equipe'

def charge_match(cx, dossier):
    fichiers = [f for f in sorted(glob.glob(os.path.join(dossier, '*.xml'))) if infos_match(os.path.basename(f))]
    if not fichiers:
        print('  ! %s : aucun nom de fichier lisible' % os.path.basename(dossier))
        return
    par_niveau, joueurs = ({}, [])
    for f in sorted(fichiers, key=os.path.getsize, reverse=True):
        n = niveau_du_fichier(f)
        if n == 'equipe':
            par_niveau.setdefault('equipe', f)
            continue
        ids = joueurs_du_fichier(f)
        if all((not ids & deja for _, deja, _ in joueurs)):
            joueurs.append((f, ids, est_fichier_gardien(f)))
    if 'equipe' not in par_niveau:
        print('  ! %s : pas de fichier au niveau equipe' % os.path.basename(dossier))
        return
    inf = infos_match(os.path.basename(par_niveau['equipe']))
    mid, date, dom, ext, sd, se = inf
    cx.execute('INSERT OR REPLACE INTO match VALUES (?,?,?,?,?,?)', inf)
    actions = collections.OrderedDict()
    sources = [('equipe', par_niveau['equipe'], False)] + [('joueur', f, g) for f, _, g in joueurs]
    for niveau, fichier, gardien in sources:
        for h, t, eq, jid, num, nom, x, y, tag in lit(fichier, gardien):
            cle = (niveau, h, t, eq, jid)
            a = actions.setdefault(cle, dict(num=num, nom=nom, x=x, y=y, tags=set()))
            a['tags'].add(tag)
            if a['x'] is None:
                a['x'], a['y'] = (x, y)
            if jid and nom:
                cx.execute('INSERT OR IGNORE INTO joueur VALUES (?,?,?)', (jid, nom, eq))
    n_act = n_tag = 0
    for (niveau, h, t, eq, jid), a in actions.items():
        cur = cx.execute('INSERT OR IGNORE INTO action (match_id,niveau,mi_temps,t_s,equipe,joueur_id,numero,joueur,x,y) VALUES (?,?,?,?,?,?,?,?,?,?)', (mid, niveau, h, t, eq, jid, a['num'], a['nom'], a['x'], a['y']))
        aid = cur.lastrowid
        if not cur.rowcount:
            aid = cx.execute('SELECT action_id FROM action WHERE match_id=? AND niveau=? AND mi_temps=? AND t_s=? AND equipe IS ? AND joueur_id IS ?', (mid, niveau, h, t, eq, jid)).fetchone()[0]
        else:
            n_act += 1
        subi = bool(a['tags'] & libelles.EVENEMENTS_SUBIS)
        for tg in a['tags']:
            cx.execute('INSERT OR IGNORE INTO action_tag VALUES (?,?,?)', (aid, tg, 'gardien' if subi else nature(tg)))
            n_tag += 1
    manque = '' if joueurs else '   ! pas de donnees par joueur'
    gk = [f for f, _, g in joueurs if g]
    print('  %-34s %s  %d actions, %d etiquettes%s%s' % (mid, '%d-%d' % (sd, se), n_act, n_tag, manque, '   + gardien' if gk else ''))
