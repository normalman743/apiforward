# app/core/billing.py
from fastapi import HTTPException
from typing import Dict
from app.models.database import db
from app.models.logger import logger
from datetime import datetime

class BillingSystem:
    async def check_balance(self, api_key: str, estimated_cost: float):
        request_id = str(datetime.now().timestamp())
        
        logger.info("Checking user balance", extra={
            "request_id": request_id,
            "api_key": api_key,
            "estimated_cost": estimated_cost
        })
        
        user = await db.api_keys.find_one({"api_key": api_key})
        current_balance = user["balance"]
        
        logger.debug("Balance details", extra={
            "request_id": request_id,
            "api_key": api_key,
            "current_balance": current_balance,
            "estimated_cost": estimated_cost,
            "remaining_balance": current_balance - estimated_cost
        })
        
        if current_balance < estimated_cost:
            logger.warning("Insufficient balance", extra={
                "request_id": request_id,
                "api_key": api_key,
                "current_balance": current_balance,
                "estimated_cost": estimated_cost,
                "shortage": estimated_cost - current_balance
            })
            return False
            
        logger.info("Balance check passed", extra={
            "request_id": request_id,
            "api_key": api_key,
            "remaining_balance": current_balance - estimated_cost
        })
        return True
        
    async def calculate_cost(self, tokens: Dict, model_config: Dict):
        request_id = str(datetime.now().timestamp())
        
        input_cost = (tokens["input"] / 1_000_000) * model_config["pricing"]["input_price"]
        output_cost = (tokens["output"] / 1_000_000) * model_config["pricing"]["output_price"]
        total_cost = input_cost + output_cost
        
        logger.debug("Cost calculation details", extra={
            "request_id": request_id,
            "input_tokens": tokens["input"],
            "output_tokens": tokens["output"],
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "model_id": model_config.get("model_id")
        })
        
        return total_cost
        
    async def deduct_balance(self, api_key: str, cost: float):
        request_id = str(datetime.now().timestamp())
        
        logger.info("Starting balance deduction", extra={
            "request_id": request_id,
            "api_key": api_key,
            "deduction_amount": cost
        })
        
        # Get current balance
        user = await db.api_keys.find_one({"api_key": api_key})
        old_balance = user["balance"]
        new_balance = old_balance - cost
        
        # Update balance
        await db.api_keys.update_one(
            {"api_key": api_key},
            {"$set": {"balance": new_balance}}
        )
        
        logger.info("Balance deducted successfully", extra={
            "request_id": request_id,
            "api_key": api_key,
            "previous_balance": old_balance,
            "deduction_amount": cost,
            "new_balance": new_balance
        })
        
        # Log transaction
        await self._log_transaction(
            api_key=api_key,
            amount=cost,
            old_balance=old_balance,
            new_balance=new_balance,
            transaction_type="deduction"
        )
        
    async def _log_transaction(self, **kwargs):
        """Log billing transaction details"""
        await db.transactions.insert_one({
            "timestamp": datetime.now(),
            **kwargs
        })