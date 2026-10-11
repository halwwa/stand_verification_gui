import os

from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill


# ============================================================
#                    ПЕРЕВОД СТАТУСОВ
# ============================================================

STATUS_LABELS = {
    'ok':    'Пройден',
    'warn':  'Внимание',
    'fail':  'Провален',
    'error': 'Ошибка',
}


def _fill_for(status):
    return {
        'ok':    'C6EFCE',
        'warn':  'FFEB9C',
        'fail':  'FFC7CE',
        'error': 'FFC7CE',
    }.get(status)


def export_excel(snapshot, filepath, log_callback=None):
    if os.path.exists(filepath):
        wb = load_workbook(filepath)
    else:
        wb = Workbook()
        wb.remove(wb.active)

    layouts = {
        'freq': (
            'Частота',
            ['Уст Частота, Гц', 'Изм Частота, Гц', 'Погрешность, Гц',
             'Допуск, Гц', 'Частота ПЧ, кГц', 'Статус'],
        ),
        'level': (
            'Уровень',
            ['Частота, МГц', 'Заданный уровень, дБм', 'Измеренный уровень, дБм',
             'Погрешность, дБ', 'Допуск, дБ', 'Статус'],
        ),
        'am_noise': (
            'АМ шум',
            ['Уст Частота, Гц', 'Полоса, кГц', 'СКЗ шум, %', 'Допуск, %', 'Статус'],
        ),
        'fm_noise': (
            'ЧМ шум',
            ['Уст Частота, Гц', 'Полоса, кГц', 'СКЗ шум, Гц', 'Допуск, Гц', 'Статус'],
        ),
        'pm_noise': (
            'ФМ шум',
            ['Уст Частота, Гц', 'Полоса, кГц', 'СКЗ шум, рад', 'Допуск, рад', 'Статус'],
        ),
        'am_fm_transition': (
            'Переход АМ↔ЧМ',
            ['Направление', 'Значение +', 'Значение −',
             'Коэффициент', 'Допуск', 'Ед.', 'Статус'],
        ),
    }

    # Удаляем существующие листы, которые будем пересоздавать
    for name, _ in layouts.values():
        if name in wb.sheetnames:
            del wb[name]

    for key, (name, headers) in layouts.items():
        if key not in snapshot.active_tests:
            continue

        ws = wb.create_sheet(name)
        ws.append(headers)

        for row in snapshot.results.get(key, []):
            if key == 'freq':
                values = [
                    row.reference_frequency_hz, row.measured_frequency_hz,
                    row.error_hz, row.tolerance_hz, row.if_frequency_khz,
                    STATUS_LABELS.get(row.status, row.status),
                ]
                status_col = 6
            elif key == 'level':
                values = [
                    row.frequency_mhz, row.set_level_dbm, row.measured_level_dbm,
                    row.error_db, row.tolerance_db,
                    STATUS_LABELS.get(row.status, row.status),
                ]
                status_col = 6
            elif key in ('am_noise', 'fm_noise', 'pm_noise'):
                band_str = f"{row.band_low_khz:g}-{row.band_high_khz:g}"
                values = [
                    row.frequency_mhz * 1_000_000,
                    band_str,
                    row.noise_value, row.tolerance,
                    STATUS_LABELS.get(row.status, row.status),
                ]
                status_col = 5
            else:  # am_fm_transition
                values = [
                    row.direction, row.value_plus, row.value_minus,
                    row.coefficient, row.tolerance, row.unit,
                    STATUS_LABELS.get(row.status, row.status),
                ]
                status_col = 7

            ws.append(values)

            color = _fill_for(row.status)
            if color:
                fill = PatternFill(start_color=color, end_color=color,
                                   fill_type='solid')
                ws.cell(ws.max_row, status_col).fill = fill

    # --- Служебные листы ---
    for name in ('Сводка', 'Тесты', 'Диагностика'):
        if name in wb.sheetnames:
            del wb[name]

    ws = wb.create_sheet('Сводка')
    ws.append(['Итог', 'Причина завершения', 'Выключение выполнено',
               'Ошибка выключения'])
    ws.append([
        snapshot.final_status, snapshot.termination_reason,
        snapshot.shutdown_success, snapshot.shutdown_error,
    ])

    ws = wb.create_sheet('Тесты')
    ws.append(['Тест', 'Статус', 'План', 'Точек', 'OK',
               'Предупреждений', 'Ошибок'])
    for key, value in snapshot.summary.items():
        if key == 'final_status':
            continue
        ws.append([
            key, value['status'], value['planned'], value['total'],
            value['ok'], value['warn'], value['fail'] + value['error'],
        ])

    ws = wb.create_sheet('Диагностика')
    ws.append(['Диагностика'])
    for diagnostic in snapshot.diagnostics:
        ws.append([str(diagnostic)])

    wb.save(filepath)
    if log_callback:
        log_callback(f'Результаты сохранены: {filepath}')
    return True