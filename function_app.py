import json

import azure.functions as func

from services.fetcher import DriveFetcher
from services.inventory import Inventory
from config import logger
from services.database import Database
import traceback

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
database = Database()

@app.function_name(name="health")
@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Simple health check endpoint."""
    return func.HttpResponse(
        body=json.dumps({"status": "ok", "message": "NhuTin DB Receipts Processing Service is running"}),
        mimetype="application/json",
        status_code=200,
    )


@app.function_name(name="process-receipts")
@app.route(route="process_receipt", methods=["POST"])
def process_receipt(req: func.HttpRequest) -> func.HttpResponse:
    """
    Trigger receipts processing from the user inputs, in JSON format.

    Route: /api/process_receipt
    """
    try:
        body = req.get_json()
        logger.info(f"Received request body: {body}")
        
        inventory_records = database.executeQuery("SELECT * FROM inventory_records")
        logger.info(f"✅ Inventory records: {inventory_records}")

        responsePayload = {"status": "ok", "inventoryRecords": inventory_records}
        return func.HttpResponse(
            body=json.dumps(responsePayload, default=str),
            mimetype="application/json",
            status_code=200,
        )

    except Exception:
        logger.error(f"❌ Error processing request: {traceback.format_exc()}")
        return func.HttpResponse(body=json.dumps({"status": "error", "message": traceback.format_exc()}), mimetype="application/json", status_code=500,)