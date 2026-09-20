# Kiosk CNC — instrukcja operatora

**fh6parse 1.4.0.** Ekran po polsku. Pełny montaż, okablowanie i aktualizacja z SSH: `packaging/LINUX-KIOSK.md` (angielski, serwis).

Ten arkusz jest do stołu przy maszynie. Nie instaluje się tu systemu i nie zmienia się pinów.

---

## 1. Codziennie

1. Włącz kiosk. Na ekranie: **Włóż pendrive** (albo lista z poprzedniego kija, jeśli został w gnieździe).
2. Włóż pendrive. Programy **`.nc` / `.tap` w katalogu głównym** kija (nie w podfolderach) pojawiają się na liście. Przy liczbie plików: **Można wyjąć** = wolno wyciągnąć kij. **Czytanie pendrive — czekaj** = kiosk jeszcze czyta (podgląd albo kopiuje STEP) — nie wyrywaj.
3. Pokrętłem **pliku** podświetl program (za ostatnim wraca na pierwszy). Drugie pokrętło wybiera obrabiarkę (też się zawija; nazwa obok wersji). Pod listą widać operacje (ile narzędzi, czas cyklu), czy jest widok 3D, i izometrię detalu gdy jest gotowa. Tu sprawdzasz OP1 vs OP2 **zanim** wydrukujesz. Jeśli na kiju nadpiszesz ten sam `.nc`, podgląd sam się odświeży — poczekaj aż zniknie **Czytanie…**, potem LOAD / SET / RUN. Lista i trzy kolorowe pola na dole są duże — pola stoją nad przyciskami.
4. Przycisk **zielony LOAD** (lewy, pod ekranem) — bilet operatora (T, H/D/S, Min Z, kratki załadunku, podpis). Treść zmieniasz w **F2**.
5. Przycisk **żółty SET** (środek) — bilet ustawiacza (program, mill, STEP gdy gotowy, prostokąt offsetu, czas cyklu bez wykresu, uwagi `!`).
6. Przycisk **czerwony RUN** (prawy) — pełny bilet 80 mm (STEP, offset, operacje, czas, rozkład G0/skrawanie/ATC, lista narzędzi, każda wymiana Txx / M00). Bez kratek załadunku i podpisu.
7. Po bilecie krótka pauza (**Czekaj przed następnym biletem**) — drugie naciśnięcie nie da dwóch kartek.
8. Na dole **Pokrywa otwarta**, **Brak papieru** albo **Zacięcie drukarki** — nie drukuj, najpierw drukarka. Przycisk nie wytnie pustego biletu.
9. Brak żółtej kostki 3D obok nazwy = drukuj i tak. Bilet będzie sam tekst, bez czekania. Chip przy kostce mówi dlaczego: **szuka…** / **liczy…** / **brak STEP** / **Z: wył.** / **brak CAD**.
10. Po dobrym druku na dole: **`device:/dev/usb/lp0`**. Jeśli widać `lp:…`, wołaj serwis (kolejka CUPS zamiast USB).
11. Po **60 s** bez pokrętła i bez nowego USB ekran gaśnie (oszczędza panel).

---

## 2. Co oznacza ekran

| Widok | Znaczenie |
| --- | --- |
| **Włóż pendrive** | Brak kija albo brak `.nc` / `.tap` w korzeniu kija |
| **Można wyjąć** przy liczbie plików | Kiosk nie czyta kija — wolno wyciągnąć |
| **Czytanie pendrive — czekaj** | Podgląd albo kopia STEP z kija — nie wyrywaj |
| Żółta **kostka 3D** przy pliku | Widok izometryczny gotowy do druku |
| **3D gotowe** przy kostce | Ten plik ma rysunek — można drukować z izometrią |
| **szuka…** | Szuka pasującego `.stp` na kiju albo udziale — poczekaj albo drukuj tekst |
| **liczy…** | Znalazł model, rysuje izometrię — poczekaj albo drukuj tekst |
| **brak STEP** | Brak pasującego `.stp` (kij i udział). Drukuj tekst |
| **Z: wył.** | Firmowy udział (dysk Z:) nieosiągalny. Kij bez `.stp` = tylko tekst |
| **brak CAD** | Na kiosku nie ma bibliotek 3D — serwis (`pip … [models]`). Drukuj tekst |
| Izometria pod podświetleniem | Ten sam rysunek co na bilecie — zły STEP widać przed drukiem |
| **v1.4.0** u góry | Wersja programu (numer może zostać, a żółty **AKTUALIZUJ** pokazuje skrót gita) |
| Nazwa obrabiarki przy wersji | Drugie pokrętło (mill). Ta sama lista co **Dodaj obrabiarkę…** |
| Chip **PL** / **EN** | Język ekranu i biletu. Domyślnie polski |
| Trzy kolorowe pola na dole | Nad przyciskami: **zielony LOAD**, **żółty SET**, **czerwony RUN** (od lewej) |
| **Czekaj przed następnym biletem** | Pauza po druku — przycisk zignorowany, żeby nie było dwóch kartek |
| **Pokrywa otwarta** | Zamknij pokrywę P047 — LOAD / SET / RUN nic nie wyśle |
| **Brak papieru** | Załaduj rolkę 80 mm |
| **Zacięcie drukarki** | Sprawdź papier i nożyk; nie wciskaj RUN w kółko |

