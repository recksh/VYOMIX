from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import csv
import io

try:
    from model_runner import run_gmm, run_anomaly, run_forecast
except ModuleNotFoundError:
    from backend.model_runner import run_gmm, run_anomaly, run_forecast


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="VYOMIX ML Backend",
    description="AI backend for VYOMIX Module A and Module B",
    version="1.0.0"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# MODULE A - EXACT 32 MODEL INPUT FEATURES
# =========================================================

MODULE_A_FEATURES = [

    "IGSS_uA_0h",
    "IGSS_uA_24h",
    "IGSS_uA_96h",

    "IDSS_uA_0h",
    "IDSS_uA_24h",
    "IDSS_uA_96h",

    "VGSth_V_0h",
    "VGSth_V_24h",
    "VGSth_V_96h",

    "RDSon_mOhm_0h",
    "RDSon_mOhm_24h",
    "RDSon_mOhm_96h",

    "IGSS_uA_slope_0_24h",
    "IGSS_uA_slope_24_96h",

    "IDSS_uA_slope_0_24h",
    "IDSS_uA_slope_24_96h",

    "VGSth_V_slope_0_24h",
    "VGSth_V_slope_24_96h",

    "RDSon_mOhm_slope_0_24h",
    "RDSon_mOhm_slope_24_96h",

    "IGSS_uA_0h_lot_z",
    "IGSS_uA_24h_lot_z",
    "IGSS_uA_96h_lot_z",

    "IDSS_uA_0h_lot_z",
    "IDSS_uA_24h_lot_z",
    "IDSS_uA_96h_lot_z",

    "VGSth_V_0h_lot_z",
    "VGSth_V_24h_lot_z",
    "VGSth_V_96h_lot_z",

    "RDSon_mOhm_0h_lot_z",
    "RDSon_mOhm_24h_lot_z",
    "RDSon_mOhm_96h_lot_z"
]


BASE_MEASUREMENT_FEATURES = [
    "IGSS_uA_0h", "IGSS_uA_24h", "IGSS_uA_96h",
    "IDSS_uA_0h", "IDSS_uA_24h", "IDSS_uA_96h",
    "VGSth_V_0h", "VGSth_V_24h", "VGSth_V_96h",
    "RDSon_mOhm_0h", "RDSon_mOhm_24h", "RDSon_mOhm_96h"
]


def build_module_a_values(row, rows):
    """Build Module A's 32 features from processed or raw CSV columns."""

    if all(feature in row for feature in MODULE_A_FEATURES):
        return [float(row[feature]) for feature in MODULE_A_FEATURES]

    raw_columns = [
        feature
        for feature in BASE_MEASUREMENT_FEATURES
        if not feature.endswith("_96h")
    ]
    missing = [feature for feature in raw_columns if feature not in row]
    if missing:
        raise ValueError(
            "CSV must contain either the 32 processed model columns or "
            "these raw measurement columns: " + ", ".join(missing)
        )

    values = [
        float(row[feature]) if row.get(feature, "") != "" else float(
            row[feature.replace("_96h", "_24h")]
        )
        for feature in BASE_MEASUREMENT_FEATURES
    ]

    for metric in ("IGSS_uA", "IDSS_uA", "VGSth_V", "RDSon_mOhm"):
        value_0h = float(row[f"{metric}_0h"])
        value_24h = float(row[f"{metric}_24h"])
        value_96h = float(row.get(f"{metric}_96h") or value_24h)
        values.extend([
            (value_24h - value_0h) / 24,
            (value_96h - value_24h) / 72
        ])

    for feature in BASE_MEASUREMENT_FEATURES:
        population = [
            float(item[feature]) if item.get(feature, "") != "" else float(
                item[feature.replace("_96h", "_24h")]
            )
            for item in rows
        ]
        mean = sum(population) / len(population)
        variance = sum((item - mean) ** 2 for item in population) / len(population)
        standard_deviation = variance ** 0.5
        value = (
            float(row[feature]) if row.get(feature, "") != "" else float(
                row[feature.replace("_96h", "_24h")]
            )
        )
        values.append((value - mean) / standard_deviation if standard_deviation else 0.0)

    return values


MODULE_B_24H_FEATURES = [
    "IGSS_uA_0h", "IGSS_uA_24h",
    "IDSS_uA_0h", "IDSS_uA_24h",
    "VGSth_V_0h", "VGSth_V_24h",
    "RDSon_mOhm_0h", "RDSon_mOhm_24h"
]


