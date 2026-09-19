"""Polish / English UI and ticket strings."""

from __future__ import annotations

from typing import Any

LANGS = ("pl", "en")
KIOSK_DEFAULT = "pl"
GUI_DEFAULT = "en"

_ALIASES = {
    "pl": "pl",
    "pl_pl": "pl",
    "polish": "pl",
    "polski": "pl",
    "en": "en",
    "en_us": "en",
    "en_gb": "en",
    "english": "en",
    "angielski": "en",
}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app_title_kiosk": "CNC kiosk {version}",
        "app_title_gui": "CNC Tool Report {version}",
        "brand": "CNC TOOLS",
        "insert_usb": "Insert USB",
        "usb_safe": "Safe to remove",
        "usb_busy": "Reading USB — wait",
        "local_extra": "+{n} local",
        "cad_legend": "3D view ready to print",
        "keys_hint": (
            "FULL / F  full ticket     MIN / M  short ticket     "
            "F2  settings     Esc  window"
        ),
        "update": "UPDATE",
        "update_to": "UPDATE to {version}",
        "update_sha": "UPDATE  {sha}",
        "updating": "UPDATING…",
        "update_status": "v{current} → {new}  ·  tap UPDATE to install and restart",
        "update_available": "Update available  ·  tap UPDATE to install and restart",
        "update_progress": "Updating — will restart the kiosk",
        "update_restarting": "Updated — restarting kiosk",
        "update_frozen": "This install cannot auto-update",
        "update_failed": (
            "Update failed — tap again, or: sudo systemctl restart fh6parse-kiosk"
        ),
        "update_progress_gui": "Updating — the window will restart",
        "update_restarting_gui": "Updated — restarting",
        "update_failed_gui": "Update failed — click UPDATE to try again.",
        "update_available_gui": "Update available  ·  click UPDATE to install and restart",
        "update_status_gui": "v{current} → {new}  ·  click UPDATE to install and restart",
        "printing": "Printing {kind}: {name}…",
        "print_kind_full": "full",
        "print_kind_min": "min",
        "printed": "Printed {name}  ({route})",
        "print_fail": "Print failed: {detail}",
        "print_cover": "Printer cover open",
        "print_paper": "No paper",
        "print_cutter": "Printer jam",
        "print_error": "Printer error",
        "no_file": "No file",
        "busy_update": "Updating…",
        "gpio_off": "GPIO off: {detail}",
        "preview_reading": "Reading…",
        "preview_fail": "Cannot read {name}",
        "preview_no_tools": "no tools",
        "preview_step_yes": "3D ready",
        "preview_step_no": "no 3D",
        "cad_chip_ready": "3D ready",
        "cad_chip_searching": "searching…",
        "cad_chip_rendering": "rendering…",
        "cad_chip_no_step": "no STEP",
        "cad_chip_missing": "no CAD",
        "cad_chip_share_down": "Z: off",
        "settings": "Settings",
        "settings_blurb": (
            "Language, mill (rapids and tool-change time), BCM pins, and ticks "
            "from one tooth valley to the next. Rest is the file; the highlight "
            "changes halfway to the next tooth."
        ),
        "language": "Language",
        "lang_pl": "Polski",
        "lang_en": "English",
        "machine": "Machine",
        "machine_detail": "Rapids {rapid}  ·  tool change {tchg}",
        "machine_add": "Add mill…",
        "machine_add_title": "New mill",
        "machine_name": "Name",
        "machine_rapid": "Rapids (m/min)",
        "machine_rotary": "B/C rapid (deg/min)",
        "machine_tchg": "Tool change (s)",
        "machine_atc": "ATC G53 X Y Z",
        "machine_atc_bc": "ATC G53 B C",
        "machine_g54": "G54 G53 X Y Z",
        "machine_g54_bc": "G54 G53 B C",
        "machine_tool_len": "Tool length (mm)",
        "machine_travel_xy": "Travel Xmin Xmax Ymin Ymax",
        "machine_travel_z": "Travel Zmin Zmax",
        "machine_save": "Save mill",
        "machine_cancel": "Cancel",
        "machine_name_required": "Type a mill name.",
        "machine_bad_number": "Check the numbers.",
        "machine_saved": "Saved mill {name}",
        "machine_default": "Default mill",
        "gpio_pins": "GPIO (BCM numbers, not header pins)",
        "gpio_pi5": "Pi 5 needs python3-lgpio; RPi.GPIO is not supported",
        "pin_clk": "Encoder CLK",
        "pin_dt": "Encoder DT",
        "pin_full": "FULL button",
        "pin_min": "MIN button",
        "encoder_knob": "Knob",
        "encoder_swap_off": "Normal direction",
        "encoder_swap_on": "Reverse",
        "encoder_steps": "Ticks per tooth",
        "encoder_steps_blurb": (
            "GPIO ticks from one rest (the valley) to the next. A 36-tooth "
            "knob is 10° per file; the list changes at about 5°, so a small "
            "wiggle at rest does not move the highlight. Raise this until "
            "rest is stable and one tooth is one file. Keyboard arrows stay "
            "one file per key."
        ),
        "settings_keys": (
            "F2 / C / Esc  close     arrows change language     "
            "+ / −  mill, pins and ticks"
        ),
        "settings_saved": "Saved {path}",
        "settings_save_fail": "Could not save settings ({detail})",
        "lang_chip": "EN",
        "open_nc": "Open NC files…",
        "save_formats": "Save all formats",
        "save_all": "Save all files",
        "output_folder": "Output folder…",
        "step_folders": "STEP folders…",
        "save_next_to_nc": "Save next to each .nc file",
        "preview_print": "Preview / print:",
        "paper_thermal": "80 mm thermal",
        "print_a4": "Print A4…",
        "print_80": "Print 80 mm…",
        "report_preview": "Report preview",
        "gui_idle": "Open NC files, then Print A4 or Print 80 mm.",
        "files_loaded": "{files} loaded",
        "step_ready": "STEP ready {ready}/{total}",
        "cad_ok": "CAD ok",
        "cad_missing": "CAD libraries missing in this build",
        "step_folders_status": "STEP folders: {n}  ({cad})  saved {name}",
        "select_cnc": "Select CNC programs",
        "ft_cnc": "CNC programs",
        "ft_all": "All files",
        "parse_error": "Parse error",
        "cad_not_in_build": "STEP CAD libraries not in this build",
        "step_hint": "STEP next to the NC, or set STEP folders…",
        "choose_step": "STEP / CAD folder (subfolders are searched)",
        "step_add_title": "STEP folders",
        "step_add_body": (
            "Add this folder to the existing list?\n\n"
            "Yes = keep current folders and add this one.\n"
            "No = use only this folder."
        ),
        "out_folder_title": "Report output folder",
        "save_title": "Save",
        "save_all_title": "Save all",
        "print_title": "Print",
        "select_first": "Select a file first.",
        "open_first": "Open NC files first.",
        "wrote_files": "Wrote {n} files in {folder}",
        "wrote_all": "Wrote A4 + 80 mm reports for {n} file(s)",
        "opened_print": "Opened {label} print preview ({name})",
        "company_folder_readonly": (
            "fh6parse never writes or deletes files in the company STEP folder. "
            "Choose a different output folder, or open NC files that are not on that share."
        ),
        "ticket_title_a4": "CNC TOOL REPORT  |  A4",
        "ticket_title_80": "CNC TOOL REPORT",
        "ticket_title_min": "CNC TOOLS MIN",
        "ticket_title_html": "CNC tool report",
        "ticket_title_html_doc": "Tool report {prog}",
        "ticket_80mm": "80 mm",
        "ticket_file": "File:",
        "ticket_file_html": "File",
        "ticket_file_fallback": "file",
        "ticket_program": "Program:",
        "ticket_program_html": "Program",
        "ticket_units": "Units:",
        "ticket_units_html": "Units",
        "ticket_units_mm": "mm (G21)",
        "ticket_units_inch": "inch (G20)",
        "ticket_generated": "Generated:",
        "ticket_printed_html": "Printed",
        "ticket_header_notes": "Header notes:",
        "ticket_programmer_notes": "Programmer notes (!):",
        "ticket_notes_short": "! NOTES",
        "ticket_minz_legend": "Min Z = lowest work Z (G53/G28 ignored).",
        "ticket_time_legend": (
            "Time ≈ programmed moves + cycles ({assumptions}). "
            "+ means missing F or S."
        ),
        "ticket_cycle_legend": (
            "Cycle = that op until M30. The chart under Cycle is each T as a share."
        ),
        "ticket_sim_legend": (
            "Each operation is simulated until M30 "
            "(GOTO, IF, WHILE/DO, M97 L, canned L)."
        ),
        "ticket_m97_legend": "Select a header op by changing M97 P# in main.",
        "ticket_loaded_legend": "[ ] = loaded",
        "ticket_no_ops": "(no operations found)",
        "ticket_no_ops_short": "(no operations)",
        "ticket_no_tools": "(no tools)",
        "ticket_no_tool_changes": "(no tool changes until M30)",
        "ticket_no_txx": "(no Txx M6)",
        "ticket_no_comment": "(no comment)",
        "ticket_no_onumber": "(no O-number)",
        "ticket_share": "Share of cycle",
        "ticket_share_short": "SHARE",
        "ticket_tool_list": "TOOL LIST (deepest Min Z per T)",
        "ticket_each_change": "EACH TOOL CHANGE",
        "ticket_each_change_short": "EACH CHANGE",
        "ticket_each_change_html": "Each tool change",
        "ticket_warning": "WARNING:",
        "ticket_minz": "Min Z",
        "ticket_minz_compact": "MinZ",
        "ticket_time": "Time",
        "ticket_cycle": "Cycle {time}",
        "ticket_na": "n/a",
        "ticket_sign_a4": (
            "Operator: ____________________    Date: ________    Loaded: [ ]"
        ),
        "ticket_sign_op": "Op: ________",
        "ticket_sign_date": "Date: ______",
        "ticket_sign_loaded": "Loaded: [ ]",
        "ticket_sign_loaded_html": "Loaded",
        "ticket_operator": "Operator",
        "ticket_date": "Date",
        "ticket_tools_loaded": "Tools loaded",
        "ticket_load": "Load",
        "ticket_desc": "Description",
        "ticket_ok": "OK",
        "ticket_sub": "Sub",
        "ticket_minz_work": "MinZ=work Z",
        "ticket_minz_work_html": "Min Z = work Z",
        "ticket_time_moves": "Time≈moves {assumptions}",
        "ticket_time_moves_html": "Time ≈ moves {assumptions}",
        "ticket_until_m30": "Until M30; loops/L/M99",
        "ticket_op_m97": "Op = change M97 P#",
        "ticket_rapids": "rapids {rapid}",
        "ticket_tchg": "tool change {tchg}",
        "ticket_g53_frame": "G53 ATC/G54",
        "ticket_no_accel": "no accel",
        "ticket_tchg_compact": "Tchg {tchg}",
        "ticket_g53_compact": "G53",
        "ticket_html_fine": (
            "Min Z is lowest work-coordinate Z (G53/G28 ignored). "
            "Time is programmed motion and canned cycles (approx; {assumptions}). "
            "Cycle is the sum for that operation until M30. The chart under Cycle "
            "is each T as a share of that cycle. Each Txx M6 also shows its own %. "
            "A trailing + means missing F or S. Each operation is simulated until "
            "M30 (GOTO, IF, WHILE/DO, M97 L, canned L). Select a header op by "
            "changing M97 P# in main."
        ),
        "ticket_print": "Print",
        "ticket_print_hint_a4": (
            "Print dialog: A4, portrait, 100% scale, headers and footers off."
        ),
        "ticket_print_hint_80": (
            "Print dialog: select the 80 mm printer, paper 80 mm, 100% scale, "
            "headers/footers off, do not fit to A4."
        ),
        "ticket_step_alt": "STEP isometric",
        "ticket_warn_g95_next": "G95 still active (feed per rev); set G94",
        "ticket_warn_g95_end": "G95 still active at M30; set G94",
        "ticket_warn_no_motion": "no motion after tool change",
        "ticket_warn_no_feed": "no feed (probe/macro?)",
        "ticket_warn_mismatch": "{offset} does not match {tool}",
        "ticket_g54_heading": "G54 origin in G53 mm",
        "ticket_g54_sw": "SW {xy}",
        "ticket_g54_se": "SE {xy}",
        "ticket_g54_ne": "NE {xy}",
        "ticket_g54_nw": "NW {xy}",
        "ticket_g54_center": "Center {xy}",
        "ticket_g54_z": "G54 Z G53 {z0} … {z1} mm",
        "ticket_g54_too_big": "Work XY larger than machine travel.",
        "ticket_g54_out": "Stored G54 is outside this box.",
        "ticket_g54_ok": "Stored G54 is inside this box.",
        "ticket_g54_alt": "G54 origin box",
    },
    "pl": {
        "app_title_kiosk": "Kiosk CNC {version}",
        "app_title_gui": "Raport narzędzi CNC {version}",
        "brand": "NARZĘDZIA CNC",
        "insert_usb": "Włóż pendrive",
        "usb_safe": "Można wyjąć",
        "usb_busy": "Czytanie pendrive — czekaj",
        "local_extra": "+{n} lokalne",
        "cad_legend": "Widok 3D gotowy do druku",
        "keys_hint": (
            "FULL / F  pełny wydruk     MIN / M  krótki     "
            "F2  ustawienia     Esc  okno"
        ),
        "update": "AKTUALIZUJ",
        "update_to": "AKTUALIZUJ do {version}",
        "update_sha": "AKTUALIZUJ  {sha}",
        "updating": "AKTUALIZOWANIE…",
        "update_status": (
            "v{current} → {new}  ·  naciśnij AKTUALIZUJ, potem restart"
        ),
        "update_available": (
            "Aktualizacja dostępna  ·  naciśnij AKTUALIZUJ, potem restart"
        ),
        "update_progress": "Aktualizowanie — kiosk uruchomi się ponownie",
        "update_restarting": "Zaktualizowano — restart kiosku",
        "update_frozen": "Ta instalacja nie aktualizuje się sama",
        "update_failed": (
            "Aktualizacja nieudana — naciśnij jeszcze raz, albo: "
            "sudo systemctl restart fh6parse-kiosk"
        ),
        "update_progress_gui": "Aktualizowanie — okno uruchomi się ponownie",
        "update_restarting_gui": "Zaktualizowano — restart",
        "update_failed_gui": "Aktualizacja nieudana — kliknij AKTUALIZUJ ponownie.",
        "update_available_gui": (
            "Aktualizacja dostępna  ·  kliknij AKTUALIZUJ, potem restart"
        ),
        "update_status_gui": (
            "v{current} → {new}  ·  kliknij AKTUALIZUJ, potem restart"
        ),
        "printing": "Drukowanie ({kind}): {name}…",
        "print_kind_full": "pełny",
        "print_kind_min": "skrót",
        "printed": "Wydrukowano {name}  ({route})",
        "print_fail": "Druk nieudany: {detail}",
        "print_cover": "Pokrywa otwarta",
        "print_paper": "Brak papieru",
        "print_cutter": "Zacięcie drukarki",
        "print_error": "Błąd drukarki",
        "no_file": "Brak pliku",
        "busy_update": "Aktualizowanie…",
        "gpio_off": "GPIO wyłączone: {detail}",
        "preview_reading": "Czytanie…",
        "preview_fail": "Nie można odczytać {name}",
        "preview_no_tools": "brak narzędzi",
        "preview_step_yes": "3D gotowe",
        "preview_step_no": "brak 3D",
        "cad_chip_ready": "3D gotowe",
        "cad_chip_searching": "szuka…",
        "cad_chip_rendering": "liczy…",
        "cad_chip_no_step": "brak STEP",
        "cad_chip_missing": "brak CAD",
        "cad_chip_share_down": "Z: wył.",
        "settings": "Ustawienia",
        "settings_blurb": (
            "Język, obrabiarka (szybkie i czas wymiany narzędzia), piny BCM "
            "i impulsy od jednej doliny zęba do następnej. Spoczynek to plik; "
            "podświetlenie zmienia się w połowie drogi do następnego zęba."
        ),
        "language": "Język",
        "lang_pl": "Polski",
        "lang_en": "English",
        "machine": "Obrabiarka",
        "machine_detail": "Szybkie {rapid}  ·  wymiana narzędzia {tchg}",
        "machine_add": "Dodaj obrabiarkę…",
        "machine_add_title": "Nowa obrabiarka",
        "machine_name": "Nazwa",
        "machine_rapid": "Szybkie (m/min)",
        "machine_rotary": "B/C szybkie (stopnie/min)",
        "machine_tchg": "Wymiana narzędzia (s)",
        "machine_atc": "ATC G53 X Y Z",
        "machine_atc_bc": "ATC G53 B C",
        "machine_g54": "G54 G53 X Y Z",
        "machine_g54_bc": "G54 G53 B C",
        "machine_tool_len": "Długość narzędzia (mm)",
        "machine_travel_xy": "Skok Xmin Xmax Ymin Ymax",
        "machine_travel_z": "Skok Zmin Zmax",
        "machine_save": "Zapisz obrabiarkę",
        "machine_cancel": "Anuluj",
        "machine_name_required": "Wpisz nazwę obrabiarki.",
        "machine_bad_number": "Sprawdź liczby.",
        "machine_saved": "Zapisano obrabiarkę {name}",
        "machine_default": "Domyślna obrabiarka",
        "gpio_pins": "GPIO (numery BCM, nie piny złącza)",
        "gpio_pi5": "Pi 5 wymaga python3-lgpio; RPi.GPIO nie jest obsługiwane",
        "pin_clk": "Enkoder CLK",
        "pin_dt": "Enkoder DT",
        "pin_full": "Przycisk FULL",
        "pin_min": "Przycisk MIN",
        "encoder_knob": "Pokrętło",
        "encoder_swap_off": "Kierunek normalny",
        "encoder_swap_on": "Odwróć",
        "encoder_steps": "Impulsy na ząb",
        "encoder_steps_blurb": (
            "Impulsy GPIO od spoczynku (dolina) do następnego. Pokrętło "
            "36-zębne to 10° na plik; lista zmienia się przy ok. 5°, więc "
            "lekkie drgnięcie w dolinie nie zmienia podświetlenia. Podnieś, "
            "aż spoczynek będzie stabilny i jeden ząb to jeden plik. "
            "Strzałki klawiatury nadal to jeden plik na klawisz."
        ),
        "settings_keys": (
            "F2 / C / Esc  zamknij     strzałki zmieniają język     "
            "+ / −  obrabiarka, piny i impulsy"
        ),
        "settings_saved": "Zapisano {path}",
        "settings_save_fail": "Nie udało się zapisać ustawień ({detail})",
        "lang_chip": "PL",
        "open_nc": "Otwórz pliki NC…",
        "save_formats": "Zapisz wszystkie formaty",
        "save_all": "Zapisz wszystkie pliki",
        "output_folder": "Folder zapisu…",
        "step_folders": "Foldery STEP…",
        "save_next_to_nc": "Zapis obok każdego pliku .nc",
        "preview_print": "Podgląd / druk:",
        "paper_thermal": "80 mm termiczny",
        "print_a4": "Drukuj A4…",
        "print_80": "Drukuj 80 mm…",
        "report_preview": "Podgląd raportu",
        "gui_idle": "Otwórz pliki NC, potem Drukuj A4 lub Drukuj 80 mm.",
        "files_loaded": "Wczytano {files}",
        "step_ready": "STEP gotowy {ready}/{total}",
        "cad_ok": "CAD OK",
        "cad_missing": "Brak bibliotek CAD w tej wersji",
        "step_folders_status": "Foldery STEP: {n}  ({cad})  zapis {name}",
        "select_cnc": "Wybierz programy CNC",
        "ft_cnc": "Programy CNC",
        "ft_all": "Wszystkie pliki",
        "parse_error": "Błąd analizy",
        "cad_not_in_build": "Biblioteki CAD STEP nie są w tej wersji",
        "step_hint": "STEP obok NC albo ustaw Foldery STEP…",
        "choose_step": "Folder STEP / CAD (przeszukiwane są podfoldery)",
        "step_add_title": "Foldery STEP",
        "step_add_body": (
            "Dodać ten folder do listy?\n\n"
            "Tak = zostaw obecne foldery i dodaj ten.\n"
            "Nie = użyj tylko tego folderu."
        ),
        "out_folder_title": "Folder raportów",
        "save_title": "Zapis",
        "save_all_title": "Zapisz wszystkie",
        "print_title": "Druk",
        "select_first": "Najpierw wybierz plik.",
        "open_first": "Najpierw otwórz pliki NC.",
        "wrote_files": "Zapisano {n} plików w {folder}",
        "wrote_all": "Zapisano raporty A4 i 80 mm dla {n} plików",
        "opened_print": "Otwarto podgląd wydruku {label} ({name})",
        "company_folder_readonly": (
            "fh6parse nigdy nie zapisuje ani nie usuwa plików w firmowym folderze STEP. "
            "Wybierz inny folder zapisu albo otwórz NC spoza tego udziału."
        ),
        "ticket_title_a4": "RAPORT NARZĘDZI CNC  |  A4",
        "ticket_title_80": "RAPORT NARZĘDZI CNC",
        "ticket_title_min": "NARZĘDZIA CNC MIN",
        "ticket_title_html": "Raport narzędzi CNC",
        "ticket_title_html_doc": "Raport narzędzi {prog}",
        "ticket_80mm": "80 mm",
        "ticket_file": "Plik:",
        "ticket_file_html": "Plik",
        "ticket_file_fallback": "plik",
        "ticket_program": "Program:",
        "ticket_program_html": "Program",
        "ticket_units": "Jednostki:",
        "ticket_units_html": "Jednostki",
        "ticket_units_mm": "mm (G21)",
        "ticket_units_inch": "cale (G20)",
        "ticket_generated": "Wygenerowano:",
        "ticket_printed_html": "Wydrukowano",
        "ticket_header_notes": "Uwagi nagłówka:",
        "ticket_programmer_notes": "Uwagi programisty (!):",
        "ticket_notes_short": "! UWAGI",
        "ticket_minz_legend": "Min Z = najniższe Z robocze (G53/G28 pomijane).",
        "ticket_time_legend": (
            "Czas ≈ ruchy i cykle programowane ({assumptions}). "
            "+ oznacza brak F lub S."
        ),
        "ticket_cycle_legend": (
            "Cykl = ta operacja do M30. Wykres pod Cyklem to udział każdego T."
        ),
        "ticket_sim_legend": (
            "Każda operacja liczona do M30 "
            "(GOTO, IF, WHILE/DO, M97 L, cykle L)."
        ),
        "ticket_m97_legend": "Wybór operacji z nagłówka: zmień M97 P# w main.",
        "ticket_loaded_legend": "[ ] = załadowano",
        "ticket_no_ops": "(brak operacji)",
        "ticket_no_ops_short": "(brak operacji)",
        "ticket_no_tools": "(brak narzędzi)",
        "ticket_no_tool_changes": "(brak wymian do M30)",
        "ticket_no_txx": "(brak Txx M6)",
        "ticket_no_comment": "(brak komentarza)",
        "ticket_no_onumber": "(brak numeru O)",
        "ticket_share": "Udział cyklu",
        "ticket_share_short": "UDZIAŁ",
        "ticket_tool_list": "LISTA NARZĘDZI (najniższe Min Z na T)",
        "ticket_each_change": "KAŻDA WYMIANA NARZĘDZIA",
        "ticket_each_change_short": "KAŻDA WYMIANA",
        "ticket_each_change_html": "Każda wymiana narzędzia",
        "ticket_warning": "UWAGA:",
        "ticket_minz": "Min Z",
        "ticket_minz_compact": "MinZ",
        "ticket_time": "Czas",
        "ticket_cycle": "Cykl {time}",
        "ticket_na": "n/d",
        "ticket_sign_a4": (
            "Operator: ____________________    Data: ________    Załad.: [ ]"
        ),
        "ticket_sign_op": "Op: ________",
        "ticket_sign_date": "Data: ______",
        "ticket_sign_loaded": "Załad.: [ ]",
        "ticket_sign_loaded_html": "Załadowano",
        "ticket_operator": "Operator",
        "ticket_date": "Data",
        "ticket_tools_loaded": "Narzędzia załadowane",
        "ticket_load": "Załad.",
        "ticket_desc": "Opis",
        "ticket_ok": "OK",
        "ticket_sub": "Sub",
        "ticket_minz_work": "MinZ=Z robocze",
        "ticket_minz_work_html": "Min Z = Z robocze",
        "ticket_time_moves": "Czas≈ruchy {assumptions}",
        "ticket_time_moves_html": "Czas ≈ ruchy {assumptions}",
        "ticket_until_m30": "Do M30; pętle/L/M99",
        "ticket_op_m97": "Op = zmień M97 P#",
        "ticket_rapids": "szybkie {rapid}",
        "ticket_tchg": "wymiana narzędzia {tchg}",
        "ticket_g53_frame": "G53 ATC/G54",
        "ticket_no_accel": "bez przysp.",
        "ticket_tchg_compact": "Wym. {tchg}",
        "ticket_g53_compact": "G53",
        "ticket_html_fine": (
            "Min Z to najniższe Z we współrzędnych detalu (G53/G28 pomijane). "
            "Czas to ruchy programowane i cykle wiertarskie (ok.; {assumptions}). "
            "Cykl to suma tej operacji do M30. Wykres pod Cyklem to udział "
            "każdego T w tym cyklu. Każde Txx M6 ma też własny %. "
            "Plus na końcu oznacza brak F lub S. Każda operacja liczona do "
            "M30 (GOTO, IF, WHILE/DO, M97 L, cykle L). Wybór operacji z "
            "nagłówka: zmień M97 P# w main."
        ),
        "ticket_print": "Drukuj",
        "ticket_print_hint_a4": (
            "Druk: A4, pion, skala 100%, bez nagłówków i stopek."
        ),
        "ticket_print_hint_80": (
            "Druk: drukarka 80 mm, papier 80 mm, skala 100%, bez nagłówków, "
            "nie dopasowuj do A4."
        ),
        "ticket_step_alt": "Izometria STEP",
        "ticket_warn_g95_next": "G95 nadal aktywne (posuw/obr.); ustaw G94",
        "ticket_warn_g95_end": "G95 nadal aktywne przy M30; ustaw G94",
        "ticket_warn_no_motion": "brak ruchu po wymianie narzędzia",
        "ticket_warn_no_feed": "brak posuwu (sonda/makro?)",
        "ticket_warn_mismatch": "{offset} nie zgadza się z {tool}",
        "ticket_g54_heading": "Punkt zerowy G54 w G53 mm",
        "ticket_g54_sw": "SW {xy}",
        "ticket_g54_se": "SE {xy}",
        "ticket_g54_ne": "NE {xy}",
        "ticket_g54_nw": "NW {xy}",
        "ticket_g54_center": "Środek {xy}",
        "ticket_g54_z": "G54 Z G53 {z0} … {z1} mm",
        "ticket_g54_too_big": "Obróbka XY większa niż skok obrabiarki.",
        "ticket_g54_out": "Zapisane G54 jest poza tym prostokątem.",
        "ticket_g54_ok": "Zapisane G54 jest wewnątrz tego prostokąta.",
        "ticket_g54_alt": "Prostokąt punktu zerowego G54",
    },
}


