"""Seeded synthetic email-routing dataset generator (DE/EN, 10 categories).

Every row is synthetic. Ground truth is GT-1 (constructed): the category is
the template that produced the row; nobody checked it and it cannot show
real-world routing accuracy. The first line of labels.jsonl declares this
(docs/ground-truth.md). Regenerate with: python generate.py
"""
import json
import random

# Dataset header: provenance of the labels, read by judge_audit.runner.load_dataset.
DATASET = {"ground_truth": {
    "tier": "GT-1", "label": "constructed", "validation": "not_validated",
    "purpose": ["calibration stress test", "CI drift baseline"],
    "caveats": ["email categories are synthetic: seeded templates with item and number fills, not real mail",
                "the label is the template's category by design; no human checked it",
                "100 % here is the floor a judge must clear, not evidence of production routing accuracy"],
}}

CATEGORIES = ["order", "quote_request", "invoice_dispute", "support", "delivery_status",
              "contract", "payment_reminder", "return_request", "partnership", "spam"]

TEMPLATES = {
    "order": [
        ("Confirming PO-{n} for {q} units of {item}. Ship ASAP.", "en"),
        ("Bestellung Nr. {n}: bitte {q} Stück {item} liefern.", "de"),
        ("Please process order {n}: {q}x {item}, delivery to Rotterdam.", "en"),
    ],
    "quote_request": [
        ("Please send a quote for {q} units of {item}.", "en"),
        ("Bitte um Angebot für {q} Stück {item}.", "de"),
        ("Could you quote {q} {item} with delivery next month?", "en"),
    ],
    "invoice_dispute": [
        ("Rechnung Nr. {n} über {q} EUR ist falsch. Bitte um Klärung.", "de"),
        ("Invoice {n} charges {q} EUR too much. Please correct.", "en"),
        ("Dispute on invoice {n}: we were billed for {q} units, received {q2}.", "en"),
    ],
    "support": [
        ("Your software crashes every time I export to PDF. Fix it.", "en"),
        ("Die Maschine {item} bleibt stehen. Techniker erforderlich.", "de"),
        ("Cannot log in since yesterday, error 500 on {item}.", "en"),
    ],
    "delivery_status": [
        ("Where is shipment {n}? Tracking shows no movement for 5 days.", "en"),
        ("Wo bleibt die Lieferung {n}? Dringend.", "de"),
    ],
    "contract": [
        ("Attached the signed framework agreement for {item}.", "en"),
        ("Vertrag {n} zur Prüfung anbei.", "de"),
    ],
    "payment_reminder": [
        ("Friendly reminder: invoice {n} ({q} EUR) is due next week.", "en"),
        ("Zahlungserinnerung: Rechnung {n} über {q} EUR.", "de"),
    ],
    "return_request": [
        ("We need to return {q} defective {item} from order {n}.", "en"),
        ("Rücksendung von {q} Stück {item}, Auftrag {n}.", "de"),
    ],
    "partnership": [
        ("We'd like to discuss becoming a distributor for {item} in Spain.", "en"),
        ("Partnerschaftsanfrage für Vertrieb von {item}.", "de"),
    ],
    "spam": [
        ("Congratulations! You won a free cruise. Click here now.", "en"),
        ("Gratis Kredit ohne Schufa! Jetzt anrufen.", "de"),
    ],
}
ITEMS = ["M8x40 bolts", "bearings 6204", "hydraulic pumps", "conveyor belts", "sensors",
         "valves DN50", "steel plates", "motors 3kW"]

OPTIONS = CATEGORIES


def make_row(rng, i):
    cat = CATEGORIES[i % len(CATEGORIES)]
    text, lang = rng.choice(TEMPLATES[cat])
    state = text.format(n=f"2026-{rng.randint(1000, 9999)}", q=rng.randint(10, 900),
                        q2=rng.randint(1, 9), item=rng.choice(ITEMS))
    return {
        "state": state,
        "questions": [{"name": "category", "type": "choice",
                       "instructions": "Route this business email into exactly one category",
                       "options": OPTIONS}],
        "labels": {"category": cat},
        "_meta": {"lang": lang, "synthetic": True},
    }


def main(n=200, seed=42):
    rng = random.Random(seed)
    rows = [make_row(rng, i) for i in range(n)]
    with open("labels.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"idx": -1, "dataset": DATASET}, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {n} synthetic rows (seed={seed})")


if __name__ == "__main__":
    main()
