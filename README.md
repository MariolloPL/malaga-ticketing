# Málaga CF – FC Barcelona: monitoring biletów

Monitoring oficjalnej strony https://entradas.malagacf.com/ dla meczu z grudnia 2026.
Potrzeba: 4 bilety (2 dorosłych, dzieci 6 i 8 lat), najlepiej obok siebie.
13 grudnia to termin orientacyjny. Program nie kupuje i nie rezerwuje biletów.

## Działanie

GitHub Actions uruchamia kontrolę co 15 minut, o minutach 07, 22, 37 i 52 każdej godziny.
GitHub może opóźniać harmonogram; nie jest to gwarancja alertu w ciągu 15 minut.
W prywatnym repo uruchomienia zużywają pulę minut GitHub Actions.
Po 15 grudnia 2026 skrypt nie odpytuje strony. Wyłącz wtedy workflow w Actions,
żeby zatrzymać również uruchamianie runnerów.

Skrypt zachowuje cookies podczas kontroli i podąża za normalnymi przekierowaniami
Koobin. Nie omija kolejki ani zabezpieczeń. Nie wymaga konta klubu.

Rozróżniane stany:

| Stan | Znaczenie |
| --- | --- |
| Brak na liście | Lista wydarzeń odczytana, brak docelowego meczu |
| Oferta pojawiła się | Mecz wykryty, warunki sprzedaży niepotwierdzone |
| Socios | Wymagane Key/ID i PIN lub jawny komunikat o sprzedaży dla członków |
| Sprzedaż ogólna | Jawna informacja strony o sprzedaży dla publiczności |
| Wybór sektorów | Dostępne sektory bez logowania; późniejsze ograniczenia niezweryfikowane |
| Wyprzedane | Wszystkie widoczne sektory oznaczone jako wyprzedane |
| Kolejka | Koobin zatrzymał użytkownika w kolejce; dostępność nieznana |
| Błąd | Odczyt niemożliwy; nie jest interpretowany jako brak biletów |

Data i godzina pochodzą z wyświetlanej karty wydarzenia, nigdy ze sluga URL.
Zmiana wyświetlanego terminu wywołuje alert. Samo pokazanie godziny nie dowodzi,
że termin jest ostateczny. Program nie sprawdza czterech sąsiadujących miejsc.
Klasyfikacja wymaga ponownej weryfikacji po zmianie układu serwisu.

## Alerty

Stan i historia zmian znajdują się w jednym automatycznie tworzonym GitHub Issue.
Pierwsza kontrola zapisuje punkt odniesienia. Kolejne komentarze pojawiają się tylko
po zmianie stanu lub terminu. Po trzech kolejnych błędach odczytu listy pojawia się
alert o awarii; po przywróceniu odczytu — informacja o powrocie.
Każdy błąd odczytu jest również widoczny jako nieudane uruchomienie Actions.

Aby otrzymywać powiadomienia GitHub, włącz **Watch → All Activity** dla repozytorium
albo **Subscribe** w utworzonym Issue i sprawdź ustawienia powiadomień konta.

Dla Discorda dodaj repozytoryjny Actions secret **DISCORD_WEBHOOK_URL**:

Settings → Secrets and variables → Actions → New repository secret.

Wartość to URL webhooka wybranego kanału. Nie wpisuj go do kodu, Issue ani README.
Bez tego secretu działają alerty w GitHub Issue. Po dodaniu secretu uruchom workflow
ręcznie. Pierwsze uruchomienie z dodanym secretem wyśle potwierdzenie włączenia
Discorda i aktualny stan, nawet gdy dostępność biletów się nie zmieniła.
Jeśli chcesz ponownie przetestować Discord bez czekania na zmianę strony, uruchom
workflow **Test Discord**. Test wysyła jedną wiadomość na skonfigurowany kanał.

Hasło do konta Málaga nie jest potrzebne. Konto zwykłego klienta nie daje ID/PIN socios.

## Kontrola działania

Actions → **Bilety Malaga - Barcelona** → **Run workflow**.
Podsumowanie uruchomienia pokazuje wynik i aktywne kanały alertów.
Artefakt `ticket-status` zawiera `report.json`. Pełne strony, cookies i dane logowania
nie są zapisywane w artefaktach.

Lokalne testy:

```sh
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Testy sprawdzają parser i zmiany stanów, nie dowodzą aktualnej dostępności serwisu.
