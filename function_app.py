import json
import traceback

import azure.functions as func
from pydantic import ValidationError

from config import logger
from models.user_input import UserInput
from services.database import Database

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
        try:
            body = req.get_json()
        except ValueError:
            logger.warning("❌ Invalid JSON payload; defaulting to empty dict.")
            body = {}

        logger.info(f"✅ Received request body: {body}")

        try:
            userInput = UserInput.model_validate(body or {})
        except ValidationError as validationError:
            logger.warning(f"❌ Validation failed: {validationError}")
            return func.HttpResponse(
                body=json.dumps({"status": "validation_error", "errors": validationError.errors()}),
                mimetype="application/json",
                status_code=400,
            )

        responsePayload = {
            "status": "ok",
            "userInput": userInput.model_dump(),
        }
        return func.HttpResponse(
            body=json.dumps(responsePayload, default=str),
            mimetype="application/json",
            status_code=200,
        )

    except Exception:
        logger.error(f"❌ Error processing request: {traceback.format_exc()}")
        return func.HttpResponse(
            body=json.dumps({"status": "error", "message": traceback.format_exc()}),
            mimetype="application/json",
            status_code=500,
        )