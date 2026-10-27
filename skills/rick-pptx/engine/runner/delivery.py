"""Confirm the exact reviewed bytes after an ambiguous upload response."""
import hashlib
from resilience import WorkerHTTPError


def deliver(cfg,task,artifact,revision,send,*,check=lambda:None):
    digest=hashlib.sha256(artifact).hexdigest()
    base=f'/api/worker/{task["id"]}'
    query=f'&revision={revision}&sha256={digest}'
    check()
    send(cfg,base+'?action=delivery-ready'+query,lease=task['lease'])
    try:
        send(cfg,base+'?action=complete'+query,artifact,task['lease'])
    except WorkerHTTPError as error:
        if not error.retryable:raise
        # A timeout says nothing about whether the server committed the upload.
        try:receipt=send(cfg,base+'?action=delivery-status',lease=task['lease'])
        except WorkerHTTPError:raise error
        if receipt.get('status')=='complete' and receipt.get('sha256')==digest and receipt.get('revision')==revision:
            return {'sha256':digest,'confirmed_after_timeout':True}
        raise error
    return {'sha256':digest,'confirmed_after_timeout':False}