def build_module_b_values(row, rows):
    """Return the model's 32 values from precomputed or raw CSV features."""

    if all(feature in row for feature in MODULE_A_FEATURES):
        return [float(row[feature]) for feature in MODULE_A_FEATURES]

    missing = [
        feature for feature in BASE_MEASUREMENT_FEATURES
        if feature not in row
    ]

    if missing:
        raise ValueError(
            "CSV must contain either the 32 processed model columns or "
            "these raw measurement columns: " + ", ".join(missing)
        )

    values = [float(row[feature]) for feature in BASE_MEASUREMENT_FEATURES]

    for metric in ("IGSS_uA", "IDSS_uA", "VGSth_V", "RDSon_mOhm"):
        value_0h = float(row[f"{metric}_0h"])
        value_24h = float(row[f"{metric}_24h"])
        value_96h = float(row[f"{metric}_96h"])
        values.extend([
            (value_24h - value_0h) / 24,
            (value_96h - value_24h) / 72
        ])

    for feature in BASE_MEASUREMENT_FEATURES:
        population = [float(item[feature]) for item in rows]
        mean = sum(population) / len(population)
        variance = sum((item - mean) ** 2 for item in population) / len(population)
        standard_deviation = variance ** 0.5
        value = float(row[feature])
        values.append((value - mean) / standard_deviation if standard_deviation else 0.0)

    return values


def get_drift_values(row):
    """Return display values for the first available time-series metric."""

    prefixes = (
        "RDSon_mOhm",
        "IGSS_uA",
        "IDSS_uA",
        "VGSth_V"
    )
    prefix = next(
        (candidate for candidate in prefixes if f"{candidate}_0h" in row),
        None
    )

    if prefix is None:
        return None

    value_0h = float(row[f"{prefix}_0h"])
    value_24h = float(row[f"{prefix}_24h"])
    slope = (value_24h - value_0h) / 24
    predicted_168h = value_24h + (slope * 144)

    return {
        "value_0h": round(value_0h, 4),
        "value_24h": round(value_24h, 4),
        "predicted_168h": round(predicted_168h, 4),
        "drift": round(predicted_168h - value_0h, 4),
        "safety_slope": round(slope, 4)
    }


def classify_module_b_risk(measurements):
    """Classify a Module B forecast using the percentage drift relative to 0h."""

    if not measurements:
        return "Normal"

    value_0h = measurements.get("value_0h")
    drift = measurements.get("drift")
    predicted_168h = measurements.get("predicted_168h")

    if value_0h in (None, "") or predicted_168h in (None, ""):
        return "Normal"

    if float(value_0h) == 0:
        return "Normal"

    drift_percent = float(drift) if drift not in (None, "") else 0.0
    if drift_percent >= 25.0:
        return "High"
    if drift_percent >= 10.0:
        return "Review"
    return "Normal"


def predict_from_24h_values(row):
    """Forecast each supported measurement with the trained Module B model."""

    for feature in MODULE_B_24H_FEATURES:
        if feature not in row:
            raise ValueError(
                "Module B requires 0h and 24h columns for IGSS, IDSS, "
                "VGSth, and RDSon."
            )

    values = [float(row[feature]) for feature in MODULE_B_24H_FEATURES]
    predictions_list = run_forecast(values)
    predictions = {
        f"{metric}_168h": round(predictions_list[index], 4)
        for index, metric in enumerate(
            ("IGSS_uA", "IDSS_uA", "VGSth_V", "RDSon_mOhm")
        )
    }
    measurements = {
        "value_0h": round(float(row["RDSon_mOhm_0h"]), 4),
        "value_24h": round(float(row["RDSon_mOhm_24h"]), 4),
        "predicted_168h": predictions["RDSon_mOhm_168h"],
        "drift": round(
            (
                predictions["RDSon_mOhm_168h"]
                - float(row["RDSon_mOhm_0h"])
            )
            / float(row["RDSon_mOhm_0h"])
            * 100,
            4
        ),
        "prediction_method": "ML forecast"
    }

    actual_key = "RDSon_mOhm_168h"
    if actual_key in row and row[actual_key] != "":
        actual = float(row[actual_key])
        error = actual - predictions["RDSon_mOhm_168h"]
        measurements["actual_168h"] = round(actual, 4)
        measurements["prediction_error"] = round(error, 4)
        measurements["absolute_percentage_error"] = round(
            abs(error) / abs(actual) * 100 if actual else 0.0,
            4
        )

    return measurements, predictions


