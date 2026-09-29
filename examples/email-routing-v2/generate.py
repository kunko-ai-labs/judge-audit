"""Seeded synthetic email-routing dataset, v2 (DE/EN, 10 categories, 1,000 rows).

What changed against v1 (examples/email-routing, frozen: the published audits cite it):
80 templates instead of 24 (four English and four German per category), 32 items
instead of 8, and company, sender, city, country and date fills; 1,000 rows, 100 per
category, and no two rows share a text (case and whitespace ignored). Templates, not
rows, are split: split-templates.json holds one English and one German template per
category out, and a held-out template is never used in development (see its `rule`).

Every row is synthetic. Ground truth is GT-1 (constructed): the category is the
template that produced the row; nobody checked it and it cannot show real-world
routing accuracy. Rows of one template differ only in their fills: near-duplicates by
design, which is why only the template-level split measures generalisation. The first
line of labels.jsonl declares this (docs/ground-truth.md).

Regenerate with: python generate.py   (CI: python scripts/synthetic_v2.py --check)
"""
from __future__ import annotations

import importlib.util
import random
from functools import partial
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("synthetic_v2_common",
                                               HERE.parent / "synthetic_v2_common.py")
common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(common)

NAME = "email-routing-v2"
LABELS = f"examples/{NAME}/labels.jsonl"
SPLIT = f"examples/{NAME}/split-templates.json"
SEED = 1042
N_ROWS = 1000

CATEGORIES = ["order", "quote_request", "invoice_dispute", "support", "delivery_status",
              "contract", "payment_reminder", "return_request", "partnership", "spam"]
OPTIONS = CATEGORIES
QUESTION = {"name": "category", "type": "choice",
            "instructions": "Route this business email into exactly one category",
            "options": OPTIONS}

