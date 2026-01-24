"""
Trello API client for board and card management.

Provides access to Trello boards, lists, cards, and members.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import structlog

import httpx

logger = structlog.get_logger(__name__)


class TrelloClient:
    """
    Async Trello API client.

    Supports:
    - Board management
    - List operations
    - Card operations
    - Member management
    - Webhooks
    """

    BASE_URL = "https://api.trello.com/1"

    def __init__(
        self,
        api_key: str,
        api_token: str,
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.api_token = api_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "TrelloClient":
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        return self._client

    def _auth_params(self) -> Dict[str, str]:
        """Get authentication parameters."""
        return {"key": self.api_key, "token": self.api_token}

    # -------------------------------------------------------------------------
    # Members
    # -------------------------------------------------------------------------

    async def get_me(self) -> Dict[str, Any]:
        """Get the authenticated member."""
        resp = await self.client.get("/members/me", params=self._auth_params())
        resp.raise_for_status()
        return resp.json()

    async def get_member(
        self,
        member_id: str,
    ) -> Dict[str, Any]:
        """Get a specific member."""
        resp = await self.client.get(
            f"/members/{member_id}", params=self._auth_params()
        )
        resp.raise_for_status()
        return resp.json()

    async def get_member_boards(
        self,
        member_id: str = "me",
        filter: str = "all",
    ) -> List[Dict[str, Any]]:
        """Get boards for a member."""
        params = {**self._auth_params(), "filter": filter}
        resp = await self.client.get(f"/members/{member_id}/boards", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Boards
    # -------------------------------------------------------------------------

    async def get_board(
        self,
        board_id: str,
        lists: bool = False,
        cards: str = "none",
        members: bool = False,
    ) -> Dict[str, Any]:
        """
        Get a board.

        Args:
            board_id: Board ID
            lists: Include lists
            cards: Include cards (none, all, open, closed)
            members: Include members

        Returns:
            Board data
        """
        params = {
            **self._auth_params(),
            "lists": str(lists).lower(),
            "cards": cards,
            "members": str(members).lower(),
        }
        resp = await self.client.get(f"/boards/{board_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_board(
        self,
        name: str,
        desc: Optional[str] = None,
        default_lists: bool = True,
        default_labels: bool = True,
        prefs_background: str = "blue",
    ) -> Dict[str, Any]:
        """Create a new board."""
        params = {
            **self._auth_params(),
            "name": name,
            "defaultLists": str(default_lists).lower(),
            "defaultLabels": str(default_labels).lower(),
            "prefs_background": prefs_background,
        }
        if desc:
            params["desc"] = desc

        resp = await self.client.post("/boards", params=params)
        resp.raise_for_status()
        return resp.json()

    async def update_board(
        self,
        board_id: str,
        name: Optional[str] = None,
        desc: Optional[str] = None,
        closed: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a board."""
        params = self._auth_params()
        if name is not None:
            params["name"] = name
        if desc is not None:
            params["desc"] = desc
        if closed is not None:
            params["closed"] = str(closed).lower()

        resp = await self.client.put(f"/boards/{board_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def delete_board(
        self,
        board_id: str,
    ) -> Dict[str, Any]:
        """Delete a board."""
        resp = await self.client.delete(
            f"/boards/{board_id}", params=self._auth_params()
        )
        resp.raise_for_status()
        return resp.json()

    async def get_board_members(
        self,
        board_id: str,
    ) -> List[Dict[str, Any]]:
        """Get members of a board."""
        resp = await self.client.get(
            f"/boards/{board_id}/members",
            params=self._auth_params(),
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Lists
    # -------------------------------------------------------------------------

    async def get_board_lists(
        self,
        board_id: str,
        cards: str = "none",
        filter: str = "all",
    ) -> List[Dict[str, Any]]:
        """Get lists on a board."""
        params = {
            **self._auth_params(),
            "cards": cards,
            "filter": filter,
        }
        resp = await self.client.get(f"/boards/{board_id}/lists", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_list(
        self,
        board_id: str,
        name: str,
        pos: str = "bottom",
    ) -> Dict[str, Any]:
        """Create a list on a board."""
        params = {
            **self._auth_params(),
            "name": name,
            "idBoard": board_id,
            "pos": pos,
        }
        resp = await self.client.post("/lists", params=params)
        resp.raise_for_status()
        return resp.json()

    async def update_list(
        self,
        list_id: str,
        name: Optional[str] = None,
        closed: Optional[bool] = None,
        pos: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a list."""
        params = self._auth_params()
        if name is not None:
            params["name"] = name
        if closed is not None:
            params["closed"] = str(closed).lower()
        if pos is not None:
            params["pos"] = pos

        resp = await self.client.put(f"/lists/{list_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def archive_all_cards(
        self,
        list_id: str,
    ) -> Dict[str, Any]:
        """Archive all cards in a list."""
        resp = await self.client.post(
            f"/lists/{list_id}/archiveAllCards",
            params=self._auth_params(),
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Cards
    # -------------------------------------------------------------------------

    async def get_card(
        self,
        card_id: str,
        checklists: str = "none",
        attachments: bool = False,
        members: bool = False,
    ) -> Dict[str, Any]:
        """Get a card."""
        params = {
            **self._auth_params(),
            "checklists": checklists,
            "attachments": str(attachments).lower(),
            "members": str(members).lower(),
        }
        resp = await self.client.get(f"/cards/{card_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_list_cards(
        self,
        list_id: str,
    ) -> List[Dict[str, Any]]:
        """Get cards in a list."""
        resp = await self.client.get(
            f"/lists/{list_id}/cards",
            params=self._auth_params(),
        )
        resp.raise_for_status()
        return resp.json()

    async def get_board_cards(
        self,
        board_id: str,
        filter: str = "visible",
    ) -> List[Dict[str, Any]]:
        """Get cards on a board."""
        params = {**self._auth_params(), "filter": filter}
        resp = await self.client.get(f"/boards/{board_id}/cards", params=params)
        resp.raise_for_status()
        return resp.json()

    async def create_card(
        self,
        list_id: str,
        name: str,
        desc: Optional[str] = None,
        pos: str = "bottom",
        due: Optional[str] = None,
        member_ids: Optional[List[str]] = None,
        label_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a card.

        Args:
            list_id: List ID to add card to
            name: Card name
            desc: Card description
            pos: Position (top, bottom, or number)
            due: Due date (ISO 8601)
            member_ids: Member IDs to assign
            label_ids: Label IDs to add

        Returns:
            Created card
        """
        params: Dict[str, Any] = {
            **self._auth_params(),
            "idList": list_id,
            "name": name,
            "pos": pos,
        }
        if desc:
            params["desc"] = desc
        if due:
            params["due"] = due
        if member_ids:
            params["idMembers"] = ",".join(member_ids)
        if label_ids:
            params["idLabels"] = ",".join(label_ids)

        resp = await self.client.post("/cards", params=params)
        resp.raise_for_status()
        return resp.json()

    async def update_card(
        self,
        card_id: str,
        name: Optional[str] = None,
        desc: Optional[str] = None,
        list_id: Optional[str] = None,
        closed: Optional[bool] = None,
        due: Optional[str] = None,
        due_complete: Optional[bool] = None,
        pos: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a card."""
        params = self._auth_params()
        if name is not None:
            params["name"] = name
        if desc is not None:
            params["desc"] = desc
        if list_id is not None:
            params["idList"] = list_id
        if closed is not None:
            params["closed"] = str(closed).lower()
        if due is not None:
            params["due"] = due
        if due_complete is not None:
            params["dueComplete"] = str(due_complete).lower()
        if pos is not None:
            params["pos"] = pos

        resp = await self.client.put(f"/cards/{card_id}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def delete_card(
        self,
        card_id: str,
    ) -> Dict[str, Any]:
        """Delete a card."""
        resp = await self.client.delete(f"/cards/{card_id}", params=self._auth_params())
        resp.raise_for_status()
        return resp.json()

    async def add_card_comment(
        self,
        card_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Add a comment to a card."""
        params = {**self._auth_params(), "text": text}
        resp = await self.client.post(
            f"/cards/{card_id}/actions/comments", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def get_card_actions(
        self,
        card_id: str,
        filter: str = "all",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get actions (activity) on a card."""
        params = {
            **self._auth_params(),
            "filter": filter,
            "limit": limit,
        }
        resp = await self.client.get(f"/cards/{card_id}/actions", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Labels
    # -------------------------------------------------------------------------

    async def get_board_labels(
        self,
        board_id: str,
    ) -> List[Dict[str, Any]]:
        """Get labels on a board."""
        resp = await self.client.get(
            f"/boards/{board_id}/labels",
            params=self._auth_params(),
        )
        resp.raise_for_status()
        return resp.json()

    async def create_label(
        self,
        board_id: str,
        name: str,
        color: str,
    ) -> Dict[str, Any]:
        """Create a label on a board."""
        params = {
            **self._auth_params(),
            "idBoard": board_id,
            "name": name,
            "color": color,
        }
        resp = await self.client.post("/labels", params=params)
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Checklists
    # -------------------------------------------------------------------------

    async def get_card_checklists(
        self,
        card_id: str,
    ) -> List[Dict[str, Any]]:
        """Get checklists on a card."""
        resp = await self.client.get(
            f"/cards/{card_id}/checklists",
            params=self._auth_params(),
        )
        resp.raise_for_status()
        return resp.json()

    async def create_checklist(
        self,
        card_id: str,
        name: str,
    ) -> Dict[str, Any]:
        """Create a checklist on a card."""
        params = {
            **self._auth_params(),
            "idCard": card_id,
            "name": name,
        }
        resp = await self.client.post("/checklists", params=params)
        resp.raise_for_status()
        return resp.json()

    async def add_checklist_item(
        self,
        checklist_id: str,
        name: str,
        checked: bool = False,
    ) -> Dict[str, Any]:
        """Add an item to a checklist."""
        params = {
            **self._auth_params(),
            "name": name,
            "checked": str(checked).lower(),
        }
        resp = await self.client.post(
            f"/checklists/{checklist_id}/checkItems",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------------

    async def list_webhooks(
        self,
    ) -> List[Dict[str, Any]]:
        """List all webhooks for the token."""
        resp = await self.client.get(
            f"/tokens/{self.api_token}/webhooks",
            params=self._auth_params(),
        )
        resp.raise_for_status()
        return resp.json()

    async def create_webhook(
        self,
        callback_url: str,
        id_model: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook.

        Args:
            callback_url: URL to receive webhook events
            id_model: ID of model to watch (board, card, etc.)
            description: Webhook description

        Returns:
            Created webhook
        """
        params: Dict[str, Any] = {
            **self._auth_params(),
            "callbackURL": callback_url,
            "idModel": id_model,
        }
        if description:
            params["description"] = description

        resp = await self.client.post("/webhooks", params=params)
        resp.raise_for_status()
        return resp.json()

    async def delete_webhook(
        self,
        webhook_id: str,
    ) -> Dict[str, Any]:
        """Delete a webhook."""
        resp = await self.client.delete(
            f"/webhooks/{webhook_id}",
            params=self._auth_params(),
        )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    async def search(
        self,
        query: str,
        model_types: str = "cards,boards",
        board_ids: Optional[List[str]] = None,
        cards_limit: int = 10,
        boards_limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Search Trello.

        Args:
            query: Search query
            model_types: Types to search (cards, boards, organizations, members)
            board_ids: Limit to specific boards
            cards_limit: Max cards to return
            boards_limit: Max boards to return

        Returns:
            Search results
        """
        params: Dict[str, Any] = {
            **self._auth_params(),
            "query": query,
            "modelTypes": model_types,
            "cards_limit": cards_limit,
            "boards_limit": boards_limit,
        }
        if board_ids:
            params["idBoards"] = ",".join(board_ids)

        resp = await self.client.get("/search", params=params)
        resp.raise_for_status()
        return resp.json()
