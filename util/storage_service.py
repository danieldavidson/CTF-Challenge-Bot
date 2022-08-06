import os
from typing import Any, Dict, List

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError
from pydantic import ValidationError

from bottypes.challenge import Challenge
from bottypes.ctf import CTF
from util.loghandler import log

CTF_INDEX = "ctf"


class StorageService:
    """
    Storage for ctfs and challenges.
    """

    def __init__(self):
        host = os.environ.get("STORAGE_HOST", default="127.0.0.1")
        port = int(os.environ.get("STORAGE_PORT", default=9200))
        auth = (
            os.environ.get("STORAGE_USERNAME", default="admin"),
            os.environ.get("STORAGE_USERNAME", default="admin"),
        )  # For testing only. Don't store credentials in code.

        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
            http_auth=auth,
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False,
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
                "query": {
                    "term": {
                        "name": ctf_name,
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

    def update_ctf(self, ctf_id, update_func) -> CTF | None:
        ctf = self.get_ctf(ctf_id=ctf_id)
        if ctf:
            update_func(ctf)
            self.add_ctf(ctf)
            return ctf
        return None

    def update_ctf_name(self, ctf_id: str, ctf_name: str):
        self.update(CTF, {"doc": {"name": ctf_name}}, ctf_id)
        ctf = self.get_ctf(ctf_id=ctf_id)
        ctf.name = ctf_name
        self.add_ctf(ctf)

    def add_challenge(self, challenge: Challenge, ctf_id: str = ""):
        ctf = self.get_ctf(ctf_id)
        if not ctf:
            raise ValueError(f"No CTF with id {ctf_id}.")
        ctf.add_challenge(challenge)
        self.add_ctf(ctf)

    def get_challenges(self, ctf_id: str = "") -> List[Challenge]:
        ctf = self.get_ctf(ctf_id=ctf_id)
        if ctf:
            return ctf.challenges

    def get_challenge(
        self, challenge_id: str = "", challenge_name: str = "", ctf_id: str = ""
    ) -> Challenge | None:
        if not (challenge_id or challenge_name):
            raise ValueError("One of challenge_id or challenge_name must be specified.")

        the_chal_dict = {}
        if challenge_id and ctf_id:
            ctf = self.get_ctf(ctf_id=ctf_id)
            if ctf:
                challenges = ctf.challenges
                for challenge in challenges:
                    if challenge.channel_id == challenge_id:
                        return challenge
        elif challenge_name and ctf_id:
            ctf = self.get_ctf(ctf_id=ctf_id)
            if ctf:
                challenges = ctf.challenges
                for challenge in challenges:
                    if challenge.name == challenge_name:
                        return challenge
        elif challenge_id and not ctf_id:
            the_chal_dict = self._search_all_ctfs_for_challenge(
                "channel_id", challenge_id
            )
        elif challenge_name and not ctf_id:
            the_chal_dict = self._search_all_ctfs_for_challenge("name", challenge_name)

        try:
            return Challenge.parse_obj(the_chal_dict)
        except ValidationError as e:
            log.warning(f"Failed to build Challenge from obj: {the_chal_dict}")
            return None

    def remove_challenge(self, challenge_id: str = "", ctf_id: str = ""):
        ctf = self.get_ctf(ctf_id=ctf_id)
        ctf.challenges = list(
            filter(
                lambda challenge: challenge.channel_id != challenge_id,
                ctf.challenges,
            )
        )
        self.add_ctf(ctf)

    def update_challenge_name(self, challenge_id: str, new_name: str):
        challenge_dict = self._search_all_ctfs_for_challenge(
            "channel_id", challenge_id
        )
        ctf_id = challenge_dict["ctf_channel_id"]
        ctf = self.get_ctf(ctf_id=ctf_id)
        for chal in ctf.challenges:
            if chal.channel_id == challenge_id:
                chal.name = new_name
                break
        self.add_ctf(ctf)

    def _search_all_ctfs_for_challenge(self, field: str, value: str) -> Dict:
        query = {"query": {"match_all": {}}}
        result = self.search(CTF_INDEX, query)
        the_chal_dict = {}
        if result["hits"]["total"]["value"] > 0:
            for ctf_dict in result["hits"]["hits"]:
                for chal_dict in ctf_dict["_source"]["challenges"]:
                    if value == chal_dict[field]:
                        the_chal_dict = chal_dict
        return the_chal_dict

    def add(self, index: str, document: Dict[Any, Any], doc_id: str):
        self.client.index(index=index, body=document, id=doc_id, refresh=True)

    def update(self, index: str, document: Dict[Any, Any], doc_id: str):
        self.client.update(index=index, body=document, id=doc_id, refresh=True)

    def get(self, index: str, doc_id: str):
        return self.client.get(index=index, id=doc_id)

    def search(self, index: str, query: Any):
        return self.client.search(index=index, body=query)

    def delete(self, index, doc_id):
        self.client.delete(index=index, id=doc_id)
