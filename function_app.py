import json
import os
import tempfile

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
# Ingest receipts from PDF files
@app.function_name(name="ingestReceipts")
@app.route(route="ingest-receipts", methods=["POST"])
def ingestReceipts(req: func.HttpRequest) -> func.HttpResponse:
    # PDF-specific processing with OCR, etc.
    return func.HttpResponse(
        body=json.dumps({
            "status": "ok",
            "message": "Receipts ingestion not implemented yet",
        }),
        mimetype="application/json",
        status_code=200,
    )

@app.function_name(name="ingestInventory")
@app.route(route="ingest-inventory", methods=["POST"])
def ingestInventory(req: func.HttpRequest) -> func.HttpResponse:  # noqa: ARG001
    """
    Ingest inventory data from an uploaded Excel file.

    Route: /api/ingest-inventory
    Body: Raw Excel file bytes (.xlsx)
    """
    try:
        fileData = req.get_body()

        if not fileData:
            return func.HttpResponse(
                body=json.dumps({
                    "status": "error",
                    "message": "No file data received in request body",
                }),
                mimetype="application/json",
                status_code=400,
            )

        # Write to temp file (Azure Functions only allows /tmp writes)
        tempFilePath = os.path.join(tempfile.gettempdir(), "inventory_upload.xlsx")

        with open(tempFilePath, "wb") as f:
            f.write(fileData)

        logger.info(f"📁 Received inventory file upload, size={len(fileData)} bytes")

        Inventory.ingestInventoryFromExcel(tempFilePath)

        # Cleanup temp file
        if os.path.exists(tempFilePath):
            os.remove(tempFilePath)

        return func.HttpResponse(
            body=json.dumps({
                "status": "ok",
                "message": "Inventory ingestion complete",
            }),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error during inventory ingestion: {e}")
        return func.HttpResponse(
            body=json.dumps({
                "status": "error",
                "message": f"Error processing inventory file: {str(e)}",
            }),
            mimetype="application/json",
            status_code=500,
        )


