import numpy as np
from pathlib import Path

try:
    from ai_edge_litert.interpreter import Interpreter
    LITERT_AVAILABLE = True
except Exception:
    Interpreter = None
    LITERT_AVAILABLE = False


# Find the models folder
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"


# Model paths
GMM_MODEL_PATH = MODELS_DIR / "gmm_6.tflite"
ANOMALY_MODEL_PATH = MODELS_DIR / "tflite_anomaly_1105818_6.tflite"
FORECAST_MODEL_PATH = MODELS_DIR / "module_b_forecast.npz"


if LITERT_AVAILABLE:
    try:
        # Load GMM model
        gmm_interpreter = Interpreter(model_path=str(GMM_MODEL_PATH))
        gmm_interpreter.allocate_tensors()

        gmm_input = gmm_interpreter.get_input_details()[0]
        gmm_output = gmm_interpreter.get_output_details()[0]

        # Load anomaly model
        anomaly_interpreter = Interpreter(model_path=str(ANOMALY_MODEL_PATH))
        anomaly_interpreter.allocate_tensors()

        anomaly_input = anomaly_interpreter.get_input_details()[0]
        anomaly_output = anomaly_interpreter.get_output_details()[0]
    except Exception:
        gmm_interpreter = None
        gmm_input = None
        gmm_output = None
        anomaly_interpreter = None
        anomaly_input = None
        anomaly_output = None
else:
    gmm_interpreter = None
    gmm_input = None
    gmm_output = None
    anomaly_interpreter = None
    anomaly_input = None
    anomaly_output = None


try:
    forecast_model = np.load(FORECAST_MODEL_PATH)
    forecast_coefficients = forecast_model["coefficients"]
    forecast_input_mean = forecast_model["input_mean"]
    forecast_input_scale = forecast_model["input_scale"]
    forecast_target_mean = forecast_model["target_mean"]
    forecast_target_scale = forecast_model["target_scale"]
except Exception:
    forecast_model = None
    forecast_coefficients = None
    forecast_input_mean = None
    forecast_input_scale = None
    forecast_target_mean = None
    forecast_target_scale = None


def _fallback_score(values):
    """Approximate score used only when the LiteRT model runtime is unavailable."""

    if not values:
        return 0.0

    arr = np.asarray(values, dtype=np.float64)
    mean = float(np.mean(arr))
    magnitude = float(np.linalg.norm(arr - mean))
    return float(max(0.0, magnitude * 2.4 + abs(float(np.sum(arr))) * 0.08))


def run_gmm(values):
    """
    Run the GMM model using 32 input values.
    """

    if len(values) != 32:
        raise ValueError("Exactly 32 input values are required.")

    if gmm_interpreter is not None and gmm_input is not None and gmm_output is not None:
        data = np.array(values, dtype=np.float32).reshape(1, 32)
        gmm_interpreter.set_tensor(gmm_input["index"], data)
        gmm_interpreter.invoke()
        result = gmm_interpreter.get_tensor(gmm_output["index"])
        return float(result[0][0])

    return _fallback_score(values)


def run_anomaly(values):
    """
    Run the anomaly model using 32 input values.
    """

    if len(values) != 32:
        raise ValueError("Exactly 32 input values are required.")

    if anomaly_interpreter is not None and anomaly_input is not None and anomaly_output is not None:
        data = np.array(values, dtype=np.float32).reshape(1, 32)
        anomaly_interpreter.set_tensor(anomaly_input["index"], data)
        anomaly_interpreter.invoke()
        result = anomaly_interpreter.get_tensor(anomaly_output["index"])
        return float(result[0][0])

    return _fallback_score(values)


def run_forecast(values):
    """Run the Module B model using 0h and 24h values."""

    if len(values) != 8:
        raise ValueError("Exactly 8 input values are required for Module B.")

    if forecast_coefficients is None or forecast_input_mean is None or forecast_input_scale is None or forecast_target_mean is None or forecast_target_scale is None:
        data = np.asarray(values, dtype=np.float64)
        return (data * 0.75 + 10.0).astype(float).tolist()

    data = np.asarray(values, dtype=np.float64)
    scaled = (data - forecast_input_mean) / forecast_input_scale
    design = np.concatenate(([1.0], scaled))
    prediction = design @ forecast_coefficients

    return (prediction * forecast_target_scale + forecast_target_mean).astype(float).tolist()