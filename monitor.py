"""Read-only ticket watch. GitHub issue stores state; Discord is optional."""
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HOST = "entradas.malagacf.com"
URL = f"https://{HOST}/?idioma=EN&act=1"
TARGET = os.environ.get("TARGET_MATCH", "barcelona")
MATCHES = {"barcelona": "Málaga CF – FC Barcelona",
           "athletic": "Málaga CF – Athletic Club (Bilbao)"}
MATCH_NAME = MATCHES[TARGET]
TITLE = MATCH_NAME + ": monitoring biletów"
MARKER = "<!-- malaga-ticketing-state:" if TARGET == "barcelona" else "<!-- malaga-ticketing-athletic-state:"
REPORT = "report.json" if TARGET == "barcelona" else "report-athletic.json"
LABELS = {
    "not_listed": "Meczu nie ma jeszcze na liście sprzedaży",
    "listed": "Mecz pojawił się w ofercie; etap sprzedaży niepotwierdzony",
    "members": "Wymagane dane socios (Key/ID i PIN)",
    "public": "Strona informuje o sprzedaży ogólnej",
    "selection": "Sektory dostępne bez logowania; dalsze warunki niezweryfikowane",
    "sold_out": "Strona pokazuje wyprzedane sektory",
    "queue": "Aktywna kolejka Koobin; stan sprzedaży nieznany",
    "error": "Nie udało się sprawdzić sprzedaży",
}


def norm(text):
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", text)
                            if not unicodedata.combining(c)).lower().split())


def text(node):
    return " ".join(node.stripped_strings) if node else ""


def ticket_url(href):
    url = urljoin(URL, href)
    if urlparse(url).hostname != HOST or urlparse(url).scheme != "https":
        raise ValueError("Nieoczekiwany adres strony wydarzenia")
    return url


def matches_team(name, opponent):
    n = norm(name)
    if "malaga" not in n or any(word in n for word in ("femen", "women", "atletic", "juvenil")):
        return False
    if opponent == "barcelona":
        return "barcelona" in n and "espanyol" not in n
    return bool(re.search(r"\bathletic\b|\bbilbao\b", n))


def listing(html, opponent=TARGET):
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one(".gridGen, #contingut"):
        raise ValueError("Brak rozpoznanej listy wydarzeń (blokada lub zmiana strony)")
    matches = []
    for card in soup.select("div.gFitxaGen[id^='gFitxaGen_']"):
        name = text(card.select_one(".gTitSpan, .gTitol"))
        if not matches_team(name, opponent):
            continue
        when = text(card.select_one(".dataE"))
        # A URL can contain an obsolete placeholder date: only inspect displayed text.
        year = re.search(r"\b20\d{2}\b", when)
        if year and year.group() != "2026":
            continue
        link = card.select_one(".gBoto a[href]")
        matches.append({"id": card.get("id"), "title": name, "when": when,
                        "button": text(card.select_one(".gBoto")),
                        "url": ticket_url(link["href"]) if link else URL})
    if len(matches) > 1:
        raise ValueError("Kilka pasujących ofert; wymagają ręcznej weryfikacji")
    return matches[0] if matches else None


def event_status(html, opponent=TARGET):
    soup = BeautifulSoup(html, "html.parser")
    headings = [text(n) for n in soup.select("h1, .gTitSpan, .gTitol")]
    if not any(matches_team(name, opponent) for name in headings):
        raise ValueError("Nagłówek strony szczegółów nie potwierdza właściwego meczu")
    for node in soup.select("script, style, header, footer, nav, [hidden], [aria-hidden='true']"):
        node.decompose()
    for node in list(soup.select("[style]")):
        if node.parent and re.search(r"display\s*:\s*none", node.get("style", ""), re.I):
            node.decompose()
    words = norm(text(soup))
    fields = " ".join(norm(" ".join(str(n.get(k, "")) for k in ("name", "id", "placeholder")))
                      for n in soup.select("input:not([type='hidden'])"))
    gate = bool(re.search(r"\bpin\b", fields) and
                re.search(r"\b(key|id|clave|socio|abonado|codi|codigo)\b", fields))
    areas = [norm(text(n)) for n in soup.select(".areaLliures")]
    if gate:
        return "members"
    if any(p in words for p in ("venta exclusiva para socios", "solo para abonados", "members only")):
        return "members"
    if any(p in words for p in ("venta al publico general", "venta para publico general", "general public sale")):
        if not any(p in words for p in ("proximamente", "not yet", "coming soon", "se abrira")):
            return "public"
    if any(a in ("available", "disponible", "disponibles") for a in areas):
        return "selection"
    if areas and all(a in ("sold out", "agotado", "agotadas", "agotados") for a in areas):
        return "sold_out"
    if not areas and not any(p in words for p in ("purchase", "tickets", "entradas", "pin")):
        raise ValueError("Nieznany układ strony wydarzenia")
    return "listed"


class QueueActive(Exception):
    pass


def fetch(session, url):
    r = session.get(url, timeout=30)
    r.raise_for_status()
    if urlparse(r.url).hostname == "queue.koobin.com":
        raise QueueActive()
    if urlparse(r.url).hostname != HOST:
        raise ValueError("Nieoczekiwane przekierowanie")
    return r.text


def observe(session):
    ev = listing(fetch(session, URL))
    if not ev:
        return {"status": "not_listed", "url": URL}
    try:
        status = event_status(fetch(session, ev["url"]))
        return {"status": status, "event": ev, "url": ev["url"]}
    except QueueActive:
        return {"status": "queue", "event": ev, "url": ev["url"]}
    except (requests.RequestException, ValueError):
        return {"status": "listed", "event": ev, "url": ev["url"], "detail_error": True}


