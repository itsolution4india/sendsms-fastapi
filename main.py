import logging
import os
import typing as ty
import aiofiles
import aiohttp
import uvicorn
import asyncio
import json
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

# Configure logging to log to console only (no file)
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG for more verbose logging
    format="%(asctime)s [%(levelname)s] %(message)s",  # Include timestamp
    datefmt="%Y-%m-%d %H:%M:%S",  # Customize date format
    handlers=[
        logging.StreamHandler()  # Log to console (stdout)
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI()

# Define the Pydantic model for request body
class MessageRequest(BaseModel):
    token: str
    phone_number_id: str
    template_name: str
    language: str
    media_type: str
    media_id: ty.Optional[str]
    contact_list: ty.List[str]
    variable_list: ty.Optional[ty.List[str]] = None

class FlowMessageRequest(BaseModel):
    token: str
    phone_number_id: str
    template_name: str
    flow_id: str
    language: str
    recipient_phone_number: str

async def send_template_with_flow(token: str, phone_number_id: str, template_name: str, flow_id: str, language: str, recipient_phone_number: str):
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": recipient_phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language
            },
            "components": [
                {
                    "type": "button",
                    "sub_type": "flow",
                    "index": "0",
                    "parameters": [
                        {
                            "type": "payload",
                            "payload": flow_id
                        }
                    ]
                }
            ]
        }
    }
    
    logger.info(f"Attempting to send flow message. Data: {json.dumps(data, indent=2)}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, headers=headers, json=data) as response:
                status_code = response.status
                response_dict = await response.json()
                return status_code, response_dict
        except aiohttp.ClientError as e:
            logger.error(f"Error sending flow message: {e}")
            raise HTTPException(status_code=500, detail=f"Error sending flow message: {e}")

async def send_message(session: aiohttp.ClientSession, token: str, phone_number_id: str, template_name: str, language: str, media_type: str, media_id: ty.Optional[str], contact: str, variables: ty.Optional[ty.List[str]] = None) -> None:
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    header_component = {
        "type": "header",
        "parameters": []
    }

    body_component = {
        "type": "body",
        "parameters": []
    }
    
    if variables:
        body_component["parameters"] = [
            {
                "type": "text",
                "text": variable
            } for variable in variables
        ]

    context_info = json.dumps({
        "template_name": template_name,
        "language": language,
        "media_type": media_type
    })

    if media_id and media_type in ["IMAGE", "DOCUMENT", "VIDEO", "AUDIO"]:
        header_component["parameters"].append({
            "type": media_type.lower(),
            media_type.lower(): {"id": media_id}
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": contact,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": [
                header_component,
                body_component
            ]
        },
        "context": {
            "message_id": f"template_{template_name}_{context_info}"
        }
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_message = await response.text()
                logger.error(f"Failed to send message to {contact}. Status: {response.status}, Error: {error_message}")
                return
    except aiohttp.ClientError as e:
        logger.error(f"Error sending message to {contact}: {e}")
        return

async def send_messages(token: str, phone_number_id: str, template_name: str, language: str, media_type: str, media_id: ty.Optional[str], contact_list: ty.List[str], variable_list: ty.List[str]) -> None:
    logger.info(f"Processing {len(contact_list)} contacts for sending messages.")
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=1000)) as session:
        for batch in chunks(contact_list, 75):
            logger.info(f"Sending batch of {len(batch)} contacts")
            tasks = [send_message(session, token, phone_number_id, template_name, language, media_type, media_id, contact, variable_list) for contact in batch]
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.5)
    logger.info("All messages processed.")

def chunks(lst: ty.List[str], size: int) -> ty.Generator[ty.List[str], None, None]:
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

@app.post("/send_sms/")
async def send_messages_api(request: MessageRequest):
    try:
        await send_messages(
            token=request.token,
            phone_number_id=request.phone_number_id,
            template_name=request.template_name,
            language=request.language,
            media_type=request.media_type,
            media_id=request.media_id,
            contact_list=request.contact_list,
            variable_list=request.variable_list
        )
        return {'message': 'Messages sent successfully'}
    except HTTPException as e:
        logger.error(f"HTTP error: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {e}")

@app.post("/send_flow_message/")
async def send_flow_message_api(request: FlowMessageRequest):
    try:
        status_code, response_dict = await send_template_with_flow(
            request.token,
            request.phone_number_id,
            request.template_name,
            request.flow_id,
            request.language,
            request.recipient_phone_number
        )
        if status_code == 200:
            return {'message': 'Flow message sent successfully', 'response': response_dict}
        else:
            logger.error(f"Failed to send flow message. Status code: {status_code}, Response: {response_dict}")
            raise HTTPException(status_code=status_code, detail=f"Error sending flow message: {response_dict}")
    except Exception as e:
        logger.error(f"Unhandled error in send_flow_message_api: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {e}")

@app.get("/")
def root():
    logger.info("Root endpoint accessed.")
    return {"message": "Successful"}

@app.post("/shopify-webhook/")
async def receive_order(request: Request):
    data = await request.json()
    order_details = data.get("order")
    # Extract necessary order details
    order_id = order_details.get("id")
    customer_name = order_details.get("customer", {}).get("first_name")
    total_price = order_details.get("total_price")
    phone_number = order_details.get("customer", {}).get("phone")
    logging.info(f"{order_id}, {customer_name}, {total_price}, {phone_number}")

    return {"status": "success"}

if __name__ == '__main__':
    logger.info("Starting the FastAPI server")
    uvicorn.run(app, host="127.0.0.1", port=8000)
