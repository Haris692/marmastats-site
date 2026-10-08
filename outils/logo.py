"""Mot « marmastats » vectorisé (Archivo variable, crénage HarfBuzz) + symbole « M en schéma de passes ».

    python logo.py <Archivo.ttf> apercu <sortie.html>        planche de variantes
    python logo.py <Archivo.ttf> fichiers <dossier> <wdth> <wght>   fichiers SVG de la charte
"""
import io
import os
import sys

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

NUIT = "#0B1513"
CRAIE = "#F4F2EA"
BALLON = "#FFC93C"


def mot(chemin, texte, wdth, wght, suivi=0):
    """Chemin SVG du texte (unités de la police, y vers le bas, ligne de base à 0) et sa chasse."""
    with open(chemin, "rb") as f:
        donnees = f.read()
    face = hb.Face(donnees)
    police = hb.Font(face)
    police.set_variations({"wdth": wdth, "wght": wght})
    tampon = hb.Buffer()
    tampon.add_str(texte)
    tampon.guess_segment_properties()
    hb.shape(police, tampon, {"kern": True, "liga": False})
    tt = TTFont(io.BytesIO(donnees))
    statique = instancer.instantiateVariableFont(tt, {"wdth": wdth, "wght": wght})
    glyphes = statique.getGlyphSet()
    ordre = statique.getGlyphOrder()
    pen = SVGPathPen(glyphes)
    x = 0
    for info, pos in zip(tampon.glyph_infos, tampon.glyph_positions):
        nom = ordre[info.codepoint]
        tp = TransformPen(pen, (1, 0, 0, -1, x + pos.x_offset, -pos.y_offset))
        glyphes[nom].draw(tp)
        x += pos.x_advance + suivi
    x -= suivi
    bp = BoundsPen(glyphes)
    xh = statique["OS/2"].sxHeight
    return pen.getCommands(), x, xh, statique["head"].unitsPerEm


def symbole(lignes, ballon, anneau, epaisseur=3.0):
    """M dessiné comme un schéma de passes : quatre joueurs, le ballon au centre (grille 32)."""
    return (
        f'<path d="M6.5 25V7.5l9.5 10.5 9.5-10.5V25" fill="none" stroke="{lignes}" stroke-width="{epaisseur}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'<g fill="{lignes}"><circle cx="6.5" cy="25" r="3.15"/><circle cx="6.5" cy="7.5" r="3.15"/>'
        f'<circle cx="25.5" cy="7.5" r="3.15"/><circle cx="25.5" cy="25" r="3.15"/></g>'
        f'<circle cx="16" cy="18" r="3.9" fill="{ballon}" stroke="{anneau}" stroke-width="1.8"/>'
    )


def verrouillage(chemin_police, wdth, wght, couleur, fond_anneau, suivi=0):
    """Symbole + mot, sur une grille où le symbole fait 32 de haut. Renvoie (svg intérieur, largeur, hauteur)."""
    d, chasse, xh, upm = mot(chemin_police, "marmastats", wdth, wght, suivi)
    # le x-height du mot = 0.56 du symbole (de l'axe des joueurs du haut à celui du bas : 17.5)
    echelle = 15.2 / xh
    gauche = 32 + 9
    base = 25 + 2.9 * 0.0 + 0.6
    largeur = gauche + chasse * echelle + 1
    g = (f'<g transform="translate({gauche:.2f} {base:.2f}) scale({echelle:.5f})">'
         f'<path d="{d}" fill="{couleur}"/></g>')
    return symbole(couleur, BALLON, fond_anneau) + g, largeur, 32


def apercu(chemin_police, sortie):
    variantes = [(100, 700, 0), (112, 700, 0), (125, 700, 0), (112, 800, 0), (125, 800, -6), (112, 600, 0)]
    lignes = []
    for wdth, wght, suivi in variantes:
        for fond, coul in ((CRAIE, NUIT), (NUIT, CRAIE)):
            inner, w, h = verrouillage(chemin_police, wdth, wght, coul, fond, suivi)
            lignes.append(
                f'<div style="background:{fond};padding:28px 36px;display:flex;align-items:center;gap:20px">'
                f'<svg viewBox="-2 -2 {w + 4:.1f} {h + 4}" height="72">{inner}</svg>'
                f'<code style="color:{coul};font:12px monospace;opacity:.6">wdth {wdth} · wght {wght} · suivi {suivi}</code></div>')
    icones = []
    for taille in (128, 48, 32, 16):
        icones.append(
            f'<svg viewBox="0 0 32 32" width="{taille}" height="{taille}"><rect width="32" height="32" rx="7.5" fill="{NUIT}"/>'
            f'<g transform="translate(3.2 3.2) scale(.8)">{symbole(CRAIE, BALLON, NUIT, 2.6)}</g></svg>')
    html = ('<!doctype html><meta charset="utf-8"><body style="margin:0;font-family:sans-serif">'
            + "".join(lignes)
            + f'<div style="padding:24px;display:flex;gap:24px;align-items:end;background:#ddd">{"".join(icones)}</div>')
    with open(sortie, "w", encoding="utf-8") as f:
        f.write(html)


def fichiers(chemin_police, dossier, wdth, wght):
    os.makedirs(dossier, exist_ok=True)
    ecrits = []

    def ecrire(nom, contenu):
        with open(os.path.join(dossier, nom), "w", encoding="utf-8") as f:
            f.write(contenu)
        ecrits.append(nom)

    for nom, coul, fond in (("logo-nuit.svg", NUIT, CRAIE), ("logo-craie.svg", CRAIE, NUIT)):
        inner, w, h = verrouillage(chemin_police, wdth, wght, coul, fond)
        ecrire(nom, f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1 -1 {w + 2:.2f} {h + 2}" '
                    f'width="{(w + 2) * 8:.0f}" height="{(h + 2) * 8}">{inner}</svg>\n')
    ecrire("symbole-nuit.svg", f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="256" height="256">'
                               f'{symbole(NUIT, BALLON, CRAIE)}</svg>\n')
    ecrire("symbole-craie.svg", f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="256" height="256">'
                                f'{symbole(CRAIE, BALLON, NUIT)}</svg>\n')
    ecrire("icone.svg", f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="512" height="512">'
                        f'<rect width="32" height="32" rx="7.5" fill="{NUIT}"/>'
                        f'<g transform="translate(3.2 3.2) scale(.8)">{symbole(CRAIE, BALLON, NUIT, 2.6)}</g></svg>\n')
    d, chasse, xh, upm = mot(chemin_police, "marmastats", wdth, wght)
    print("écrits :", ", ".join(ecrits))
    return d, chasse, xh


if __name__ == "__main__":
    police, mode = sys.argv[1], sys.argv[2]
    if mode == "apercu":
        apercu(police, sys.argv[3])
    else:
        fichiers(police, sys.argv[3], float(sys.argv[4]), float(sys.argv[5]))
