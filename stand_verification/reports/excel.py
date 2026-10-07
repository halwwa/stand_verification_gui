import os

from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill


def export_excel(snapshot, filepath, log_callback=None):
    if os.path.exists(filepath):
        wb = load_workbook(filepath)
    else:
        wb = Workbook()
        wb.remove(wb.active)
    layouts = {
        'freq': ('Частота', ['Уст Частота, Гц', 'Изм Частота, Гц', 'Погрешность, Гц',
            'Допуск, Гц', 'Частота ПЧ, кГц', 'Статус', 'Комментарий']),
        'level': ('Уровень', ['Частота, МГц', 'Заданный уровень, дБм', 'Измеренный уровень, дБм',
            'Погрешность, дБ', 'Допуск, дБ', 'Статус', 'Комментарий']),
    }
    fills = {key: PatternFill(start_color=color, end_color=color, fill_type='solid') for key, color in {
        'ok': 'C6EFCE', 'warn': 'FFEB9C', 'fail': 'FFC7CE', 'error': 'FFC7CE'}.items()}
    for name, _ in layouts.values():
        if name in wb.sheetnames:
            del wb[name]
    for key, (name, headers) in layouts.items():
        if key not in snapshot.active_tests:
            continue
        ws = wb.create_sheet(name)
        ws.append(headers)
        for row in snapshot.results.get(key, []):
            ws.append(row)
            if row[5] in fills:
                ws.cell(ws.max_row, 6).fill = fills[row[5]]
            if row[5] == 'error' and row[6]:
                ws.cell(ws.max_row, 7).comment = Comment(str(row[6]), 'MeasurementEngine')
    for name in ('Сводка', 'Тесты', 'Диагностика'):
        if name in wb.sheetnames:
            del wb[name]
    ws = wb.create_sheet('Сводка')
    ws.append(['Итог', 'Причина завершения', 'Выключение выполнено', 'Ошибка выключения'])
    ws.append([snapshot.final_status, snapshot.termination_reason,
               snapshot.shutdown_success, snapshot.shutdown_error])
    ws = wb.create_sheet('Тесты')
    ws.append(['Тест', 'Статус', 'План', 'Точек', 'OK', 'Предупреждений', 'Ошибок'])
    for key, value in snapshot.summary.items():
        if key != 'final_status':
            ws.append([key, value['status'], value['planned'], value['total'], value['ok'],
                       value['warn'], value['fail'] + value['error']])
    ws = wb.create_sheet('Диагностика')
    ws.append(['Диагностика'])
    for diagnostic in snapshot.diagnostics:
        ws.append([str(diagnostic)])
    wb.save(filepath)
    if log_callback:
        log_callback(f'Результаты сохранены: {filepath}')
    return True
