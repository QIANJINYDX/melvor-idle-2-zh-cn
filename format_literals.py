"""Translate reviewed display literals inside SmartFormat expressions."""

REPLACEMENTS = {
    '{Value:cond:<0?Decreased|>=0?Increased}': '{Value:cond:<0?降低|>=0?提高}',
    '{1:list:0|, |, and }': '{1:list:0|、|和}',
}


def translate_format_literals(text):
    # Only these complete expressions are approved; selectors, tests and
    # numeric formats remain unchanged. Never run on IDs or raw game data.
    for source, target in REPLACEMENTS.items():
        text = text.replace(source, target)
    return text
