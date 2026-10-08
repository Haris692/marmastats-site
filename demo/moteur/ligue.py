import re

def publie(data_dir):
    return (None, [])

def slug(texte):
    return re.sub('[^a-z0-9]+', '-', str(texte).lower()).strip('-')