# (template, lang). Slots: {n} {n2} reference numbers, {q} quantity, {q2} small count,
# {pct} percentage, {amount} EUR, {item}, {company}, {name}, {city}, {date},
# {country} / {land} (English / German name of one country).
TEMPLATES = {
    "order": [
        ("Confirming PO {n} for {q} units of {item}. Please ship as soon as possible.", "en"),
        ("Please process order {n}: {q}x {item}, delivery to our warehouse in {city}.", "en"),
        ("We would like to order {q} {item} at the price in your last offer. Our reference: {n}.", "en"),
        ("Order from {company}: {q} pcs {item}, requested delivery date {date}. Regards, {name}", "en"),
        ("Bestellung Nr. {n}: bitte {q} Stück {item} liefern.", "de"),
        ("Hiermit bestellen wir {q} Stück {item} zur Lieferung nach {city}. Bestellnummer {n}.", "de"),
        ("Auftrag {n} von {company}: {q}x {item}, Wunschtermin {date}.", "de"),
        ("Bitte liefern Sie gemäß Ihrem Angebot {n} {q} {item} an unser Werk in {city}. Gruß, {name}", "de"),
    ],
    "quote_request": [
        ("Please send a quote for {q} units of {item}. Reference {n}.", "en"),
        ("Could you quote {q} {item} with delivery to {city} by {date}?", "en"),
        ("What would {q} {item} cost including shipping? Please send your best price. {name}, {company}", "en"),
        ("Request for quotation {n}: {q} pcs {item}, incoterms DAP {city}.", "en"),
        ("Bitte um Angebot für {q} Stück {item}, Anfrage {n}.", "de"),
        ("Können Sie uns ein Angebot über {q} {item} mit Lieferung bis {date} machen?", "de"),
        ("Anfrage {n}: Was kosten {q} Stück {item} frei Haus {city}?", "de"),
        ("Wir benötigen ein Preisangebot für {q} {item}. Mit freundlichen Grüßen, {name}, {company}", "de"),
    ],
    "invoice_dispute": [
        ("Invoice {n} charges {amount} EUR too much. Please correct it.", "en"),
        ("Dispute on invoice {n}: we were billed for {q} units of {item} but received {q2}.", "en"),
        ("Your invoice {n} lists a unit price for {item} that does not match our contract. Please issue a credit note.", "en"),
        ("We contest invoice {n} over {amount} EUR: the freight to {city} was agreed free of charge. {name}", "en"),
        ("Rechnung Nr. {n} über {amount} EUR ist falsch. Bitte um Klärung.", "de"),
        ("Einspruch gegen Rechnung {n}: berechnet wurden {q} Stück {item}, geliefert nur {q2}.", "de"),
        ("Die Rechnung {n} enthält einen falschen Stückpreis für {item}. Bitte senden Sie eine Gutschrift.", "de"),
        ("Wir widersprechen der Rechnung {n}: die Fracht nach {city} war kostenfrei vereinbart. {name}, {company}", "de"),
    ],
    "support": [
        ("Your software crashes every time I export report {n} to PDF. Please fix it.", "en"),
        ("The {item} on line {q2} at our {city} plant stopped working this morning. We need a technician.", "en"),
        ("Cannot log in to the customer portal since {date}, error 500 when opening order {n}.", "en"),
        ("Ticket {n}: the firmware update bricked {q2} of our {item}. Please advise. {name}", "en"),
        ("Die Anlage mit {item} bleibt stehen. Techniker für Werk {city}, Linie {q2} erforderlich.", "de"),
        ("Seit {date} können wir uns nicht im Kundenportal anmelden. Fehler bei Auftrag {n}.", "de"),
        ("Störung {n}: {q2} von unseren {item} zeigen Fehlercode E{q}. Bitte um Rückruf.", "de"),
        ("Die Software stürzt beim Export von Bericht {n} ab. Bitte dringend beheben. {name}", "de"),
    ],
    "delivery_status": [
        ("Where is shipment {n}? Tracking shows no movement for {q2} days.", "en"),
        ("Could you tell us when order {n} ({q} {item}) will arrive in {city}?", "en"),
        ("Our delivery {n} was due on {date} and has not arrived. Please send an update.", "en"),
        ("Status request for consignment {n} to {city}, please. {name}, {company}", "en"),
        ("Wo bleibt die Lieferung {n}? Dringend, seit {q2} Tagen keine Bewegung.", "de"),
        ("Wann trifft Auftrag {n} mit {q} Stück {item} in {city} ein?", "de"),
        ("Die Sendung {n} war für den {date} angekündigt und ist nicht angekommen. Bitte um Status.", "de"),
        ("Bitte teilen Sie uns den Lieferstatus von Bestellung {n} mit. Gruß, {name}", "de"),
    ],
    "contract": [
        ("Attached is the signed framework agreement for {item}, reference {n}.", "en"),
        ("Please review the draft supply contract {n} with {company} before {date}.", "en"),
        ("We accept the amended terms of contract {n}; the countersigned copy follows by post to {city}.", "en"),
        ("Contract {n}: we would like to extend the term by {q2} years under the same conditions. {name}", "en"),
        ("Vertrag {n} zur Prüfung anbei. Gruß, {name}", "de"),
        ("Anbei der unterschriebene Rahmenvertrag über {item}, Vertragsnummer {n}.", "de"),
        ("Bitte prüfen Sie den Entwurf des Liefervertrags {n} mit {company} bis zum {date}.", "de"),
        ("Wir möchten den Vertrag {n} um {q2} Jahre zu gleichen Konditionen verlängern. {name}", "de"),
    ],
    "payment_reminder": [
        ("Friendly reminder: invoice {n} ({amount} EUR) is due next week.", "en"),
        ("Our records show invoice {n} over {amount} EUR is {q2} weeks overdue. Please pay promptly.", "en"),
        ("Second reminder for invoice {n}, due {date}. Kindly transfer {amount} EUR. {company}", "en"),
        ("Payment reminder from {company}: {amount} EUR for order {n} remains open. {name}", "en"),
        ("Zahlungserinnerung: Rechnung {n} über {amount} EUR.", "de"),
        ("Die Rechnung {n} über {amount} EUR ist seit {q2} Wochen fällig. Bitte begleichen Sie den Betrag.", "de"),
        ("Zweite Mahnung zur Rechnung {n}, fällig am {date}: {amount} EUR offen.", "de"),
        ("Freundliche Erinnerung von {company}: Auftrag {n}, offener Betrag {amount} EUR. {name}", "de"),
    ],
    "return_request": [
        ("We need to return {q} defective {item} from order {n}.", "en"),
        ("Please send an RMA number for {q2} damaged {item} delivered on {date}.", "en"),
        ("The {item} from delivery {n} do not match the specification. We want to send back all {q}.", "en"),
        ("Return request {n}: {q} {item} arrived in the wrong size. Please arrange pickup in {city}. {name}", "en"),
        ("Rücksendung von {q} Stück {item}, Auftrag {n}.", "de"),
        ("Bitte um RMA-Nummer für {q2} beschädigte {item} aus der Lieferung vom {date}.", "de"),
        ("Die {item} aus Lieferung {n} entsprechen nicht der Spezifikation. Wir senden alle {q} zurück.", "de"),
        ("Retoure {n}: {q} {item} in falscher Ausführung. Bitte Abholung in {city} veranlassen. {name}", "de"),
    ],
    "partnership": [
        ("{company} would like to discuss becoming a distributor for {item} in {country}.", "en"),
        ("{company} is looking for a technology partner for {item}. Would you be open to a call before {date}?", "en"),
        ("Proposal for a joint venture: co-developing {item} for the market in {country}. {name}, {company}", "en"),
        ("We run {q2} service centres around {city} and would like to become an authorised reseller of your {item}.", "en"),
        ("Partnerschaftsanfrage von {company} für den Vertrieb von {item} in {land}.", "de"),
        ("{company} sucht einen Technologiepartner für {item}. Hätten Sie vor dem {date} Zeit für ein Gespräch?", "de"),
        ("Vorschlag für eine Kooperation: gemeinsame Entwicklung von {item} für den Markt in {land}. {name}", "de"),
        ("Wir betreiben {q2} Servicezentren rund um {city} und möchten autorisierter Händler für Ihre {item} werden.", "de"),
    ],
    "spam": [
        ("Congratulations! You won a free cruise worth {amount} EUR. Click here now to claim prize {n}.", "en"),
        ("Earn {amount} EUR a week from home. No experience needed. Reply with code {n}.", "en"),
        ("Your mailbox is {pct} % full. Verify your account within {q2} hours or lose all messages. Ref {n}.", "en"),
        ("Exclusive offer: {pct} % off luxury watches today only. Unsubscribe code {n}.", "en"),
        ("Gratis Kredit über {amount} EUR ohne Schufa! Jetzt anrufen, Aktionscode {n}.", "de"),
        ("Sie haben gewonnen! Ihr Gutschein {n} über {amount} EUR wartet auf Sie.", "de"),
        ("Ihr Paket {n} konnte nicht zugestellt werden. Zahlen Sie {q2},99 EUR Gebühr über diesen Link.", "de"),
        ("Nur heute: {pct} % Rabatt auf Designeruhren. Abmeldecode {n}.", "de"),
    ],
}

