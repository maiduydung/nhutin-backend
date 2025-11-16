import json

import azure.functions as func

from services.fetcher import DriveFetcher
from services.inventory import Inventory
from config import logger


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.function_name(name="health")
@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:  # noqa: ARG001
    """Simple health check endpoint."""
    return func.HttpResponse(
        body=json.dumps({"status": "ok", "message": "NhuTin DB Ingestion Service is running"}),
        mimetype="application/json",
        status_code=200,
    )


@app.function_name(name="ingest")
@app.route(route="ingest", methods=["POST"])
def ingest(req: func.HttpRequest) -> func.HttpResponse:  # noqa: ARG001
    """
    Trigger inventory ingestion from the latest Excel file in Google Drive.

    Route: /api/ingest
    """
    driveFetcher = DriveFetcher()
    inventory = Inventory()

    try:
        filePath = driveFetcher.fetchLatestExcelFromFolder("Nhu Tin")

        if not filePath:
            logger.error("No Excel file found to ingest")
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "status": "error",
                        "message": "No Excel file found in Google Drive folder",
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )

        inventory.ingestInventoryFromExcel(filePath)

        return func.HttpResponse(
            body=json.dumps({"status": "ok", "filePath": filePath}),
            mimetype="application/json",
            status_code=200,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error during ingestion: {e}")
        return func.HttpResponse(
            body=json.dumps(
                {
                    "status": "error",
                    "message": "Unexpected error during ingestion",
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


