import os
from datetime import date, timedelta
import requests

import xarray as xr
import rioxarray  # чтобы заработал .rio у DataArray

OUTPUT_DIR = r"D:\Xalim\wind_visual\ADS_GASES_test_2026_new\NOA_TEMP_WIND"

# bbox координаты
LEFT_LON   = 48
RIGHT_LON  = 80
BOTTOM_LAT = 32
TOP_LAT    = 48

# Стартовая дата и количество дней
START_DAY = date(2025, 12, 19)
NUM_DAYS = 20

# Какой запуск модели использовать (00Z, 06Z, 12Z, 18Z)
RUN_HOUR = 0  # 00Z

# Какие часы прогноза брать (0..23 = все часы первых суток)
FORECAST_HOURS = list(range(0, 24))

# Базовый URL GFS 0.25 (NOMADS grib-filter)
BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def build_gfs_url(day: date, run_hour: int, forecast_hour: int, component: str):
    """
    component: 'U' или 'V'
    Собираем URL и параметры для запроса GFS 0.25:
    - gfs.YYYYMMDD/run_hour
    - gfs.t{HH}z.pgrb2.0p25.f{forecast_hour:03d}
    - параметр UGRD или VGRD на 10 m above ground, bbox.
    """
    assert component in ("U", "V")

    ymd = day.strftime("%Y%m%d")
    hh = f"{run_hour:02d}"
    fff = f"{forecast_hour:03d}"

    gfs_file = f"gfs.t{hh}z.pgrb2.0p25.f{fff}"
    directory = f"/gfs.{ymd}/{hh}/atmos"

    params = {
        "file": gfs_file,
        "lev_10_m_above_ground": "on",
        "subregion": "",
        "leftlon": str(LEFT_LON),
        "rightlon": str(RIGHT_LON),
        "toplat": str(TOP_LAT),
        "bottomlat": str(BOTTOM_LAT),
        "dir": directory,
    }

    if component == "U":
        params["var_UGRD"] = "on"
    else:
        params["var_VGRD"] = "on"

    return BASE_URL, params


def convert_grib_to_tif_cfgrib(in_path: str, out_path: str):
    """
    Конвертация одного GRIB2 в GeoTIFF через xarray + cfgrib + rioxarray.
    Оставляем значения в м/с.
    """
    print(f"      -> Конвертация в TIF: {os.path.basename(out_path)}")

    try:
        ds = xr.open_dataset(in_path, engine="cfgrib")
    except Exception as e:
        print(f"      ❌ Не удалось открыть GRIB через cfgrib: {e}")
        return

    if not ds.data_vars:
        print("      ❌ В датасете нет переменных, пропускаем.")
        return

    # Берём первую переменную (обычно ugrd10m или vgrd10m)
    var_name = list(ds.data_vars.keys())[0]
    da = ds[var_name].squeeze()

    # CRS (широта/долгота)
    if not da.rio.crs:
        da = da.rio.write_crs("EPSG:4326")

    try:
        da.rio.to_raster(out_path)
        print(f"      ✅ TIF сохранён: {out_path}")
    except Exception as e:
        print(f"      ❌ Ошибка при записи GeoTIFF: {e}")


def download_gfs_wind10m_for_day(day: date):

    print(f"\n=== Обработка даты {day} (run {RUN_HOUR:02d}Z) ===")
    date_str = day.strftime("%Y%m%d")

    for fh in FORECAST_HOURS:
        fff = f"{fh:03d}"
        hour_str = f"{fh:02d}"
        print(f"  --- Час прогноза f{fff} ({hour_str}:00) ---")

        for component in ("U", "V"):


            suffix = "U_GFS" if component == "U" else "V_GFS"
            tif_name = f"{date_str}_{hour_str}_{suffix}.tif"
            tif_path = os.path.join(OUTPUT_DIR, tif_name)

            if os.path.exists(tif_path):
                print(f"    ✔ {component}: TIF уже существует, пропускаем: {tif_path}")
                continue

            base_url, params = build_gfs_url(day, RUN_HOUR, fh, component=component)

            tmp_grib_name = f"tmp_{component}_{date_str}_f{fff}.grib2"
            tmp_grib_path = os.path.join(OUTPUT_DIR, tmp_grib_name)

            print(f"    -> Скачиваем GRIB2 ({component} 10m)...")
            resp = requests.get(base_url, params=params, stream=True)

            if resp.status_code != 200:
                print(f"    ❌ Ошибка HTTP для {component} {resp.status_code}: {resp.text[:200]}")
                continue

            with open(tmp_grib_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            print(f"      ✔ GRIB {component} временно сохранён: {tmp_grib_path}")

            try:
                convert_grib_to_tif_cfgrib(tmp_grib_path, tif_path)
            finally:
                if os.path.exists(tmp_grib_path):
                    os.remove(tmp_grib_path)




def cleanup_output_folder():

    print("\n=== Финальная очистка OUTPUT_DIR ===")
    for fname in os.listdir(OUTPUT_DIR):
        fpath = os.path.join(OUTPUT_DIR, fname)

        # Оставляем только TIFF
        if fname.lower().endswith(".tif"):
            continue

        # Удаляем всё остальное
        if os.path.isfile(fpath):
            try:
                os.remove(fpath)
                print(f"    🗑 Удалено: {fname}")
            except Exception as e:
                print(f"    ⚠ Ошибка удаления {fname}: {e}")


def main():
    print(f"OUTPUT_DIR: {OUTPUT_DIR}")

    for i in range(NUM_DAYS):
        day = START_DAY + timedelta(days=i)
        try:
            download_gfs_wind10m_for_day(day)
        except Exception as e:
            print(f"  ❌ Общая ошибка для {day}: {e}")

    # В конце подчистим всё, кроме TIF
    cleanup_output_folder()


if __name__ == "__main__":
    main()
