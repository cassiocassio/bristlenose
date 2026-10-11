"""Hidden mutants for the PBT trial. Each: (id, file, old, new, note). Applied one at a time to a copy of tree/."""
MUTANTS = [
 ("M1","bristlenose/utils/timecodes.py","    if h:\n        return f\"{h}:{m:02d}:{s:02d}\"","    if h > 1:\n        return f\"{h}:{m:02d}:{s:02d}\"","1-hour values drop the hour"),
 ("M2","bristlenose/utils/timecodes.py","ms_str = ms.ljust(3, \"0\")","ms_str = ms.rjust(3, \"0\")","SRT .5 -> 0.005"),
 ("M3","bristlenose/utils/timecodes.py","    total = max(0, int(seconds))\n    h = total // 3600","    total = max(0, round(seconds))\n    h = total // 3600","format rounds instead of truncating"),
 ("M4","bristlenose/utils/text.py","text = text[:max_length].rstrip(\"-\")\n\n    return text\n","text = text[:max_length]\n\n    return text\n","slug may end in hyphen after truncation"),
 ("M5","bristlenose/utils/text.py","    text = \"\".join(c for c in text if not unicodedata.combining(c))\n","","EQUIVALENT? accents removed by later regex anyway"),
 ("M6","bristlenose/utils/text.py","    text = text.strip(\". \")\n","    text = text.strip(\" \")\n","leading/trailing dots kept"),
 ("M7","bristlenose/utils/text.py","text = text[:max_length].rstrip(\". \")","text = text[:max_length + 1].rstrip(\". \")","off-by-one truncation"),
 ("M8","bristlenose/utils/timecodes.py","return f\"{h}h {m}m\" if m > 0 else f\"{h}h\"","return f\"{h}h {m}m\"","1h renders '1h 0m'"),
 ("M9","bristlenose/utils/timecodes.py","    return dt.astimezone(timezone.utc)\n","    return dt.replace(tzinfo=timezone.utc)\n","overwrite offset instead of convert (historical bug)"),
 ("M10","bristlenose/utils/timecodes.py","if m and len(text) >= 6 and text[-6] != \":\":","if m and len(text) >= 6 and text[-6] == \":\":","colon-less +0100 no longer normalised"),
 ("M11","bristlenose/utils/timecodes.py","        frac = int(ms.ljust(3, \"0\")) / 1000 if ms else 0.0","        frac = int(ms) / 1000 if ms else 0.0","simple-format .5 -> 0.005"),
 ("M12","bristlenose/utils/text.py","text = re.sub(r\"-+\", \"-\", text)","text = text","hyphens not collapsed"),
]
