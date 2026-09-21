import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


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
DEFAULT_OUTPUT = BASE_DIR / "models" / "module_b_forecast.joblib"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    frame = pd.read_csv(args.csv_path)
    missing = [column for column in INPUT_COLUMNS + TARGET_COLUMNS if column not in frame]
    if missing:
        raise ValueError("Missing required training columns: " + ", ".join(missing))

    train = frame[frame.get("split", "train") == "train"].copy()
    test = frame[frame.get("split", "train") == "test"].copy()
    if train.empty or test.empty:
        raise ValueError("The CSV must contain non-empty train and test splits.")

    x_train = train[INPUT_COLUMNS].astype(np.float32)
    y_train = train[TARGET_COLUMNS].astype(np.float32)
    x_test = test[INPUT_COLUMNS].astype(np.float32)
    y_test = test[TARGET_COLUMNS].astype(np.float32)

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=18,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    rmse = np.sqrt(mean_squared_error(y_test, predictions, multioutput="raw_values"))
    mae = mean_absolute_error(y_test, predictions, multioutput="raw_values")
    r2 = r2_score(y_test, predictions, multioutput="raw_values")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": model,
        "input_columns": INPUT_COLUMNS,
        "target_columns": TARGET_COLUMNS,
        "metrics": {
            "rmse": rmse.tolist(),
            "mae": mae.tolist(),
            "r2": r2.tolist()
        }
    }, args.output)

    print("saved", args.output)
    print("rows", len(train), "train", len(test), "test")
    print("rmse", rmse)
    print("mae", mae)
    print("r2", r2)


if __name__ == "__main__":
    main()
