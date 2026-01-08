import os
from datetime import date, timedelta
import requests

import xarray as xr
import rioxarray  # чтобы заработал .rio у DataArray


# ===================== НАСТРОЙКИ =====================

OUTPUT_DIR = r"D:\Xalim\wind_visual\ADS_GASES_test_2026_new\NOA_TEMP"

START_DAY = date(2025, 12, 19)
NUM_DAYS = 20
RUN_HOUR = 0  # 00Z

FORECAST_HOURS = list(range(0, 24))

LEFT_LON   = 48
RIGHT_LON  = 80
BOTTOM_LAT = 32
TOP_LAT    = 48

BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"

os.makedirs(OUTPUT_DIR, exist_ok=True)


def build_gfs_url(day: date, run_hour: int, forecast_hour: int):
    ymd = day.strftime("%Y%m%d")
    hh = f"{run_hour:02d}"
    fff = f"{forecast_hour:03d}"

    gfs_file = f"gfs.t{hh}z.pgrb2.0p25.f{fff}"
    directory = f"/gfs.{ymd}/{hh}/atmos"

    params = {
        "file": gfs_file,
        "lev_2_m_above_ground": "on",
        "var_TMP": "on",
        "subregion": "",
        "leftlon": str(LEFT_LON),
        "rightlon": str(RIGHT_LON),
        "toplat": str(TOP_LAT),
        "bottomlat": str(BOTTOM_LAT),
        "dir": directory,
    }

    return BASE_URL, params


def convert_grib_to_tif_cfgrib(in_path: str, out_path: str):
    print(f"    -> Конвертация в TIF: {os.path.basename(out_path)}")

    try:
        ds = xr.open_dataset(in_path, engine="cfgrib")
    except Exception as e:
        print(f"    ❌ Не удалось открыть GRIB через cfgrib: {e}")
        return

    if not ds.data_vars:
        print("    ❌ Нет переменных в GRIB, пропускаем.")
        return

    var_name = list(ds.data_vars.keys())[0]
    da = ds[var_name].squeeze()

    da = da - 273.15
    da.attrs["units"] = "Celsius"

    if not da.rio.crs:
        da = da.rio.write_crs("EPSG:4326")

    try:
        da.rio.to_raster(out_path)
        print(f"    ✅ TIF сохранён: {out_path}")
    except Exception as e:
        print(f"    ❌ Ошибка записи TIF: {e}")


def download_gfs_temp2m_for_day(day: date):
    print(f"\n=== {day} (run {RUN_HOUR:02d}Z) ===")
    date_str = day.strftime("%Y%m%d")

    for fh in FORECAST_HOURS:
        hour_str = f"{fh:02d}"
        fff = f"{fh:03d}"

        print(f"  --- f{fff} ({hour_str}:00) ---")

        base_url, params = build_gfs_url(day, RUN_HOUR, fh)

        tif_name = f"{date_str}_{hour_str}_GFS_temp.tif"
        tif_path = os.path.join(OUTPUT_DIR, tif_name)

        if os.path.exists(tif_path):
            print(f"    ✔ TIF уже существует: {tif_path}")
            continue

        tmp_grib_name = f"tmp_{date_str}_f{fff}.grib2"
        tmp_grib_path = os.path.join(OUTPUT_DIR, tmp_grib_name)

        print("    -> Скачиваем GRIB2...")
        resp = requests.get(base_url, params=params, stream=True)

        if resp.status_code != 200:
            print(f"    ❌ HTTP {resp.status_code}: {resp.text[:200]}")
            continue

        with open(tmp_grib_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"    ✔ GRIB временно сохранён: {tmp_grib_path}")

        try:
            convert_grib_to_tif_cfgrib(tmp_grib_path, tif_path)
        finally:
            # Удаляем временный GRIB
            if os.path.exists(tmp_grib_path):
                try:
                    os.remove(tmp_grib_path)
                    print(f"    🗑 Удалён GRIB: {tmp_grib_path}")
                except Exception as e:
                    print(f"    ⚠ Ошибка удаления GRIB: {e}")



def cleanup_output_folder():

    print("\n=== Финальная очистка OUTPUT_DIR ===")

    for fname in os.listdir(OUTPUT_DIR):
        fpath = os.path.join(OUTPUT_DIR, fname)

        # Оставляем только TIFF
        if fname.lower().endswith(".tif"):
            continue

        # Удаляем всё остальное
        try:
            os.remove(fpath)
            print(f"    🗑 Удалено: {fname}")
        except Exception as e:
            print(f"    ⚠ Ошибка удаления {fname}: {e}")

def main():
    print(f"OUTPUT_DIR: {OUTPUT_DIR}")
    for i in range(NUM_DAYS):
        day = START_DAY + timedelta(days=i)
        download_gfs_temp2m_for_day(day)

    cleanup_output_folder()
if __name__ == "__main__":
    main()
