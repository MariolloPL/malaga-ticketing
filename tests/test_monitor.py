import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from monitor import (HOST, MARKER, QueueActive, decode_state, event_status, fetch,
                     listing, main, next_state, should_alert, ticket_url)


def grid(name="MÁLAGA CF - FC BARCELONA", when="Date to be confirmed"):
    return f'''<div class="gridGen"><div class="gFitxaGen" id="gFitxaGen_1">
    <span class="gTitSpan">{name}</span><span class="dataE">{when}</span>
    <div class="gBoto"><a href="/en/malaga-barcelona">Purchase tickets</a></div>
    </div></div>'''


class Parsing(unittest.TestCase):
    def test_match_and_date(self):
        ev = listing(grid(when="Sunday, 13/12/2026 18:30"))
        self.assertEqual(ev["when"], "Sunday, 13/12/2026 18:30")
        self.assertEqual(ev["url"], f"https://{HOST}/en/malaga-barcelona")

    def test_other_games(self):
        for name in ("MÁLAGA CF - R. RACING CLUB", "MÁLAGA CF - RCD Espanyol de Barcelona",
                     "MÁLAGA CF - FC Barcelona Femenino", "Málaga - Barcelona Atlètic"):
            self.assertIsNone(listing(grid(name)))
        self.assertIsNone(listing(grid(when="13/12/2027 18:30")))

    def test_opponents_are_tracked_separately(self):
        athletic = grid("MÁLAGA CF - ATHLETIC CLUB", "Date to be confirmed")
        self.assertIsNone(listing(athletic, "barcelona"))
        self.assertIsNotNone(listing(athletic, "athletic"))
        self.assertIsNone(listing(grid(), "athletic"))
        self.assertIsNotNone(listing(grid("Málaga CF - Athletic Bilbao"), "athletic"))
        page = '<h1>Málaga CF - Athletic Club</h1><div class="areaLliures">AVAILABLE</div>'
        self.assertEqual(event_status(page, "athletic"), "selection")
        with self.assertRaises(ValueError):
            event_status(page, "barcelona")
        with self.assertRaises(ValueError):
            event_status('<h1>Málaga CF - Racing Club</h1><footer>Barcelona</footer>', "barcelona")

    def test_layout_error_is_not_absence(self):
        with self.assertRaises(ValueError):
            listing("<html>Maintenance</html>")

    def test_external_link_rejected(self):
        with self.assertRaises(ValueError):
            ticket_url("https://example.org/event")

    def test_sale_states(self):
        prefix = "<h1>Málaga CF - FC Barcelona</h1>"
        self.assertEqual(event_status(prefix + '<input name="key"><input name="pin">'), "members")
        self.assertEqual(event_status(prefix + '<div class="areaLliures">AVAILABLE</div>'), "selection")
        self.assertEqual(event_status(prefix + '<div class="areaLliures">SOLD OUT</div>'), "sold_out")
        self.assertEqual(event_status(prefix + '<p>Venta al público general</p>'), "public")
        self.assertEqual(event_status(prefix + '<p>Entradas: se abrirá venta al público general</p>'), "listed")
        self.assertEqual(event_status(prefix + '<div style="display:none"><input name="key"><input name="pin"></div>'
                                      '<div class="areaLliures">AVAILABLE</div>'), "selection")

    def test_wrong_event_is_error(self):
        with self.assertRaises(ValueError):
            event_status('<h1>Racing Club</h1><div class="areaLliures">AVAILABLE</div>')

    def test_queue_is_not_absence(self):
        session = Mock()
        session.get.return_value.url = "https://queue.koobin.com/"
        with self.assertRaises(QueueActive):
            fetch(session, "https://entradas.malagacf.com/")

    def test_state_changes_and_failure_alerts(self):
        baseline = {"status": "not_listed"}
        old = next_state({}, baseline)
        self.assertFalse(should_alert(old, baseline))
        error = {"status": "error"}
        self.assertFalse(should_alert(old, error))
        old = next_state(next_state(old, error), error)
        self.assertTrue(should_alert(old, error))
        old = next_state(old, error)
        self.assertFalse(should_alert(old, error))
        self.assertTrue(should_alert(old, baseline))
        self.assertEqual(old["snapshot"], baseline)

    def test_state_roundtrip(self):
        self.assertEqual(decode_state('text <!-- malaga-ticketing-state:{"failures":2} -->'), {"failures": 2})

    def test_new_discord_channel_sends_baseline_once(self):
        snapshot = {"status": "not_listed", "url": "https://entradas.malagacf.com/"}
        old = {"snapshot": snapshot, "failures": 0}
        with patch("monitor.GitHub") as github, patch("monitor.observe", return_value=snapshot), \
                patch("monitor.discord") as send, patch("monitor.Path.write_text"), \
                patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "test"}, clear=True), \
                patch("monitor.datetime") as clock:
            clock.now.return_value = datetime(2026, 11, 6, tzinfo=timezone.utc)
            issue = {"number": 1, "body": MARKER + json.dumps(old) + " -->"}
            github.return_value.issue.return_value = issue
            main()
            send.assert_called_once()
            self.assertIn("Monitoring Discord włączony", send.call_args.args[0])
            issue["body"] = github.return_value.call.call_args.kwargs["json"]["body"]
            main()
            send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
