import argparse
import csv
from pathlib import Path

import numpy as np


INPUT_COLUMNS = [
    "IGSS_uA_0h", "IGSS_uA_24h",
    "IDSS_uA_0h", "IDSS_uA_24h",
    "VGSth_V_0h", "VGSth_V_24h",
    "RDSon_mOhm_0h", "RDSon_mOhm_24h"
]

TARGET_COLUMNS = [
    "IGSS_uA_168h",
    "IDSS_uA_168h",
    "VGSth_V_168h",
    "RDSon_mOhm_168h"
]

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = BASE_DIR / "models" / "module_b_forecast.npz"


def load_rows(path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = load_rows(args.csv_path)
    missing = [column for column in INPUT_COLUMNS + TARGET_COLUMNS if column not in rows[0]]
    if missing:
        raise ValueError("Missing required training columns: " + ", ".join(missing))

    train = [row for row in rows if row.get("split") == "train"]
    test = [row for row in rows if row.get("split") == "test"]
    if not train or not test:
        raise ValueError("The CSV must contain train and test rows.")

    x_train = np.array([[float(row[column]) for column in INPUT_COLUMNS] for row in train], dtype=np.float64)
    y_train = np.array([[float(row[column]) for column in TARGET_COLUMNS] for row in train], dtype=np.float64)
    x_test = np.array([[float(row[column]) for column in INPUT_COLUMNS] for row in test], dtype=np.float64)
    y_test = np.array([[float(row[column]) for column in TARGET_COLUMNS] for row in test], dtype=np.float64)

    x_mean = x_train.mean(axis=0)
    x_scale = x_train.std(axis=0)
    x_scale[x_scale == 0] = 1.0
    y_mean = y_train.mean(axis=0)
    y_scale = y_train.std(axis=0)
    y_scale[y_scale == 0] = 1.0

    x_train_scaled = (x_train - x_mean) / x_scale
    y_train_scaled = (y_train - y_mean) / y_scale
    design = np.column_stack([np.ones(len(x_train_scaled)), x_train_scaled])

    regularization = 1e-6 * np.eye(design.shape[1])
    regularization[0, 0] = 0
    coefficients = np.linalg.solve(
        design.T @ design + regularization,
        design.T @ y_train_scaled
    )

    test_design = np.column_stack([
        np.ones(len(x_test)),
        (x_test - x_mean) / x_scale
    ])
    predictions = test_design @ coefficients
    predictions = predictions * y_scale + y_mean

    rmse = np.sqrt(np.mean((predictions - y_test) ** 2, axis=0))
    mae = np.mean(np.abs(predictions - y_test), axis=0)
    ss_res = np.sum((y_test - predictions) ** 2, axis=0)
    ss_tot = np.sum((y_test - y_test.mean(axis=0)) ** 2, axis=0)
    r2 = 1 - (ss_res / ss_tot)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.output,
        coefficients=coefficients,
        input_mean=x_mean,
        input_scale=x_scale,
        target_mean=y_mean,
        target_scale=y_scale,
        input_columns=np.array(INPUT_COLUMNS),
        target_columns=np.array(TARGET_COLUMNS),
        rmse=rmse,
        mae=mae,
        r2=r2
    )

    print("saved", args.output)
    print("train_rows", len(train), "test_rows", len(test))
    print("rmse", rmse)
    print("mae", mae)
    print("r2", r2)


if __name__ == "__main__":
    main()
