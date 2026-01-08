import os
import zipfile
import shutil
from datetime import date, timedelta

import cdsapi
import xarray as xr

# ================== НАСТРОЙКИ ==================
OUTPUT_ROOT = r"D:\Xalim\wind_visual\ADS_GASES_test_2026_new"  # базовая папка

LEFT_LON   = 48
RIGHT_LON  = 80
BOTTOM_LAT = 32
TOP_LAT    = 49

DATASET_ID = "cams-global-atmospheric-composition-forecasts"
REQUEST_TYPE = "analysis"              # для “карты за день”
TIMES = ["00:00", "06:00", "12:00", "18:00"]
FORMAT = "netcdf_zip"
LEADTIME_HOUR = "0"


START_DAY = date(2025, 12, 20)
END_DAY   = date(2026, 1, 7)


# 7 параметров
# AERAI = AOD550 (это не UVAI 1:1, но ежедневный аэрозольный индикатор из CAMS)
GASES = {
    "CO":    ("total_column_carbon_monoxide",        "tcco"),
    "NO2":   ("total_column_nitrogen_dioxide",       "tcno2"),
    "SO2":   ("total_column_sulphur_dioxide",        "tcso2"),
    "HCHO":  ("total_column_formaldehyde",           "tchcho"),
    "O3":    ("total_column_ozone",                  "gtco3"),
    "CH4":   ("total_column_methane",                "tc_ch4"), #НЕ НУЖЕН
    "AERAI": ("total_aerosol_optical_depth_550nm",   "aod550"), #НЕ НУЖЕН
}



def extract_first_nc(zip_path: str, extract_dir: str) -> str:
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)
        nc_files = [
            os.path.join(extract_dir, n)
            for n in z.namelist()
            if n.lower().endswith((".nc", ".nc4", ".cdf"))
        ]
    if not nc_files:
        raise RuntimeError("В ZIP не найден NetCDF (.nc/.nc4/.cdf).")
    return nc_files[0]


def pick_dataarray(ds: xr.Dataset, ads_var: str, short_var: str) -> xr.DataArray:
    if short_var in ds.data_vars:
        return ds[short_var]
    if ads_var in ds.data_vars:
        return ds[ads_var]
    if len(ds.data_vars) == 1:
        only = list(ds.data_vars.keys())[0]
        print(f"⚠ Не нашёл {short_var}/{ads_var}. Беру единственную переменную: {only}")
        return ds[only]
    raise RuntimeError(f"Не нашёл переменную. Есть: {list(ds.data_vars.keys())}")


def collapse_to_2d_latlon(da: xr.DataArray) -> xr.DataArray:
    if "longitude" in da.dims and "latitude" in da.dims:
        x_dim, y_dim = "longitude", "latitude"
    elif "lon" in da.dims and "lat" in da.dims:
        x_dim, y_dim = "lon", "lat"
    else:
        raise RuntimeError(f"Не нашёл lon/lat. dims={da.dims}")

    # схлопываем все измерения кроме lon/lat
    for dim in list(da.dims):
        if dim in (x_dim, y_dim):
            continue
        if da.sizes.get(dim, 1) > 1:
            da = da.mean(dim)
        else:
            da = da.isel({dim: 0})

    da = da.squeeze()

    # север сверху
    if da[y_dim].values[0] < da[y_dim].values[-1]:
        da = da.sortby(y_dim, ascending=False)

    da = da.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=False)
    da = da.rio.write_crs("EPSG:4326")
    return da


def safe_remove_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"⚠ Не смог удалить файл {path}: {e}")


def safe_remove_dir(path: str):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=False)
    except Exception as e:
        print(f"⚠ Не смог удалить папку {path}: {e}")


def download_one(day: date, label: str, ads_var: str, short_var: str, client: cdsapi.Client):
    day_str = day.strftime("%Y-%m-%d")

    out_dir = os.path.join(OUTPUT_ROOT, label)
    os.makedirs(out_dir, exist_ok=True)

    out_tif = os.path.join(out_dir, f"{label}_{day_str}_ADS.tif")
    if os.path.exists(out_tif):
        print(f"✔ [{label}] Уже есть: {out_tif}")
        return

    tmp_zip = os.path.join(out_dir, f"_tmp_{label}_{day_str}.zip")
    tmp_dir = os.path.join(out_dir, f"_tmp_{label}_{day_str}")

    area = [TOP_LAT, LEFT_LON, BOTTOM_LAT, RIGHT_LON]  

    request = {
        "date": day_str,
        "type": REQUEST_TYPE,
        "variable": ads_var,
        "time": TIMES,
        "leadtime_hour": LEADTIME_HOUR,
        "format": FORMAT,
        "area": area,
    }

    print(f"\n=== {label} | {day_str} ===")
    client.retrieve(DATASET_ID, request, tmp_zip)

    os.makedirs(tmp_dir, exist_ok=True)

    try:
        nc_path = extract_first_nc(tmp_zip, tmp_dir)

        with xr.open_dataset(nc_path, engine="netcdf4") as ds:
            da = pick_dataarray(ds, ads_var=ads_var, short_var=short_var).load()

        da2d = collapse_to_2d_latlon(da)
        da2d.rio.to_raster(out_tif)
        print(f"✅ [{label}] Готово: {out_tif}")

    finally:
        safe_remove_file(tmp_zip)
        safe_remove_dir(tmp_dir)


def main():
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    client = cdsapi.Client()

    day = START_DAY
    while day <= END_DAY:
        for label, (ads_var, short_var) in GASES.items():
            try:
                download_one(day, label, ads_var, short_var, client)
            except Exception as e:
                print(f"❌ Ошибка [{label}] {day}: {e}")
        day += timedelta(days=1)


if __name__ == "__main__":
    main()
