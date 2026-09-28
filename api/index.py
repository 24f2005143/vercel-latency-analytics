from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import json
import math

app = FastAPI()


# --------------------------------------------------
# CORS
# --------------------------------------------------
# Allow POST requests from any origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Load telemetry dataset
# --------------------------------------------------
DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "q-vercel-latency.json"
)

with open(DATA_FILE, "r", encoding="utf-8") as file:
    telemetry = json.load(file)


# --------------------------------------------------
# Request model
# --------------------------------------------------
class AnalyticsRequest(BaseModel):
    regions: list[str]
    threshold_ms: float


# --------------------------------------------------
# P95 calculation
# --------------------------------------------------
def percentile(values: list[float], p: float) -> float:
    """
    Calculate percentile using linear interpolation.
    """

    if not values:
        raise ValueError("Cannot calculate percentile of empty data.")

    sorted_values = sorted(values)

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * (p / 100)

    lower_index = math.floor(position)
    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return sorted_values[lower_index]

    weight = position - lower_index

    return (
        sorted_values[lower_index]
        + weight
        * (
            sorted_values[upper_index]
            - sorted_values[lower_index]
        )
    )


# --------------------------------------------------
# POST analytics endpoint
# --------------------------------------------------
@app.post("/")
def analytics(request: AnalyticsRequest):

    results = []

    for region in request.regions:

        # Select records belonging to this region
        rows = [
            record
            for record in telemetry
            if record["region"] == region
        ]

        # Handle unknown region
        if not rows:
            results.append(
                {
                    "region": region,
                    "avg_latency": None,
                    "p95_latency": None,
                    "avg_uptime": None,
                    "breaches": 0,
                }
            )
            continue

        # Extract latency and uptime values
        latencies = [
            record["latency_ms"]
            for record in rows
        ]

        uptimes = [
            record["uptime_pct"]
            for record in rows
        ]

        # Average latency
        avg_latency = sum(latencies) / len(latencies)

        # 95th percentile latency
        p95_latency = percentile(latencies, 95)

        # Average uptime
        avg_uptime = sum(uptimes) / len(uptimes)

        # Count latency values ABOVE threshold
        breaches = sum(
            1
            for latency in latencies
            if latency > request.threshold_ms
        )

        results.append(
            {
                "region": region,
                "avg_latency": avg_latency,
                "p95_latency": p95_latency,
                "avg_uptime": avg_uptime,
                "breaches": breaches,
            }
        )

    return results