ITEMS = ["M8x40 bolts", "bearings 6204", "hydraulic pumps", "conveyor belts", "pressure sensors",
         "valves DN50", "steel plates", "motors 3kW", "gear reducers", "PLC modules",
         "proximity switches", "air filters", "welding wire", "cable glands M20", "servo drives",
         "pneumatic cylinders", "roller chains", "O-rings 40x3", "frequency inverters",
         "flanges DN80", "torque wrenches", "safety relays", "linear guides", "shaft couplings",
         "cooling fans", "copper busbars", "hose clamps", "limit switches", "timing belts",
         "ball valves DN25", "hex nuts M12", "thermocouples type K"]
# Invented names: no real company or person is meant.
COMPANIES = ["Nordhafen Logistik GmbH", "Bergmann Antriebe", "Altmark Stahl KG", "Ribera Industrial S.L.",
             "Lindqvist Components AB", "Vesta Hydraulics Ltd", "Keller & Söhne", "Orbis Maschinenbau",
             "Tessaro Meccanica", "Hollis Supply Ltd", "Marek Fördertechnik", "Duarte Bombas Lda",
             "Falkenried Sensorik", "Oakridge Fasteners", "Brenner Ventiltechnik", "Kranich Automation",
             "Weserland Metall", "Polder Transport B.V.", "Castellan Motors", "Iselin Werkzeuge"]
NAMES = ["M. Schneider", "J. Okafor", "L. Fontaine", "A. Novak", "S. Brandt", "K. Yilmaz",
         "R. Lindgren", "T. Moreau", "E. Hoffmann", "D. Kowalski", "P. Weber", "C. Almeida",
         "F. Richter", "H. Janssen", "N. Rossi", "B. Keller"]
CITIES = ["Rotterdam", "Hamburg", "Bilbao", "Lyon", "Gdańsk", "Turin", "Antwerp", "Graz",
          "Brno", "Porto", "Malmö", "Leipzig", "Valencia", "Linz", "Göteborg", "Bremen"]
COUNTRIES = [("Spain", "Spanien"), ("Poland", "Polen"), ("Portugal", "Portugal"),
             ("Austria", "Österreich"), ("Sweden", "Schweden"), ("Czechia", "Tschechien"),
             ("Italy", "Italien"), ("Denmark", "Dänemark"), ("Belgium", "Belgien")]