Kiosk **nie zapisuje i nie kasuje** plików na pendrive ani w firmowym folderze dokumentacji (udział sieciowy / dysk Z:). Czyta `.stp` / `.step`. Rysunki trzyma w pamięci tymczasowej na kiosku.

---

## 3. Druk

- **LOAD** (zielony, lewy) — załadunek: T, H/D/S, opis, Min Z, kratki, podpis. Treść w **F2**.
- **SET** (żółty, środek) — ustawianie: mill, STEP gdy kostka jest, prostokąt offsetu, czas cyklu (bez wykresu), uwagi `!`.
- **RUN** (czerwony, prawy) — pełna lista narzędzi, czas, rozkład G0 / skrawanie / cykl / ATC na każde T, Min Z, każda wymiana, izometria gdy kostka już jest. Bez kratek i podpisu. Gdy obrabiarka ma skok: prostokąt punktu zerowego offsetu w współrzędnych maszyny (rogi, środek, maks. Ø G41/G42 wyśrodkowane).
- Papier: **80 mm**, drukarka termiczna przy kiosku. Nie skalować do A4.
- Jeśli na dole jest **Brak papieru** / **Pokrywa otwarta** / **Zacięcie drukarki**, najpierw drukarka — kiosk nie wytnie pustej kartki.
- Komentarze z programu (polskie opisy narzędzi) zostają jak w NC. Napisy kiosku i biletu są po polsku, gdy wybrano **Polski**.

---

## 4. Ostrzeżenia na bilecie (**UWAGA**)

| Na bilecie | Co zrobić |
| --- | --- |
| `H… nie zgadza się z T…` | Zły offset długości na G43 — sprawdź H vs numer narzędzia |
| `D… nie zgadza się z T…` | Zła korekcja promienia (G43 / G41 / G42) |
| `G95 nadal aktywne… ustaw G94` | Po gwintowaniu / posuwie na obrót brak G94 przed następnym T (albo M30) |
| `brak ruchu po wymianie narzędzia` | Pusta kieszeń: Txx M6 bez ruchu. **Ostatnia** wymiana bez ruchu to przygotowanie wrzeciona na kolejny cykl — cisza jest zamierzona |
| `brak posuwu (sonda/makro?)` | Narzędzie tylko na G0 (sonda / makro) — nie ma skrawania |
| `G55 po starcie operacji (L…)` | G54–G59 tylko na początku pliku, przed pierwszym Txx M6 / M97. Późniejsza zmiana offsetu |
| `S… przekracza max wrzeciona …` | Programowane S wyższe niż `max_rpm` obrabiarki |
| `G68 T12 L40 do G69 T15 L80` | Obrót G68 — T12 włącza, T15 kasuje G69 |
| `G68 T12 L40 bez G69` | Brak G69 przed M30 — kasuj obrót |
| `! …` przy numerze linii | Uwaga programisty z komentarza z `!` |

Pasujące H/D (= numer T) nie dają ostrzeżenia. `T12` i `M6` w dwóch liniach to ta sama wymiana (CAM często tak dzieli).

---

## 5. Ekran czarny i budzenie

- Gaśnie po minucie bez pokrętła i bez nowego USB.
- Budzi: **pokrętło pliku albo mill**, **włożenie pendrive**, klawiatura, mysz, albo opcjonalny przycisk sen/budzenie (jeśli jest).
- **Pierwszy** ruch pokrętła / klawisz / klik tylko budzi — nie przeskakuje pliku i nie drukuje.
- Przyciski **LOAD / SET / RUN przy śpiącym ekranie nic nie robią** (żeby nie strzelić biletu w ciemności). Najpierw obudź pokrętłem. Czwarty przycisk (jeśli jest) gasi ekran i budzi — bez niego kiosk i tak gaśnie po minucie.
- Przycisk zasilania na płytce Pi 5 (albo opcjonalny J2) to **zasilanie**, nie sen. Brak J2: wtyczka USB-C nadal uruchamia kiosk.