# =========================================================
# GMM THRESHOLD
# =========================================================

GMM_THRESHOLD = 348.28


# =========================================================
# JSON INPUT
# =========================================================

class ModelInput(BaseModel):

    values: list[float]


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "success": True,
        "message": "VYOMIX ML Backend is working!",
        "module_a": "/module-a",
        "module_b": "/module-b",
        "health": "/health"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "success": True,
        "status": "healthy",
        "service": "VYOMIX ML Backend"
    }


# =========================================================
# MODULE A
# CSV → 32 FEATURES → GMM
# =========================================================

@app.post("/module-a")
async def module_a(file: UploadFile = File(...)):

    try:

        # -------------------------------------------------
        # Check filename
        # -------------------------------------------------

        if not file.filename:

            return {
                "success": False,
                "module": "Module A",
                "message": "No file was selected."
            }


        if not file.filename.lower().endswith(".csv"):

            return {
                "success": False,
                "module": "Module A",
                "message": "Please upload a CSV file."
            }


        # -------------------------------------------------
        # Read uploaded CSV
        # -------------------------------------------------

        file_bytes = await file.read()

        text = file_bytes.decode("utf-8-sig")

        reader = csv.DictReader(
            io.StringIO(text)
        )

        rows = list(reader)


        if not rows:

            return {
                "success": False,
                "module": "Module A",
                "message": "CSV file contains no component records."
            }


        # -------------------------------------------------
        # Check required columns
        # -------------------------------------------------

        csv_columns = reader.fieldnames or []

        raw_columns = [
            feature for feature in BASE_MEASUREMENT_FEATURES
            if not feature.endswith("_96h")
        ]
        has_processed_columns = all(
            column in csv_columns for column in MODULE_A_FEATURES
        )
        has_raw_columns = all(
            column in csv_columns for column in raw_columns
        )

        if not has_processed_columns and not has_raw_columns:

            return {
                "success": False,
                "module": "Module A",
                "message": "Required Module A columns are missing.",
                "missing_columns": missing_columns
            }


        # -------------------------------------------------
        # Process every component
        # -------------------------------------------------

        results = []

        normal_count = 0

        anomaly_count = 0

        error_count = 0


        for index, row in enumerate(rows):

            try:

                # -----------------------------------------
                # Component ID
                # -----------------------------------------

                component_id = (

                    row.get("part_id")

                    or row.get("component_id")

                    or row.get("id")

                    or f"Component-{index + 1}"

                )


                # -----------------------------------------
                # Extract exact 32 values
                # -----------------------------------------

                values = build_module_a_values(row, rows)


                # -----------------------------------------
                # Run GMM
                # -----------------------------------------

                score = run_gmm(values)


                # -----------------------------------------
                # Determine status
                # -----------------------------------------

                if score >= GMM_THRESHOLD:

                    status = "Anomaly"

                    anomaly_count += 1

                    explanation = (

                        f"Dynamic lot-relative anomaly score {score:.2f} "

                        f"exceeds the population threshold "

                        f"of {GMM_THRESHOLD:.2f}."

                    )

                else:

                    status = "Normal"

                    normal_count += 1

                    explanation = (

                        f"Dynamic lot-relative anomaly score {score:.2f} "

                        f"is below the population threshold "

                        f"of {GMM_THRESHOLD:.2f}."

                    )


                # -----------------------------------------
                # Save result
                # -----------------------------------------

                results.append({

                    "component_id": component_id,

                    "lot_batch": (
                        row.get("lot_id")
                        or row.get("lot")
                        or row.get("batch_id")
                        or row.get("batch")
                        or "-"
                    ),

                    "status": status,

                    "score": round(score, 4),

                    "anomaly_score": round(score, 4),

                    "threshold": GMM_THRESHOLD,

                    "detection_method": "Dynamic lot-relative outlier detection",

                    "comparison_basis": "Lot population features and lot z-scores",

                    "explanation": explanation

                })


            except Exception as component_error:

                error_count += 1


                results.append({

                    "component_id": (

                        row.get("part_id")

                        or row.get("component_id")

                        or row.get("id")

                        or f"Component-{index + 1}"

                    ),

                    "status": "Review",

                    "score": None,

                    "anomaly_score": None,

                    "threshold": GMM_THRESHOLD,

                    "detection_method": "Dynamic lot-relative outlier detection",

                    "explanation": (

                        "Unable to process this component: "

                        + str(component_error)

                    )

                })


        # -------------------------------------------------
        # Final response
        # -------------------------------------------------

        return {

            "success": True,

            "module": "Module A",

            "filename": file.filename,

            "total_components": len(rows),

            "normal_components": normal_count,

            "anomaly_components": anomaly_count,

            "review_components": error_count,

            "threshold": GMM_THRESHOLD,

            "results": results

        }


    except Exception as error:

        return {

            "success": False,

            "module": "Module A",

            "message": str(error)

        }


