Файлы main.py, graph.py, rasterimage.py отвечают за генерацию Word-отчёта:

main.py — основной скрипт. Принимает входные параметры (газы, дата, регион, период графика), запускает сбор всех материалов и формирует итоговый .docx.

graph.py — генерация графика временного ряда по выбранному газу (средние значения по региону за последние N дней) и сохранение графика в PNG.

rasterimage.py — генерация картинок по растру:

обзорная карта по республике,

карта с приближением выбранного региона (и подсветкой границ), и сохранение изображений в PNG.

EN

The main.py, graph.py, and rasterimage.py scripts are responsible for generating the Word report:

main.py — the main entry point. It receives input parameters (gases, date, region, chart period), triggers all processing steps, and produces the final .docx report.

graph.py — generates the time-series chart for the selected gas (region mean values for the last N days) and saves it as a PNG.

rasterimage.py — generates raster-based map images:

a country-wide overview map,

a zoomed map highlighting the selected region,
and saves the outputs as PNG files.
