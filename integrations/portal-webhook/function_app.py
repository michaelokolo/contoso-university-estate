
import json
import logging
import os
import threading
import time

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from signature import is_valid

logging.getLogger("azure").setLevel(logging.WARNING)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

credential = DefaultAzureCredential()
sb_client = ServiceBusClient(os.environ["SERVICEBUS_NAMESPACE"], credential)
QUEUE = os.environ["SERVICEBUS_QUEUE"]
sender = sb_client.get_queue_sender(QUEUE)
send_lock = threading.Lock()

@app.route(route="webhooks/portal", methods=["POST"])
def portal_webhook(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_body()
    signature = req.headers.get("X-Contoso-Signature", "")
    if not is_valid(body, signature, os.environ["PORTAL_WEBHOOK_SECRET"], time.time()):
        logging.warning("Rejected portal webhook: invalid signature")
        return func.HttpResponse(status_code=401)

    event = json.loads(body)
    message = ServiceBusMessage(
        body,
        message_id=event["id"],
        content_type="application/json",
        subject=event["type"],
    )
    with send_lock:
        sender.send_messages(message)

    logging.info("Queued %s %s", event["type"], event["id"])
    return func.HttpResponse(status_code=202)