@app.post("/module-a/predict")
def module_a_predict(data: ModelInput):

    try:

        if len(data.values) != len(MODULE_A_FEATURES):
            return {
                "success": False,
                "module": "Module A",
                "message": "Exactly 32 input values are required."
            }

        score = run_gmm(data.values)

        return {
            "success": True,
            "module": "Module A",
            "score": score
        }

    except Exception as error:
        return {
            "success": False,
            "module": "Module A",
            "message": str(error)
        }


# =========================================================
# MODULE B
# =========================================================

@app.post("/module-b")
def module_b(data: ModelInput):

    try:

        if not data.values:

            return {

                "success": False,

                "module": "Module B",

                "message": "No values were provided."

            }


        score = run_anomaly(
            data.values
        )


        return {

            "success": True,

            "module": "Module B",

            "score": score

        }


    except Exception as error:

        return {

            "success": False,

            "module": "Module B",

            "message": str(error)

        }


# =========================================================
# MODULE B CSV
# CSV -> 32 FEATURES -> ANOMALY MODEL
# =========================================================

@app.post("/module-b/analyze")
async def module_b_csv(file: UploadFile = File(...)):

    try:

        if not file.filename:
            return {
                "success": False,
                "module": "Module B",
                "message": "No file was selected."
            }

        if not file.filename.lower().endswith(".csv"):
            return {
                "success": False,
                "module": "Module B",
                "message": "Please upload a CSV file."
            }

        text = (await file.read()).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = [
            {
                (key or "").strip().lstrip("\ufeff"): (value or "").strip()
                for key, value in raw_row.items()
            }
            for raw_row in reader
        ]

        if not rows:
            return {
                "success": False,
                "module": "Module B",
                "message": "CSV file contains no component records."
            }

        results = []
        high_risk_count = 0

        for index, row in enumerate(rows):
            component_id = (
                row.get("part_id")
                or row.get("component_id")
                or row.get("id")
                or f"Component-{index + 1}"
            )

            try:
                if all(feature in row for feature in MODULE_B_24H_FEATURES):
                    measurements, predictions = predict_from_24h_values(row)
                    score = predictions["RDSon_mOhm_168h"]
                    risk = classify_module_b_risk(measurements)
                    explanation = (
                        "168h values were forecast from the eight observed 0h-to-24h inputs."
                        f" Predicted RDSon drift is {measurements.get('drift', 0)}% relative to the 0h value."
                        f" IGSS: {predictions['IGSS_uA_168h']};"
                        f" IDSS: {predictions['IDSS_uA_168h']};"
                        f" VGSth: {predictions['VGSth_V_168h']};"
                        f" RDSon: {predictions['RDSon_mOhm_168h']}."
                    )
                else:
                    values = build_module_b_values(row, rows)
                    score = run_anomaly(values)
                    risk = "High" if score >= GMM_THRESHOLD else "Normal"
                    measurements = get_drift_values(row)
                    predictions = {}
                    explanation = (
                        f"Anomaly score {score:.2f} "
                        f"is classified as {risk.lower()} risk."
                    )

                if risk == "High":
                    high_risk_count += 1

                results.append({
                    "component_id": component_id,
                    "lot_batch": (
                        row.get("lot_id")
                        or row.get("lot")
                        or row.get("batch_id")
                        or row.get("batch")
                        or "-"
                    ),
                    "score": round(score, 4),
                    "risk": risk,
                    "status": risk,
                    "measurements": measurements,
                    "predictions": predictions,
                    "model_score": round(score, 4),
                    "explanation": explanation
                })

            except Exception as component_error:
                results.append({
                    "component_id": component_id,
                    "score": None,
                    "model_score": None,
                    "risk": "Review",
                    "measurements": None,
                    "explanation": "Unable to process this component: " + str(component_error),
                    "error": str(component_error)
                })

        return {
            "success": True,
            "module": "Module B",
            "total_components": len(rows),
            "prediction_count": len(rows),
            "high_risk_count": high_risk_count,
            "results": results
        }

    except Exception as error:
        return {
            "success": False,
            "module": "Module B",
            "message": str(error)
        }