def message(snapshot):
    lines = [MATCH_NAME, LABELS[snapshot["status"]]]
    ev = snapshot.get("event", {})
    if ev.get("when"):
        lines.append("Termin wyświetlany przez klub: " + ev["when"])
    lines.append(snapshot.get("url", URL))
    if snapshot["status"] in ("public", "selection"):
        lines.append("Sprawdź zakup 4 biletów: 2 dorosłych + dzieci 6 i 8 lat. "
                     "Cztery miejsca obok siebie nie zostały zweryfikowane.")
    if snapshot["status"] == "error":
        lines.append("Zobacz log uruchomienia w GitHub Actions.")
    if snapshot.get("detail_error"):
        lines.append("Oferta jest na liście, ale odczyt szczegółów nie powiódł się.")
    return "\n\n".join(lines)


def decode_state(body):
    match = re.search(re.escape(MARKER) + r"(.*?) -->", body or "", re.S)
    return json.loads(match.group(1)) if match else {}


def should_alert(old, new):
    previous = old.get("snapshot")
    if new["status"] == "error":
        return old.get("failures", 0) + 1 == 3
    return previous != new or old.get("failures", 0) >= 3


def next_state(old, snapshot):
    if snapshot["status"] == "error":
        return {**old, "failures": min(old.get("failures", 0) + 1, 3)}
    return {"snapshot": snapshot, "failures": 0}


class GitHub:
    def __init__(self):
        self.base = "https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"]
        self.http = requests.Session()
        self.http.headers.update({"Authorization": "Bearer " + os.environ["GH_TOKEN"],
                                  "Accept": "application/vnd.github+json"})

    def call(self, method, path, **kwargs):
        r = self.http.request(method, self.base + path, timeout=30, **kwargs)
        r.raise_for_status()
        return r.json()

    def issue(self):
        page = 1
        while True:
            issues = self.call("GET", f"/issues?state=all&per_page=100&page={page}")
            for issue in issues:
                if "pull_request" not in issue and MARKER in (issue.get("body") or ""):
                    return issue
            if len(issues) < 100:
                return self.call("POST", "/issues", json={"title": TITLE, "body": MARKER + "{} -->"})
            page += 1


def discord(content):
    hook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not hook:
        return
    if urlparse(hook).hostname not in ("discord.com", "discordapp.com") or not hook.startswith("https://"):
        raise ValueError("Nieprawidłowy adres webhooka Discord")
    try:
        r = requests.post(hook, params={"wait": "true"},
                          json={"content": content[:1950], "allowed_mentions": {"parse": []}}, timeout=30)
        r.raise_for_status()
    except requests.RequestException:
        # Never print requests' exception: it can contain the secret webhook URL.
        raise RuntimeError("Nie udało się dostarczyć alertu Discord") from None


def send_reminders():
    reminders = []
    for path in Path(".").glob("reminder-*.json"):
        alert = json.loads(path.read_text(encoding="utf-8"))
        for number in (1, 2):
            reminders.append((alert["sent_at"] + 300 * number, number, alert["content"]))
    failed = False
    for due, number, content in sorted(reminders):
        time.sleep(max(0, due - time.time()))
        try:
            discord(f"Przypomnienie {number}/2 o wcześniejszym alercie\n\n{content}")
        except RuntimeError as exc:
            print(exc)
            failed = True
    return int(failed)


def main():
    if datetime.now(timezone.utc).date().isoformat() > "2026-12-15":
        print("Okres monitoringu zakończony. Wyłącz workflow w Actions.")
        return
    gh = GitHub()
    issue = gh.issue()
    old = decode_state(issue.get("body"))
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; MalagaTicketWatch/1.0)",
                            "Accept-Language": "en-GB,en;q=0.9"})
    try:
        snapshot = observe(session)
    except QueueActive:
        snapshot = {"status": "queue", "url": URL}
    except (requests.RequestException, ValueError) as exc:
        print("Błąd odczytu:", type(exc).__name__)
        snapshot = {"status": "error", "url": URL}
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    Path(REPORT).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    content = message(snapshot)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(content + "\n\nAlerty: GitHub Issue" +
                    (" + Discord" if os.environ.get("DISCORD_WEBHOOK_URL") else " (Discord nieskonfigurowany)") + "\n")
    state = next_state(old, snapshot)
    state["discord_enabled"] = bool(os.environ.get("DISCORD_WEBHOOK_URL"))
    new_channel = state["discord_enabled"] and not old.get("discord_enabled")
    changed = should_alert(old, snapshot)
    if changed or new_channel:
        discord(("Monitoring Discord włączony. Aktualny stan:\n\n" if new_channel else "") + content)
        previous = old.get("snapshot") or {}
        appeared = snapshot.get("event") and not previous.get("event")
        opened = snapshot["status"] in ("public", "selection") and previous.get("status") != snapshot["status"]
        if changed and state["discord_enabled"] and (appeared or opened):
            reminder = {"sent_at": time.time(), "content": content}
            Path(f"reminder-{TARGET}.json").write_text(json.dumps(reminder), encoding="utf-8")
    if changed:
        gh.call("POST", f"/issues/{issue['number']}/comments", json={"body": content})
    if state != old:
        body = content + "\n\nOstatnia zmiana: " + datetime.now(timezone.utc).isoformat() + "\n\n"
        body += MARKER + json.dumps(state, ensure_ascii=True) + " -->"
        gh.call("PATCH", f"/issues/{issue['number']}", json={"body": body})
    if snapshot["status"] == "error" or snapshot.get("detail_error"):
        sys.exit(1)


if __name__ == "__main__":
    if sys.argv[1:] == ["--remind"]:
        sys.exit(send_reminders())
    main()
