"""Images de partage (Open Graph, 1200 x 630) et icônes du site.

    python outils/images_partage.py

- assets/og/og-en.png, og-fr.png, og-ar.png : rendu de outils/og.html par Chrome sans fenêtre
  (il faut le réseau pour les polices Google) ;
- favicon.ico (16, 32, 48) et assets/brand/apple-touch-icon.png (180, fond plein) depuis
  assets/brand/icone-512.png.
"""
import os
import shutil
import subprocess
import tempfile

from PIL import Image

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def og(lang):
    sortie = os.path.join(RACINE, "assets", "og", f"og-{lang}.png")
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    url = "file:///" + os.path.join(RACINE, "outils", "og.html").replace("\\", "/") + f"?lang={lang}"
    profil = tempfile.mkdtemp(prefix="og-")
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--allow-file-access-from-files", "--window-size=1200,630", "--virtual-time-budget=8000",
                        "--user-data-dir=" + profil, "--screenshot=" + sortie, url],
                       capture_output=True, timeout=90)
    finally:
        shutil.rmtree(profil, ignore_errors=True)
    im = Image.open(sortie).convert("RGB")
    assert im.size == (1200, 630), im.size
    im.save(sortie, optimize=True)
    print(os.path.relpath(sortie, RACINE), os.path.getsize(sortie) // 1024, "Ko")


def icones():
    src = Image.open(os.path.join(RACINE, "assets", "brand", "icone-512.png")).convert("RGBA")
    src.save(os.path.join(RACINE, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    fond = Image.new("RGBA", src.size, (11, 21, 19, 255))
    plein = Image.alpha_composite(fond, src).convert("RGB").resize((180, 180), Image.LANCZOS)
    plein.save(os.path.join(RACINE, "assets", "brand", "apple-touch-icon.png"), optimize=True)
    print("favicon.ico, assets/brand/apple-touch-icon.png")


if __name__ == "__main__":
    for l in ("en", "fr", "ar"):
        og(l)
    icones()