def template_ids(templates: dict[str, list[tuple[str, str]]]) -> dict[str, list[tuple[str, str, str]]]:
    """category -> [(id, template, lang)], ids `category/lang-k` in declared order."""
    out: dict[str, list[tuple[str, str, str]]] = {}
    for cat, ts in templates.items():
        seen: dict[str, int] = {}
        out[cat] = []
        for text, lang in ts:
            seen[lang] = seen.get(lang, 0) + 1
            out[cat].append((f"{cat}/{lang}-{seen[lang]}", text, lang))
    return out


BY_CATEGORY = template_ids(TEMPLATES)
LANG_OF = {tid: lang for ts in BY_CATEGORY.values() for tid, _, lang in ts}
# One stratum per category and language: 4 templates each, 1 held out.
STRATA: dict[str, list[str]] = {}
for _cat, _ts in BY_CATEGORY.items():
    for _tid, _, _lang in _ts:
        STRATA.setdefault(f"{_cat}|{_lang}", []).append(_tid)
DEV, HELDOUT = common.split_templates(STRATA)
HALF = {**{t: "dev" for t in DEV}, **{t: "heldout" for t in HELDOUT}}
# The wording each template owns (scripts/synthetic_v2.py checks no held-out template
# shares a six-word run with a development one).
TEMPLATE_TEXTS = {tid: [text] for ts in BY_CATEGORY.values() for tid, text, _ in ts}


def fill(rng: random.Random, text: str) -> str:
    """One draw of every slot (the same number of draws whatever the template uses)."""
    country, land = rng.choice(COUNTRIES)
    return text.format(
        n=f"{rng.choice((2025, 2026))}-{rng.randint(10000, 99999)}",
        n2=f"{rng.choice((2025, 2026))}-{rng.randint(10000, 99999)}",
        q=rng.randint(5, 2000), q2=rng.randint(2, 9), pct=rng.randint(10, 90),
        amount=rng.randint(120, 48000), item=rng.choice(ITEMS),
        company=rng.choice(COMPANIES), name=rng.choice(NAMES), city=rng.choice(CITIES),
        date=f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        country=country, land=land)


def make_row(state: str, cat: str, lang: str, tid: str) -> dict:
    return {
        "state": state,
        "questions": [dict(QUESTION, options=list(OPTIONS))],
        "labels": {"category": cat},
        "_meta": {"lang": lang, "synthetic": True, "template": tid},
    }


def build(n: int = N_ROWS, seed: int = SEED) -> list[dict]:
    """Row i is category i mod 10 and cycles through that category's 8 templates."""
    rng = random.Random(seed)
    seen = common.Unique()
    rows = []
    for i in range(n):
        cat = CATEGORIES[i % len(CATEGORIES)]
        tid, text, lang = BY_CATEGORY[cat][(i // len(CATEGORIES)) % len(BY_CATEGORY[cat])]
        rows.append(make_row(seen.draw(partial(fill, rng, text)), cat, lang, tid))
    common.assert_unique_states(rows)
    return rows


def header(rows: list[dict]) -> dict:
    n_t = sum(map(len, TEMPLATES.values()))
    return {
        "ground_truth": {
            "tier": "GT-1", "label": "constructed", "validation": "not_validated",
            "purpose": ["calibration stress test",
                        "generalisation to templates never seen in development"],
            "caveats": [
                f"email categories are synthetic: {n_t} seeded templates (half English, half German) "
                f"with item, company, sender, city, country, date and number fills, not real mail",
                "the label is the template's category by design; no human checked it",
                f"{len(rows)} rows, no two with the same text (case and whitespace ignored), but rows "
                "of one template differ only in their fills: near-duplicates by design; only the "
                f"template-level split in {SPLIT} ({len(HELDOUT)} of {n_t} templates held out) "
                "measures generalisation",
                "100 % here is the floor a judge must clear, not evidence of production routing accuracy",
            ],
        },
        "generator": {"version": 2, "script": f"examples/{NAME}/generate.py", "seed": SEED,
                      "template_split": SPLIT,
                      "v1": "examples/email-routing (frozen: the published audits cite it)"},
    }


def files() -> dict[str, str]:
    """file name (in this directory) -> exact text."""
    rows = build()
    text = common.render_jsonl(header(rows), rows)
    split = common.split_record(dataset=NAME, labels=LABELS, question="category",
                                seed=common.SPLIT_SEED, strata=STRATA, dev=DEV,
                                heldout=HELDOUT, rows=rows, labels_text=text)
    return {"labels.jsonl": text, "split-templates.json": common.render_split(split)}


def main() -> None:
    for name, text in files().items():
        (HERE / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {N_ROWS} synthetic rows (seed={SEED}); {len(DEV)} development and "
          f"{len(HELDOUT)} held-out templates -> {HERE.name}/")


if __name__ == "__main__":
    main()
