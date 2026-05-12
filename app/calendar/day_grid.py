"""Tagesraster-Generator für den Kalender (Deutsch, mit KW-Spalte)."""
import calendar
import html as html_mod

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def generate_day_grid(month: int, year: int) -> str:
    """Erzeugt das Tagesraster-HTML für einen Monat.

    Args:
        month: Monat (1=Januar, 12=Dezember).
        year: Jahr (z.B. 2026).

    Returns:
        HTML-String mit dem Tagesraster.
    """
    cal = calendar.Calendar(firstweekday=0)  # Montag
    weeks = list(cal.monthdayscalendar(year, month))
    cal_weeks = list(cal.monthdatescalendar(year, month))

    parts = ['<div class="day-grid">']

    # Kopfzeile: KW + Wochentage
    parts.append('<div class="weekday-row">')
    parts.append('<span class="kw-header">KW</span>')
    for day_name in WEEKDAYS:
        parts.append(f"<span>{html_mod.escape(day_name)}</span>")
    parts.append("</div>")

    # Wochen-Zeilen
    for week_idx, week in enumerate(weeks):
        parts.append('<div class="week-row">')
        # KW-Nummer
        kw_num = ""
        if week_idx < len(cal_weeks):
            kw_num = str(cal_weeks[week_idx][0].isocalendar()[1])
        parts.append(f'<span class="kw">{html_mod.escape(kw_num)}</span>')

        for day_idx, day in enumerate(week):
            if day == 0:
                parts.append('<span class="day empty"></span>')
            else:
                weekend = "weekend" if day_idx >= 5 else ""
                parts.append(
                    f'<span class="day {weekend}">'
                    f'{html_mod.escape(str(day))}'
                    f"</span>"
                )
        parts.append("</div>")

    parts.append("</div>")
    return "\n".join(parts)
