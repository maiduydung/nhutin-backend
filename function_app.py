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
from services.optimizer import OptimizerV2

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
            "functionName": "health",
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

        # Run optimization with 4-phase algorithm
        optimizer = OptimizerV2(database)
        result = optimizer.optimize(
            containerLength=userInput.containerLength,
            itemModelType=userInput.itemModelType,
            slatType=userInput.slatType,
            receiptPrice=userInput.receiptPrice,
            containerType=userInput.containerType,
            thickness=userInput.thickness,
            targetProfitMargin=userInput.targetProfitMargin,
            buildContainer=userInput.buildContainer,
            existingContainerWeight=userInput.existingContainerWeight,
            relaxedMode=userInput.relaxedMode,
        )

        # For impossible cases (error status), return minimal response with diagnostic info
        if result.get("status") == "error":
            response = {
                "status": "error",
                "error": result.get("error"),
                "items": [],  # Empty - nothing to return
                "totalWeight": 0,
                "totalCost": 0,
                "receiptPrice": result.get("receiptPrice"),
                "profit": 0,
                "profitMargin": 0,
                "constraints": result.get("constraints", {}),
                "diagnostic": result.get("diagnostic", {}),
            }
        else:
            # Normal response with items
            response = {
                "status": result.get("status", "ok"),
                "items": result["items"],
                "totalWeight": result["totalWeight"],
                "totalCost": result["totalCost"],
                "receiptPrice": result["receiptPrice"],
                "profit": result["profit"],
                "profitMargin": result["profitMargin"],
                "containerBuiltFromMaterials": result.get("containerBuiltFromMaterials", False),
                "constraints": result.get("constraints", {}),
                "error": result.get("error"),
                "warning": result.get("warning"),  # Relaxed mode warning
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
