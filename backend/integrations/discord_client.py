"""Discord Bot API client for AEP connector integration.

Discord uses a Bot OAuth2 flow for server integrations.

Supports:
- Guilds (servers)
- Channels
- Messages
- Members
- Webhooks
"""

from typing import Any, Dict, List, Optional
import httpx
import structlog

logger = structlog.get_logger(__name__)


class DiscordClient:
    """
    Discord Bot API client for AEP NAVI integration.

    Uses Bot token authentication for full guild access.
    """

    API_URL = "https://discord.com/api/v10"

    def __init__(
        self,
        bot_token: str,
        timeout: float = 30.0,
    ):
        self.bot_token = bot_token
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        logger.info("DiscordClient initialized")

    async def __aenter__(self) -> "DiscordClient":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers=self._headers(),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
        }

    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a GET request to the Discord API."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async with context manager."
            )

        url = f"{self.API_URL}{endpoint}"
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Make a POST request to the Discord API."""
        if not self._client:
            raise RuntimeError(
                "Client not initialized. Use async with context manager."
            )

        url = f"{self.API_URL}{endpoint}"
        response = await self._client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # Bot/User Methods
    # -------------------------------------------------------------------------

    async def get_current_user(self) -> Dict[str, Any]:
        """
        Get the current bot user.

        Returns:
            Bot user information
        """
        user = await self._get("/users/@me")
        logger.info("Discord bot user fetched", username=user.get("username"))
        return user

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get a user by ID.

        Args:
            user_id: Discord user ID

        Returns:
            User information
        """
        return await self._get(f"/users/{user_id}")

    # -------------------------------------------------------------------------
    # Guild Methods
    # -------------------------------------------------------------------------

    async def get_current_guilds(self) -> List[Dict[str, Any]]:
        """
        Get guilds the bot is a member of.

        Returns:
            List of guild objects
        """
        guilds = await self._get("/users/@me/guilds")
        logger.info("Discord guilds fetched", count=len(guilds))
        return guilds

    async def get_guild(self, guild_id: str) -> Dict[str, Any]:
        """
        Get a guild by ID.

        Args:
            guild_id: Discord guild ID

        Returns:
            Guild information
        """
        return await self._get(f"/guilds/{guild_id}")

    async def get_guild_channels(self, guild_id: str) -> List[Dict[str, Any]]:
        """
        Get all channels in a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            List of channel objects
        """
        channels = await self._get(f"/guilds/{guild_id}/channels")
        logger.info("Discord channels fetched", guild_id=guild_id, count=len(channels))
        return channels

    async def get_guild_members(
        self,
        guild_id: str,
        limit: int = 100,
        after: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get members of a guild.

        Args:
            guild_id: Discord guild ID
            limit: Max members to return (1-1000)
            after: Get members after this user ID

        Returns:
            List of member objects
        """
        params: Dict[str, Any] = {"limit": min(limit, 1000)}
        if after:
            params["after"] = after

        members = await self._get(f"/guilds/{guild_id}/members", params=params)
        logger.info("Discord members fetched", guild_id=guild_id, count=len(members))
        return members

    # -------------------------------------------------------------------------
    # Channel Methods
    # -------------------------------------------------------------------------

    async def get_channel(self, channel_id: str) -> Dict[str, Any]:
        """
        Get a channel by ID.

        Args:
            channel_id: Discord channel ID

        Returns:
            Channel information
        """
        return await self._get(f"/channels/{channel_id}")

    async def get_channel_messages(
        self,
        channel_id: str,
        limit: int = 50,
        before: Optional[str] = None,
        after: Optional[str] = None,
        around: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get messages from a channel.

        Args:
            channel_id: Discord channel ID
            limit: Max messages to return (1-100)
            before: Get messages before this message ID
            after: Get messages after this message ID
            around: Get messages around this message ID

        Returns:
            List of message objects
        """
        params: Dict[str, Any] = {"limit": min(limit, 100)}
        if before:
            params["before"] = before
        if after:
            params["after"] = after
        if around:
            params["around"] = around

        messages = await self._get(f"/channels/{channel_id}/messages", params=params)
        logger.info(
            "Discord messages fetched", channel_id=channel_id, count=len(messages)
        )
        return messages

    async def send_message(
        self,
        channel_id: str,
        content: str,
        embeds: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to a channel.

        Args:
            channel_id: Discord channel ID
            content: Message content
            embeds: Optional message embeds

        Returns:
            Created message object
        """
        data: Dict[str, Any] = {"content": content}
        if embeds:
            data["embeds"] = embeds

        message = await self._post(f"/channels/{channel_id}/messages", data)
        logger.info(
            "Discord message sent", channel_id=channel_id, message_id=message.get("id")
        )
        return message

    # -------------------------------------------------------------------------
    # Thread Methods
    # -------------------------------------------------------------------------

    async def get_channel_threads(
        self,
        channel_id: str,
        archived: bool = False,
    ) -> Dict[str, Any]:
        """
        Get threads in a channel.

        Args:
            channel_id: Discord channel ID
            archived: Get archived threads

        Returns:
            Thread list response
        """
        if archived:
            endpoint = f"/channels/{channel_id}/threads/archived/public"
        else:
            endpoint = f"/channels/{channel_id}/threads/active"

        return await self._get(endpoint)

    async def get_thread_messages(
        self,
        thread_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get messages from a thread.

        Args:
            thread_id: Discord thread ID
            limit: Max messages to return

        Returns:
            List of message objects
        """
        return await self.get_channel_messages(thread_id, limit=limit)

    # -------------------------------------------------------------------------
    # Webhook Methods
    # -------------------------------------------------------------------------

    async def get_guild_webhooks(self, guild_id: str) -> List[Dict[str, Any]]:
        """
        Get all webhooks for a guild.

        Args:
            guild_id: Discord guild ID

        Returns:
            List of webhook objects
        """
        return await self._get(f"/guilds/{guild_id}/webhooks")

    async def get_channel_webhooks(self, channel_id: str) -> List[Dict[str, Any]]:
        """
        Get webhooks for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            List of webhook objects
        """
        return await self._get(f"/channels/{channel_id}/webhooks")

    async def create_webhook(
        self,
        channel_id: str,
        name: str,
        avatar: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a webhook for a channel.

        Args:
            channel_id: Discord channel ID
            name: Webhook name
            avatar: Base64 encoded avatar image

        Returns:
            Created webhook object
        """
        data: Dict[str, Any] = {"name": name}
        if avatar:
            data["avatar"] = avatar

        webhook = await self._post(f"/channels/{channel_id}/webhooks", data)
        logger.info(
            "Discord webhook created",
            channel_id=channel_id,
            webhook_id=webhook.get("id"),
        )
        return webhook

    # -------------------------------------------------------------------------
    # Search Methods
    # -------------------------------------------------------------------------

    async def search_guild_messages(
        self,
        guild_id: str,
        content: Optional[str] = None,
        author_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        has: Optional[str] = None,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Search messages in a guild.

        Note: Requires the bot to have the MESSAGE_CONTENT intent.

        Args:
            guild_id: Discord guild ID
            content: Search query
            author_id: Filter by author
            channel_id: Filter by channel
            has: Filter by attachment type (link, embed, file, video, image, sound)
            limit: Max results

        Returns:
            Search results
        """
        params: Dict[str, Any] = {"limit": min(limit, 25)}
        if content:
            params["content"] = content
        if author_id:
            params["author_id"] = author_id
        if channel_id:
            params["channel_id"] = channel_id
        if has:
            params["has"] = has

        return await self._get(f"/guilds/{guild_id}/messages/search", params=params)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_channel_type_name(self, channel_type: int) -> str:
        """
        Get human-readable channel type name.

        Args:
            channel_type: Discord channel type integer

        Returns:
            Channel type name
        """
        types = {
            0: "text",
            1: "dm",
            2: "voice",
            3: "group_dm",
            4: "category",
            5: "announcement",
            10: "announcement_thread",
            11: "public_thread",
            12: "private_thread",
            13: "stage_voice",
            14: "directory",
            15: "forum",
            16: "media",
        }
        return types.get(channel_type, "unknown")

    def extract_message_content(self, message: Dict[str, Any]) -> str:
        """
        Extract text content from a Discord message.

        Args:
            message: Discord message object

        Returns:
            Message content with embeds
        """
        parts = []

        # Main content
        content = message.get("content", "")
        if content:
            parts.append(content)

        # Embeds
        embeds = message.get("embeds", [])
        for embed in embeds:
            title = embed.get("title", "")
            description = embed.get("description", "")
            if title:
                parts.append(f"[Embed: {title}]")
            if description:
                parts.append(description[:200])

        # Attachments
        attachments = message.get("attachments", [])
        for att in attachments:
            filename = att.get("filename", "attachment")
            parts.append(f"[Attachment: {filename}]")

        return "\n".join(parts)
