"""Construit les trois pages du site (/, /fr/, /ar/) et le plan du site.

    python outils/construire_pages.py

Source : outils/page.html (le gabarit) + i18n.js (les textes des trois langues).
Sorties : index.html, fr/index.html, ar/index.html, sitemap.xml. Ne jamais les éditer
à la main : modifier le gabarit ou i18n.js, puis relancer.

Chaque page reçoit ses textes en dur (Google lit le HTML, pas le JavaScript), son titre,
sa description, son adresse canonique, les liens hreflang vers les deux autres langues,
les balises de partage (Open Graph) et les données structurées (JSON-LD).
"""
import datetime
import html
import json
import os
import re

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://marmastats.com"
PAGES = {"en": "/", "fr": "/fr/", "ar": "/ar/"}
OG_LOCALE = {"en": "en_US", "fr": "fr_FR", "ar": "ar_AR"}
FAQ = 5
NOM_PLATEFORME = {"en": "Marmastats platform", "fr": "Plateforme Marmastats", "ar": "منصّة Marmastats"}

# La page racine envoie un visiteur francophone ou arabophone vers sa page, avant d'afficher
# l'anglais. Un choix fait au clic (localStorage) passe avant la langue du navigateur.
# Google arrive sans choix et en anglais : il reste sur /, et suit les liens hreflang.
REDIRECTION = ('<script>(function(){try{var p=location.pathname;if(p!=="/"&&p!=="/index.html")return;'
               'var q=new URLSearchParams(location.search).get("lang");var s=null;'
               'try{s=localStorage.getItem("mm-lang")}catch(e){}'
               'var w=q||s||(navigator.language||"").slice(0,2);var u={fr:"/fr/",ar:"/ar/"}[w];'
               'if(u)location.replace(u+location.hash)}catch(e){}})();</script>')


def lire_i18n():
    src = open(os.path.join(RACINE, "i18n.js"), encoding="utf-8").read()
    corps = src[src.index("window.I18N = ") + len("window.I18N = "):].rstrip().rstrip(";")
    corps = re.sub(r"^(\s*)(en|fr|ar): \{", r'\1"\2": {', corps, flags=re.M)
    return json.loads(corps)


def attr(v):
    return html.escape(v, quote=True)


def donnees_structurees(T, lang, url):
    org = SITE + "/#org"
    graphe = [
        {"@type": "Organization", "@id": org, "name": "Marmastats", "url": SITE + "/",
         "logo": {"@type": "ImageObject", "url": SITE + "/assets/brand/icone-512.png", "width": 512, "height": 512},
         "email": "haris.garrigos@marmastats.com",
         "address": {"@type": "PostalAddress", "addressLocality": "Lyon", "addressCountry": "FR"},
         "founder": {"@type": "Person", "name": "Haris Garrigos",
                     "sameAs": ["https://www.linkedin.com/in/haris-garrigos-926b05151/"]}},
        {"@type": "WebSite", "@id": SITE + "/#site", "url": SITE + "/", "name": "Marmastats",
         "publisher": {"@id": org}, "inLanguage": ["en", "fr", "ar"]},
        {"@type": "WebPage", "@id": url + "#page", "url": url, "name": T["seo.title"],
         "description": T["seo.desc"], "inLanguage": lang, "isPartOf": {"@id": SITE + "/#site"},
         "about": {"@id": org}, "primaryImageOfPage": SITE + f"/assets/og/og-{lang}.png"},
        {"@type": "SoftwareApplication", "name": "Kora", "applicationCategory": "SportsApplication",
         "operatingSystem": "Web", "description": T["v.sub"], "inLanguage": ["en", "fr", "ar"],
         "publisher": {"@id": org}},
        {"@type": "SoftwareApplication", "name": NOM_PLATEFORME[lang],
         "applicationCategory": "SportsApplication", "operatingSystem": "Web", "description": T["d.sub"],
         "inLanguage": ["en", "fr", "ar"], "publisher": {"@id": org}},
        {"@type": "FAQPage", "@id": url + "#faq", "inLanguage": lang, "mainEntity": [
            {"@type": "Question", "name": T[f"faq.q{i}"],
             "acceptedAnswer": {"@type": "Answer", "text": T[f"faq.a{i}"]}} for i in range(1, FAQ + 1)]},
    ]
    texte = json.dumps({"@context": "https://schema.org", "@graph": graphe}, ensure_ascii=False, indent=1)
    return texte.replace("<", "\\u003c")


