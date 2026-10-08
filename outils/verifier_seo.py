"""Contrôle le référencement des pages construites (sans réseau, sur les fichiers).

    python outils/verifier_seo.py

Pour chaque page : titre et description (longueur), une seule balise h1, canonique,
hreflang réciproques, JSON-LD lisible, aucune marque {{...}} oubliée, aucune image sans
alt, la langue courante marquée. Puis le plan du site (XML valide, trois adresses).
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://marmastats.com"
PAGES = {"en": "/", "fr": "/fr/", "ar": "/ar/"}
erreurs = []


def verifier(cond, msg):
    if not cond:
        erreurs.append(msg)


for lang, chemin in PAGES.items():
    f = os.path.join(RACINE, chemin.strip("/"), "index.html")
    s = open(f, encoding="utf-8").read()
    nom = chemin
    titre = re.search(r"<title>(.*?)</title>", s, re.S).group(1)
    desc = re.search(r'<meta name="description" content="([^"]*)"', s).group(1)
    verifier(30 <= len(titre) <= 60, f"{nom} titre de {len(titre)} caractères")
    verifier(70 <= len(desc) <= 160, f"{nom} description de {len(desc)} caractères")
    verifier(len(re.findall(r"<h1[\s>]", s)) == 1, f"{nom} : il faut un seul h1")
    verifier(f'<html lang="{lang}"' in s, f"{nom} : attribut lang")
    verifier(f'<link rel="canonical" href="{SITE + chemin}">' in s, f"{nom} : canonique")
    for autre, c in PAGES.items():
        verifier(f'<link rel="alternate" hreflang="{autre}" href="{SITE + c}">' in s, f"{nom} : hreflang {autre}")
    verifier(f'<link rel="alternate" hreflang="x-default" href="{SITE}/">' in s, f"{nom} : x-default")
    verifier("{{" not in s, f"{nom} : marque {{...}} oubliée")
    verifier(f'href="{chemin}" hreflang="{lang}" aria-current="page"' in s, f"{nom} : langue courante")
    for img in re.findall(r"<img\b[^>]*>", s):
        verifier(" alt=" in img, f"{nom} : image sans alt : {img[:80]}")
    blocs = re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
    verifier(len(blocs) == 1, f"{nom} : un bloc JSON-LD attendu")
    for b in blocs:
        try:
            d = json.loads(b)
            types = [n["@type"] for n in d["@graph"]]
            verifier(types.count("FAQPage") == 1 and "Organization" in types, f"{nom} : JSON-LD incomplet {types}")
            faq = next(n for n in d["@graph"] if n["@type"] == "FAQPage")
            for q in faq["mainEntity"]:
                verifier(q["name"] in s and q["acceptedAnswer"]["text"].replace("'", "&#x27;") in s or q["acceptedAnswer"]["text"] in s,
                         f"{nom} : la réponse FAQ « {q['name'][:40]} » n'est pas visible sur la page")
        except (ValueError, KeyError, StopIteration) as e:
            erreurs.append(f"{nom} : JSON-LD illisible ({e})")
    og = re.search(r'<meta property="og:image" content="([^"]+)"', s).group(1)
    verifier(os.path.exists(os.path.join(RACINE, og.replace(SITE + "/", ""))), f"{nom} : image de partage absente")
    print(f"{nom:5s} titre {len(titre):2d} · description {len(desc):3d} · JSON-LD {len(blocs)} · images {len(re.findall(r'<img', s))}")

arbre = ET.parse(os.path.join(RACINE, "sitemap.xml"))
locs = [e.text for e in arbre.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
verifier(locs == [SITE + c for c in PAGES.values()], f"sitemap : {locs}")
robots = open(os.path.join(RACINE, "robots.txt"), encoding="utf-8").read()
verifier(f"Sitemap: {SITE}/sitemap.xml" in robots, "robots.txt sans sitemap")
print("sitemap", len(locs), "adresses")

if erreurs:
    print("\n".join("ERREUR " + e for e in erreurs))
    sys.exit(1)
print("tout est bon")
