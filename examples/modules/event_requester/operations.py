"""Store a request and deliver it through the chassis event bus."""
from metaform import event
from . import dao
from .models import RequestReceipt


def request(prompt: str) -> RequestReceipt:
    record = dao.save_request(prompt)
    deliveries = event.publish('harness.request', refs=(record.join_ref,))
    return {'request': record, 'deliveries': deliveries}


OPERATIONS = {"request": request}