def parse_language(raw: str | None, *, default: str = GUI_DEFAULT) -> str:
    """Map ini / UI values to pl or en. Empty uses default."""
    fallback = default if default in LANGS else GUI_DEFAULT
    s = (raw or "").strip().lower().replace("-", "_")
    if not s:
        return fallback
    if s in _ALIASES:
        return _ALIASES[s]
    base = s.split("_", 1)[0]
    if base in LANGS:
        return base
    return fallback


def t(lang: str, key: str, **kwargs: Any) -> str:
    lang = parse_language(lang, default=GUI_DEFAULT)
    catalog = STRINGS[lang]
    text = catalog.get(key) or STRINGS["en"][key]
    if kwargs:
        return text.format(**kwargs)
    return text


CAD_STATUS_KEYS = {
    "ready": "cad_chip_ready",
    "searching": "cad_chip_searching",
    "rendering": "cad_chip_rendering",
    "no_step": "cad_chip_no_step",
    "cad_missing": "cad_chip_missing",
    "share_down": "cad_chip_share_down",
    "idle": "cad_legend",
}


def cad_status_label(lang: str, status: str) -> str:
    key = CAD_STATUS_KEYS.get(status, "cad_chip_no_step")
    return t(lang, key)


def file_count(lang: str, n: int) -> str:
    lang = parse_language(lang, default=GUI_DEFAULT)
    if lang == "pl":
        return f"{n} {_pl_plik(n)}"
    if n == 1:
        return "1 file"
    return f"{n} files"


def tool_count(lang: str, n: int) -> str:
    lang = parse_language(lang, default=GUI_DEFAULT)
    n = int(n)
    if lang == "pl":
        return f"{n} {_pl_narzedzie(n)}"
    if n == 1:
        return "1 tool"
    return f"{n} tools"


def usb_count(n: int) -> str:
    return f"{n} USB"


def _pl_plik(n: int) -> str:
    n = abs(int(n))
    if n == 1:
        return "plik"
    if 12 <= (n % 100) <= 14:
        return "plików"
    if 2 <= (n % 10) <= 4:
        return "pliki"
    return "plików"


def _pl_narzedzie(n: int) -> str:
    n = abs(int(n))
    if n == 1:
        return "narzędzie"
    if 12 <= (n % 100) <= 14:
        return "narzędzi"
    if 2 <= (n % 10) <= 4:
        return "narzędzia"
    return "narzędzi"


def update_button_label(lang: str, status: Any) -> str:
    new = getattr(status, "new_version", "") or ""
    current = getattr(status, "current_version", "") or ""
    sha = getattr(status, "remote_sha", "") or ""
    if new and new != current:
        return t(lang, "update_to", version=new)
    if sha:
        return t(lang, "update_sha", sha=sha)
    return t(lang, "update")
