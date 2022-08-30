import os
from typing import Any, Dict, List

from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError, RequestError
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

        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_compress=True,
        )
        try:
            response = self.client.indices.create(CTF_INDEX)
            log.debug(f"Creating index: {response}")
        except RequestError as e:
            log.debug(f"Creating index: {e}")

    def add_ctf(self, ctf: CTF):
        self.add(CTF_INDEX, ctf.dict(), ctf.channel_id)

    def get_ctfs(self) -> List[CTF]:
        ctf_list = []
        query: Dict = {"query": {"match_all": {}}}
        result = self.search(CTF_INDEX, query)
        if result["hits"]["total"]["value"] > 0:
            for ctf_dict in result["hits"]["hits"]:
                try:
                    ctf_list.append(CTF.parse_obj(ctf_dict["_source"]))
                except ValidationError as e:
                    log.warning(f"Failed to build Challenge from obj: {ctf_dict}")
        return ctf_list

    def get_ctf(
        self, ctf_id: str = "", ctf_name: str = "", challenge_id=""
    ) -> CTF | None:
        if not (ctf_id or ctf_name):
            raise ValueError("One of ctf_id or ctf_name must be specified.")

        ctf_doc = {}
        if challenge_id and not ctf_id:
            the_chal_dict = self._search_all_ctfs_for_challenge(
                "channel_id", challenge_id
            )
            ctf_id = the_chal_dict.get("ctf_channel_id")
        if ctf_id:
            try:
                result = self.get(CTF_INDEX, ctf_id)
                if result["found"] is True:
                    ctf_doc = result["_source"]
            except NotFoundError as e:
                log.info(f"CTF with id {ctf_id} not found.")
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
            else:
                log.info(f"CTF with name {ctf_name} not found.")

        try:
            if ctf_doc:
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
        self.update(CTF_INDEX, {"doc": {"name": ctf_name}}, ctf_id)
        ctf = self.get_ctf(ctf_id=ctf_id)
        ctf.name = ctf_name
        self.add_ctf(ctf)

    def add_challenge(self, challenge: Challenge, ctf_id: str):
        ctf = self.get_ctf(ctf_id)
        if not ctf:
            raise ValueError(f"No CTF with id {ctf_id}.")
        ctf.add_challenge(challenge)
        self.add_ctf(ctf)

    def get_challenges(self, ctf_id: str) -> List[Challenge]:
        ctf = self.get_ctf(ctf_id=ctf_id)
        if ctf:
            return ctf.challenges
        return []

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

    def remove_challenge(self, challenge_id: str, ctf_id: str):
        ctf = self.get_ctf(ctf_id=ctf_id)
        ctf.challenges = list(
            filter(
                lambda challenge: challenge.channel_id != challenge_id,
                ctf.challenges,
            )
        )
        self.add_ctf(ctf)

    def update_challenge(self, challenge_id: str, update_func: Any, ctf_id: str = ""):
        if ctf_id:
            ctf = self.get_ctf(ctf_id=ctf_id)
        else:
            challenge_dict = self._search_all_ctfs_for_challenge(
                "channel_id", challenge_id
            )
            ctf_id = challenge_dict["ctf_channel_id"]
            ctf = self.get_ctf(ctf_id=ctf_id)
        if ctf:
            for challenge in ctf.challenges:
                if challenge.channel_id == challenge_id:
                    update_func(challenge)
            self.add_ctf(ctf)
        else:
            log.warning(f"No CTF with id {ctf_id} found.")

    def update_challenge_name(self, challenge_id: str, new_name: str):
        challenge_dict = self._search_all_ctfs_for_challenge("channel_id", challenge_id)
        ctf_id = challenge_dict["ctf_channel_id"]
        ctf = self.get_ctf(ctf_id=ctf_id)
        for chal in ctf.challenges:
            if chal.channel_id == challenge_id:
                chal.name = new_name
                break
        self.add_ctf(ctf)

    def _search_all_ctfs_for_challenge(self, field: str, value: str) -> Dict:
        query: Dict = {"query": {"match_all": {}}}
        result = self.search(CTF_INDEX, query)
        the_chal_dict = {}
        if result["hits"]["total"]["value"] > 0:
            for ctf_dict in result["hits"]["hits"]:
                for chal_dict in ctf_dict["_source"]["challenges"]:
                    if value == chal_dict[field]:
                        the_chal_dict = chal_dict
        return the_chal_dict

    def get_challenge_from_args_or_channel(self, args, channel_id) -> Challenge | None:
        """
        Helper method for getting a Challenge either from arguments or current channel.
        Return the corresponding Challenge if called from a challenge channel.
        Return the Challenge corresponding to the first argument if called from the
        CTF channel.
        Return None if no Challenge can be found.
        """

        # Check if we're currently in a challenge channel
        current_chal = self.get_challenge(challenge_id=channel_id)

        if current_chal:
            # User is in the challenge channel
            challenge = current_chal
        else:
            # Assume user is in the ctf channel
            challenge_name = args[0].lower().strip("*")
            challenge = self.get_challenge(
                challenge_name=challenge_name, ctf_id=channel_id
            )
        return challenge

    def add(self, index: str, document: Dict[Any, Any], doc_id: str):
        response = self.client.index(
            index=index, body=document, id=doc_id, refresh=True
        )
        log.debug(f"Adding document: {response}")

    def update(self, index: str, document: Dict[Any, Any], doc_id: str):
        response = self.client.update(
            index=index, body=document, id=doc_id, refresh=True
        )
        log.debug(f"Updating document: {response}")

    def get(self, index: str, doc_id: str):
        return self.client.get(index=index, id=doc_id)

    def search(self, index: str, query: Any):
        return self.client.search(index=index, body=query)

    def delete(self, index, doc_id):
        self.client.delete(index=index, id=doc_id)