---

## 6. Ustawienia (klawiatura / mysz)

Pokrętło **nie otwiera** ustawień.

| Co | Jak |
| --- | --- |
| Otwórz ustawienia | **F2** albo **C**, albo kliknij **PL** / **EN** przy wersji. Tam treść LOAD / SET / RUN |
| Język | **Polski** / **English** — dotyczy ekranu **i** biletu |
| Obrabiarka | Drugie pokrętło, **+** / **−**, albo **Dodaj obrabiarkę…** (nazwa, szybkie m/min, B/C, czas wymiany, opcjonalnie max obr./min, ATC X/Y/Z, offset X/Y/Z i skok min/max) — od tego liczony jest czas cyklu i prostokąt offsetu |
| Zamknij | **Esc**: najpierw formularz obrabiarki, potem ustawienia |

Język i obrabiarka zapamiętują się po restarcie.

---

## 7. Żółty przycisk **AKTUALIZUJ**

- Kiosk **sam się nie aktualizuje**.
- Przycisk pojawia się po starcie albo po obudzeniu czarnego ekranu, gdy w sieci jest nowsza wersja.
- Jeden tap (albo **U**) instaluje i **restartuje** kiosk. Druk działa do momentu tapnięcia.
- Bez sieci druk działa normalnie. Przycisku wtedy nie ma — to nie jest awaria.

---

## 8. Widok 3D i dokumentacja firmowa

- Najlepiej: `.stp` / `.step` **obok** `.nc` na pendrive (albo w podfolderze na tym samym kiju).
- Jeśli kija nie ma modelu, kiosk może czytać firmowy udział (to, co na biurze jest dyskiem **Z:**), **tylko do odczytu**.
- Kostka 3D = rysunek gotowy. Brak kostki = drukuj tekst. Nie czekaj.
- Zły detal na podglądzie izometrii = zły STEP albo zła rewizja — nie drukuj w ciemno.

---

## 9. Gdy coś nie działa

| Objaw | Co spróbować |
| --- | --- |
| Włóż pendrive i pusto | Pliki `.nc` / `.tap` **w korzeniu** kija, FAT32. Wyjmij i włóż ponownie |
| Podgląd nie zgadza się z plikiem | Nadpisany `.nc` o tej samej nazwie? Czekaj na koniec **Czytanie…**. Nie wyrywaj przy **Czytanie pendrive — czekaj** |
| Pokrętło pliku nic nie robi | Ekran czarny? Najpierw obudź. Dalej — serwis (przewody CLK/DT 17/27) |
| Pokrętło mill nic nie robi | Druga obrabiarka w ustawieniach? Przewody 5/6 (złącze 29/31). Serwis |
| Przycisk nie drukuje | Ekran czarny? Obudź pokrętłem. Na dole **Brak papieru** / **Pokrywa otwarta** / **Zacięcie**? Napraw P047. Inaczej: zasilanie, USB |
| Bilet nie tnie | Sprawdź nożyk / kasetę. Serwis |
| Śmieci na papierze / podwójny wydruk | Serwis (CUPS). Status ma być `device:/dev/usb/lp0` |
| Brak kostki 3D | Patrz chip przy kostce: **szuka…** (szuka `.stp`), **liczy…** (rysuje), **brak STEP**, **Z: wył.** (udział), **brak CAD** (serwis). Druk i tak działa |
| Izometria „szara / wypełniona” | Stary rysunek w pamięci — serwis wyczyści `/tmp/fh6parse-models` |
| Ekran po angielsku | **F2** → **Polski**. Najpierw obudź, jeśli czarny |
| **AKTUALIZUJ** „nieudane” | Druk nadal działa. Wołaj serwis — nie instaluj nic z pendrive |

Nie kopiuj programów na kiosk. Nie kasuj nic z udziału firmowego. Nie aktualizuj „z internetu” poza żółtym przyciskiem.

---

## 10. Serwis (nie operator)

Okablowanie GPIO, X11, drukarka `/dev/usb/lp0`, git, udział `//serwer/…` → `/mnt/fh6parse-cad`: **`packaging/LINUX-KIOSK.md`**.
