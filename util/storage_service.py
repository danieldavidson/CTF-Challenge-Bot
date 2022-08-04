from typing import Any, Dict

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError
from pydantic import ValidationError

from bottypes.ctf import CTF
from util.loghandler import log

CTF_INDEX = "ctf"


class StorageService:
    """
    Storage for ctfs and challenges.
    """

    def __init__(self):
        host = '192.168.2.15'
        port = 9200
        auth = ('admin', 'admin')  # For testing only. Don't store credentials in code.

        # Create the client with SSL/TLS enabled, but hostname verification disabled.
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_compress=True,  # enables gzip compression for request bodies
            http_auth=auth,
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False
        )

    def add_ctf(self, ctf: CTF):
        self.add(CTF_INDEX, ctf.dict(), ctf.channel_id)

    def get_ctf(self, ctf_id: str = "", ctf_name: str = "") -> CTF | None:
        if not (ctf_id or ctf_name):
            raise ValueError("One of ctf_id or ctf_name must be specified.")

        ctf_doc = {}
        if ctf_id:
            try:
                result = self.get(CTF_INDEX, ctf_id)
                if result["found"] is True:
                    ctf_doc = result["_source"]
            except NotFoundError:
                pass
        if not ctf_doc and ctf_name:
            query = {
                'query': {
                    'term': {
                        'name': ctf_name,
                    }
                }
            }
            result = self.search(CTF_INDEX, query)
            if result["hits"]["total"]["value"] > 0:
                ctf_doc = result["hits"]["hits"][0]["_source"]

        try:
            return CTF.parse_obj(ctf_doc)
        except ValidationError as e:
            log.warning(f"Failed to build CTF from obj: {ctf_doc}")
            return None

    def remove_ctf(self, ctf_id: str):
        self.delete(CTF_INDEX, ctf_id)

    def add(self, index: str, document: Dict[Any, Any], doc_id: str):
        self.client.index(index=index, body=document, id=doc_id, refresh=True)

    def get(self, index: str, doc_id: str):
        return self.client.get(index=index, id=doc_id)

    def search(self, index: str, query: Any):
        return self.client.search(index=index, body=query)

    def delete(self, index, doc_id):
        self.client.delete(index=index, id=doc_id)
