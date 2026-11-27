# Málaga CF – FC Barcelona: monitoring biletów

Monitoring oficjalnej strony https://entradas.malagacf.com/ dla meczu z grudnia 2026.
Dodany mecz do weryfikacji: Málaga CF – Athletic Club (Bilbao), orientacyjnie
29 listopada 2026. Oba mecze mają osobne stany, GitHub Issues i alerty Discord.
Filtr dopasowuje nazwy drużyn; data nie jest wymagana, ponieważ może być niepotwierdzona.
Potrzeba: 4 bilety, najlepiej obok siebie.
13 grudnia to termin orientacyjny. Program nie kupuje i nie rezerwuje biletów.

## Działanie

Jedno uruchomienie workflow trwa ok. 5,5 godziny i sprawdza stronę co 5 minut,
a na koniec samo uruchamia następne, więc kontrola idzie bez przerwy.
Harmonogram (cron co 15 minut) jest tylko zapasem, który wznawia pętlę, gdyby się przerwała;
GitHub mocno opóźnia harmonogram, więc sam cron nie daje częstych kontroli.
Pętla wymaga publicznego repo: w prywatnym zużyłaby całą pulę minut GitHub Actions.
Athletic Club jest sprawdzany do 28 listopada 2026, Barcelona do 15 grudnia 2026.
Po 15 grudnia pętla się nie uruchamia. Wyłącz wtedy workflow w Actions.

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

Stan i historia zmian każdego meczu znajdują się w osobnym automatycznie tworzonym GitHub Issue.
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
