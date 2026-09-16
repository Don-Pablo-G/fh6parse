"""Polish / English UI strings. Tickets stay as printed (not translated)."""

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
        "printing": "Printing {kind}: {name}…",
        "print_kind_full": "full",
        "print_kind_min": "min",
        "printed": "Printed {name}  ({route})",
        "no_file": "No file",
        "busy_update": "Updating…",
        "gpio_off": "GPIO off: {detail}",
        "settings": "Settings",
        "settings_blurb": (
            "Language for this screen. Encoder and print buttons keep working "
            "as on the shop floor."
        ),
        "language": "Language",
        "lang_pl": "Polski",
        "lang_en": "English",
        "settings_keys": "F2 / C / Esc  close     arrows change language",
        "settings_saved": "Saved {path}",
        "settings_save_fail": "Could not save language ({detail})",
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
    },
    "pl": {
        "app_title_kiosk": "Kiosk CNC {version}",
        "app_title_gui": "Raport narzędzi CNC {version}",
        "brand": "NARZĘDZIA CNC",
        "insert_usb": "Włóż pendrive",
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
        "printing": "Drukowanie ({kind}): {name}…",
        "print_kind_full": "pełny",
        "print_kind_min": "skrót",
        "printed": "Wydrukowano {name}  ({route})",
        "no_file": "Brak pliku",
        "busy_update": "Aktualizowanie…",
        "gpio_off": "GPIO wyłączone: {detail}",
        "settings": "Ustawienia",
        "settings_blurb": (
            "Język tego ekranu. Pokrętło i przyciski druku działają jak na hali."
        ),
        "language": "Język",
        "lang_pl": "Polski",
        "lang_en": "English",
        "settings_keys": "F2 / C / Esc  zamknij     strzałki zmieniają język",
        "settings_saved": "Zapisano {path}",
        "settings_save_fail": "Nie udało się zapisać języka ({detail})",
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


def file_count(lang: str, n: int) -> str:
    lang = parse_language(lang, default=GUI_DEFAULT)
    if lang == "pl":
        return f"{n} {_pl_plik(n)}"
    if n == 1:
        return "1 file"
    return f"{n} files"


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


def update_button_label(lang: str, status: Any) -> str:
    new = getattr(status, "new_version", "") or ""
    current = getattr(status, "current_version", "") or ""
    sha = getattr(status, "remote_sha", "") or ""
    if new and new != current:
        return t(lang, "update_to", version=new)
    if sha:
        return t(lang, "update_sha", sha=sha)
    return t(lang, "update")
