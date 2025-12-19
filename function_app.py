"""
Azure Functions HTTP endpoints for Nhu Tin BOM system.
"""
import json
import traceback

import azure.functions as func
from pydantic import ValidationError

from config import logger
from models.user_input import UserInput
from services.database import Database
from services.optimizer import Optimizer

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
database = Database()


@app.function_name(name="health")
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse(
        body=json.dumps({
            "status": "ok",
            "message": "NhuTin BOM Service is running",
        }),
        mimetype="application/json",
        status_code=200,
    )


@app.function_name(name="process-receipts")
@app.route(route="process_receipt", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def processReceipt(req: func.HttpRequest) -> func.HttpResponse:
    """
    Process receipt and return optimized BOM.
    
    POST /api/process_receipt
    """
    try:
        try:
            body = req.get_json()
        except ValueError:
            logger.warning("Invalid JSON payload")
            body = {}

        logger.info(f"Request: {body}")

        try:
            userInput = UserInput.model_validate(body or {})
        except ValidationError as e:
            logger.warning(f"Validation failed: {e}")
            return func.HttpResponse(
                body=json.dumps({"status": "validation_error", "errors": e.errors()}),
                mimetype="application/json",
                status_code=400,
            )

        # Run optimization
        optimizer = Optimizer(database)
        result = optimizer.optimize(
            containerLength=userInput.containerLength,
            itemModelType=userInput.itemModelType,
            slatType=userInput.slatType,
            receiptPrice=userInput.receiptPrice,
            containerType=userInput.containerType,
            thickness=userInput.thickness,
            targetProfitMargin=userInput.targetProfitMargin,
        )

        response = {
            "status": "ok",
            "items": result["items"],
            "totalWeight": result["totalWeight"],
            "totalCost": result["totalCost"],
            "receiptPrice": result["receiptPrice"],
            "profit": result["profit"],
            "profitMargin": result["profitMargin"],
            "containerBuiltFromMaterials": result.get("containerBuiltFromMaterials", False),
            "constraints": result.get("constraints", {}),
        }
        
        return func.HttpResponse(
            body=json.dumps(response, default=str),
            mimetype="application/json",
            status_code=200,
        )

    except Exception:
        logger.error(f"Error: {traceback.format_exc()}")
        return func.HttpResponse(
            body=json.dumps({"status": "error", "message": traceback.format_exc()}),
            mimetype="application/json",
            status_code=500,
        )
