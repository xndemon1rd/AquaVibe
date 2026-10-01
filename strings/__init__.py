# Authored By Dev © 2025
import os

import yaml

_LANG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "langs")

languages = {}
languages_present = {}


def get_string(lang: str):
    return languages[lang]


for filename in sorted(os.listdir(_LANG_DIR)):
    if "en" not in languages:
        languages["en"] = yaml.safe_load(
            open(os.path.join(_LANG_DIR, "en.yml"), encoding="utf8")
        )
        languages_present["en"] = languages["en"]["name"]
    if not filename.endswith(".yml"):
        continue
    language_name = filename[:-4]
    if language_name == "en":
        continue
    languages[language_name] = yaml.safe_load(
        open(os.path.join(_LANG_DIR, filename), encoding="utf8")
    )
    for item in languages["en"]:
        if item not in languages[language_name]:
            languages[language_name][item] = languages["en"][item]
    try:
        languages_present[language_name] = languages[language_name]["name"]
    except Exception:
        print("There is some issue with the language file inside bot.")
        exit()
