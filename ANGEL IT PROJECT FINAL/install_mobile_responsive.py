from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
STYLESHEET = ROOT / "static" / "css" / "mobile-responsive.css"
BACKUP_DIR = ROOT / "mobile_responsive_backups"
LINK = '    <link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/mobile-responsive.css\') }}">'


def main() -> int:
    if not TEMPLATES.is_dir():
        print("ERROR: I couldn't find a 'templates' folder next to this script.")
        print("Put this installer in the main ANGEL project folder, alongside app.py.")
        return 1

    if not STYLESHEET.is_file():
        print("ERROR: The stylesheet is missing:")
        print(STYLESHEET)
        print("Extract the patch ZIP into the main ANGEL project folder first.")
        return 1

    html_files = sorted(TEMPLATES.glob("*.html"))
    if not html_files:
        print("ERROR: No .html templates were found in the templates folder.")
        return 1

    BACKUP_DIR.mkdir(exist_ok=True)
    updated = 0
    skipped = 0
    failed = []

    for template in html_files:
        try:
            original = template.read_text(encoding="utf-8")
            if "mobile-responsive.css" in original:
                skipped += 1
                continue

            close_head = original.lower().rfind("</head>")
            if close_head == -1:
                failed.append(template.name + " (no closing </head> tag)")
                continue

            backup = BACKUP_DIR / (template.name + ".original")
            if not backup.exists():
                shutil.copy2(template, backup)

            newline = "\r\n" if "\r\n" in original else "\n"
            insertion = LINK + newline
            revised = original[:close_head] + insertion + original[close_head:]
            template.write_text(revised, encoding="utf-8", newline="")
            updated += 1
        except Exception as exc:  # Keep processing other templates, but report failures.
            failed.append(f"{template.name} ({exc})")

    print(f"Mobile styling installed. Templates updated: {updated}; already linked: {skipped}.")
    print(f"Original template backups are in: {BACKUP_DIR}")
    print("Next: restart Flask and refresh the website on the phone.")
    if failed:
        print("Some templates could not be updated:")
        for item in failed:
            print(" - " + item)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