def tete(T, lang):
    url = SITE + PAGES[lang]
    titre, desc = T["seo.title"], T["seo.desc"]
    image = SITE + f"/assets/og/og-{lang}.png"
    l = [f"<title>{html.escape(titre)}</title>",
         f'<meta name="description" content="{attr(desc)}">',
         '<meta name="robots" content="index, follow, max-image-preview:large">',
         f'<link rel="canonical" href="{url}">']
    for autre, chemin in PAGES.items():
        l.append(f'<link rel="alternate" hreflang="{autre}" href="{SITE + chemin}">')
    l.append(f'<link rel="alternate" hreflang="x-default" href="{SITE}/">')
    l += ['<meta property="og:type" content="website">',
          '<meta property="og:site_name" content="Marmastats">',
          f'<meta property="og:url" content="{url}">',
          f'<meta property="og:title" content="{attr(titre)}">',
          f'<meta property="og:description" content="{attr(desc)}">',
          f'<meta property="og:image" content="{image}">',
          '<meta property="og:image:width" content="1200">',
          '<meta property="og:image:height" content="630">',
          f'<meta property="og:image:alt" content="{attr(T["og.alt"])}">',
          f'<meta property="og:locale" content="{OG_LOCALE[lang]}">']
    for autre in PAGES:
        if autre != lang:
            l.append(f'<meta property="og:locale:alternate" content="{OG_LOCALE[autre]}">')
    l += ['<meta name="twitter:card" content="summary_large_image">',
          f'<meta name="twitter:title" content="{attr(titre)}">',
          f'<meta name="twitter:description" content="{attr(desc)}">',
          f'<meta name="twitter:image" content="{image}">',
          f'<meta name="twitter:image:alt" content="{attr(T["og.alt"])}">',
          '<script type="application/ld+json">\n' + donnees_structurees(T, lang, url) + "\n</script>"]
    if lang == "en":
        l.append(REDIRECTION)
    return "\n".join(l)


def page(gabarit, T, lang):
    utilisees = set()

    def cle(k):
        if k not in T:
            raise SystemExit(f"clé absente de i18n.js ({lang}) : {k}")
        utilisees.add(k)
        return T[k]

    motif = r'<(?P<tag>[a-zA-Z0-9]+)(?P<attrs>[^>]*?\sdata-i18n{suffixe}="(?P<key>[^"]+)"[^>]*)>(?P<inner>.*?)</(?P=tag)>'
    s = re.sub(motif.format(suffixe=""), lambda m: f'<{m["tag"]}{m["attrs"]}>{html.escape(cle(m["key"]), quote=False)}</{m["tag"]}>',
               gabarit, flags=re.S)
    s = re.sub(motif.format(suffixe="-html"), lambda m: f'<{m["tag"]}{m["attrs"]}>{cle(m["key"])}</{m["tag"]}>', s, flags=re.S)

    def attribut(nom_data, nom_attr):
        def remplacer(m):
            balise = m.group(0)
            k = re.search(nom_data + r'="([^"]+)"', balise).group(1)
            return re.sub(nom_attr + r'="[^"]*"', f'{nom_attr}="{attr(cle(k))}"', balise)
        return remplacer

    s = re.sub(r'<[^>]*\sdata-i18n-alt="[^"]+"[^>]*>', attribut("data-i18n-alt", "alt"), s)
    s = re.sub(r'<[^>]*\sdata-i18n-aria="[^"]+"[^>]*>', attribut("data-i18n-aria", "aria-label"), s)

    s = s.replace('<html lang="en" dir="ltr">', f'<html lang="{lang}" dir="{"rtl" if lang == "ar" else "ltr"}">')
    s = s.replace("<!--SEO-->", tete(T, lang))
    s = s.replace("{{L}}", lang).replace("{{HOME}}", PAGES[lang]).replace("{{DEMO_LANG}}", f"?lang={lang}")
    courant = f'<a href="{PAGES[lang]}" hreflang="{lang}"'
    assert s.count(courant) == 1, courant
    s = s.replace(courant, courant + ' aria-current="page"')
    reste = re.findall(r"\{\{[A-Z_]+\}\}", s)
    if reste:
        raise SystemExit(f"marques non remplacées : {reste}")
    return s, utilisees


def plan_du_site():
    jour = datetime.date.today().isoformat()
    l = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for chemin in PAGES.values():
        l.append(f"  <url>\n    <loc>{SITE + chemin}</loc>\n    <lastmod>{jour}</lastmod>")
        for autre, c in PAGES.items():
            l.append(f'    <xhtml:link rel="alternate" hreflang="{autre}" href="{SITE + c}"/>')
        l.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE}/"/>\n  </url>')
    l.append("</urlset>")
    return "\n".join(l) + "\n"


def main():
    I = lire_i18n()
    gabarit = open(os.path.join(RACINE, "outils", "page.html"), encoding="utf-8").read()
    for lang, chemin in PAGES.items():
        s, utilisees = page(gabarit, I[lang], lang)
        dossier = os.path.join(RACINE, chemin.strip("/"))
        os.makedirs(dossier, exist_ok=True)
        with open(os.path.join(dossier, "index.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
        print(f"{chemin:5s} {len(s):7d} octets · {len(utilisees)} textes")
    with open(os.path.join(RACINE, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write(plan_du_site())
    print("sitemap.xml")


if __name__ == "__main__":
    main()
