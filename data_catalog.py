"""Translate presentation fields, never object IDs, type names or save data."""
import hashlib
import json
from pathlib import Path

import polib

from additions import TRANSLATIONS, PRESERVE
from format_literals import translate_format_literals
from unit_preferences import preserve_units

DISPLAY_FIELDS = {
    'DisplayName', 'Singular', 'Plural', 'DialogueText', 'Description',
    'TemplateString', 'CustomDescription', 'CompletedDescription', 'Observation',
    'UnlockText', 'CustomRewards', 'DisplayNameShort', 'SightingText', 'Subtitle',
    'Backstory', 'OverridePlantTerminology', 'OverrideIngredientError', 'ResistanceName',
}


def translate_data(payload, chinese):
    po = polib.pofile(chinese.decode('utf-8'), encoding='utf-8')
    translations = {}
    by_hash = {}
    for entry in po:
        if entry.obsolete:
            continue
        value = entry.msgstr or entry.msgstr_plural.get(0, '')
        if value:
            translations[entry.msgid] = value
            by_hash[hashlib.sha256(entry.msgid.encode()).hexdigest()] = value
            if entry.msgid_plural:
                translations[entry.msgid_plural] = value
    translations.update(TRANSLATIONS)
    aliases = json.loads(Path(__file__).with_name('reviewed_aliases.json').read_text('utf-8'))
    stories = json.loads(Path(__file__).with_name('story_translations.json').read_text('utf-8'))
    data = json.loads(payload)
    missing = {}
    count = 0

    def lookup(text):
        key = hashlib.sha256(text.encode()).hexdigest()
        if key in stories:
            return stories[key]
        if text in translations:
            return translations[text]
        target = aliases.get(key)
        return by_hash.get(target) if target else None

    def walk(value):
        nonlocal count
        if isinstance(value, dict):
            # Look up sibling singular before mutation; Chinese does not inflect plural names.
            singular = value.get('Singular')
            for key, child in list(value.items()):
                if key in DISPLAY_FIELDS and isinstance(child, str) and child and child not in PRESERVE:
                    translated = lookup(child)
                    if translated is None and key == 'Plural' and isinstance(singular, str):
                        translated = lookup(singular)
                    if translated is not None:
                        value[key] = preserve_units(child, translate_format_literals(translated))
                        count += 1
                    else:
                        missing[child] = key
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'), {
        'translated_fields': count, 'missing': missing,
    }
