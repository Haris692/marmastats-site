"""Exporte les SVG de la charte en PNG transparents (Chrome sans fenêtre).
    python export_png.py <dossier brand>"""
import os
import shutil
import subprocess
import sys
import tempfile

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
dossier = sys.argv[1]
travaux = [
    ("logo-nuit.svg", "logo-nuit.png", 1600, 234),
    ("logo-craie.svg", "logo-craie.png", 1600, 234),
    ("symbole-nuit.svg", "symbole-nuit.png", 512, 512),
    ("symbole-craie.svg", "symbole-craie.png", 512, 512),
    ("icone.svg", "icone-512.png", 512, 512),
]
for src, dst, w, h in travaux:
    html = os.path.join(dossier, "_export.html")
    with open(html, "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:transparent}'
                'img{display:block}</style><img src="%s" width="%d" height="%d">' % (src, w, h))
    profil = tempfile.mkdtemp(prefix="exp-")
    try:
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                        "--default-background-color=00000000", "--window-size=%d,%d" % (w, h),
                        "--user-data-dir=" + profil, "--screenshot=" + os.path.join(dossier, dst),
                        "file:///" + html.replace("\\", "/")],
                       capture_output=True, timeout=60)
    finally:
        shutil.rmtree(profil, ignore_errors=True)
        os.remove(html)
    print(dst, os.path.getsize(os.path.join(dossier, dst)), "octets")
