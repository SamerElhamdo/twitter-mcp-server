#!/usr/bin/env python3
"""
Twitter MCP Server using twikit

This server provides Twitter functionality through the Model Context Protocol (MCP).
It uses twikit for Twitter API interactions and supports authentication via ct0 and auth_token
cookies provided by the LLM model or environment variables.
"""

import asyncio
import os
import json
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)
import mcp.types as types

from twikit import Client

# Load environment variables
load_dotenv()

class TwitterMCPServer:
    def __init__(self):
        self.client = None
        self.server = Server("twitter-mcp")
        self.authenticated_clients = {}  # Cache for authenticated clients
        self.setup_handlers()

    def setup_handlers(self):
        """Set up MCP server handlers"""
        
        @self.server.list_resources()
        async def handle_list_resources() -> list[Resource]:
            """List available Twitter resources"""
            return [
                Resource(
                    uri="twitter://timeline",
                    name="Twitter Timeline",
                    description="Get tweets from your timeline (requires ct0 and auth_token)",
                    mimeType="application/json"
                ),
                Resource(
                    uri="twitter://user-tweets",
                    name="User Tweets",
                    description="Get tweets from a specific user (requires ct0 and auth_token)",
                    mimeType="application/json"
                ),
                Resource(
                    uri="twitter://search",
                    name="Search Tweets",
                    description="Search for tweets (requires ct0 and auth_token)",
                    mimeType="application/json"
                ),
                Resource(
                    uri="twitter://dm-history",
                    name="DM History",
                    description="Get direct message history with a user (requires ct0 and auth_token)",
                    mimeType="application/json"
                )
            ]

        @self.server.read_resource()
        async def handle_read_resource(uri: types.AnyUrl) -> str:
            """Read a specific Twitter resource"""
            # For resources, we'll use environment variables as fallback
            auth_token = os.getenv("TWITTER_AUTH_TOKEN")
            ct0 = os.getenv("TWITTER_CT0")
            if not auth_token or not ct0:
                return json.dumps({
                    "error": "Authentication required. Please provide TWITTER_AUTH_TOKEN and TWITTER_CT0 environment variables or use tools with ct0 and auth_token parameters."
                }, indent=2)
            
            client = await self._get_authenticated_client(ct0, auth_token)
            
            if uri.scheme != "twitter":
                raise ValueError(f"Unsupported URI scheme: {uri.scheme}")
            
            path = uri.path.lstrip("/")
            
            if path == "timeline":
                tweets = await self._get_timeline(client)
                return json.dumps(tweets, indent=2)
            elif path == "user-tweets":
                # Extract username from query parameters if provided
                username = getattr(uri, 'fragment', None) or "twitter"
                tweets = await self._get_user_tweets(client, username)
                return json.dumps(tweets, indent=2)
            elif path == "search":
                # Extract query from fragment if provided, use 'Latest' product by default
                query = getattr(uri, 'fragment', None) or "python"
                tweets = await self._search_tweets(client, query, product="Latest")
                return json.dumps(tweets, indent=2)
            elif path == "dm-history":
                # Extract username from fragment if provided
                username = getattr(uri, 'fragment', None) or "twitter"
                dm_history = await self._get_dm_history(client, username)
                return json.dumps(dm_history, indent=2)
            else:
                raise ValueError(f"Unknown resource path: {path}")

        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available Twitter tools"""
            return [
                Tool(
                    name="tweet",
                    description="Post a tweet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The text content of the tweet",
                                "maxLength": 280
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["text", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_user_info",
                    description="Get information about a Twitter user",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "username": {
                                "type": "string",
                                "description": "The username (without @) to get info for"
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["username", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="search_tweets",
                    description="Search for tweets with a specific query",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of tweets to return (default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 100
                            },
                            "product": {
                                "type": "string",
                                "description": "Type of results to return (e.g., 'Top' or 'Latest')",
                                "enum": ["Top", "Latest"],
                                "default": "Latest"
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["query", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_timeline",
                    description="Get tweets from your timeline",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "count": {
                                "type": "integer",
                                "description": "Number of tweets to return (default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 100
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_latest_timeline",
                    description="Get latest tweets from your timeline",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "count": {
                                "type": "integer",
                                "description": "Number of tweets to return (default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 100
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="like_tweet",
                    description="Like a tweet by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tweet_id": {
                                "type": "string",
                                "description": "The ID of the tweet to like"
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["tweet_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="retweet",
                    description="Retweet a tweet by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tweet_id": {
                                "type": "string",
                                "description": "The ID of the tweet to retweet"
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["tweet_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="authenticate",
                    description="Test authentication with provided cookies and return user info",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie to test"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie to test"
                            }
                        },
                        "required": ["ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="send_dm",
                    description="Send a direct message to a user",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "recipient_username": {
                                "type": "string",
                                "description": "The username (without @) of the recipient"
                            },
                            "text": {
                                "type": "string",
                                "description": "The message text to send"
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["recipient_username", "text", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_dm_history",
                    description="Get direct message history with a user",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "recipient_username": {
                                "type": "string",
                                "description": "The username (without @) to get DM history with"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of messages to return (default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 100
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["recipient_username", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="add_reaction_to_message",
                    description="Add a reaction (emoji) to a direct message",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "The ID of the message to react to"
                            },
                            "emoji": {
                                "type": "string",
                                "description": "The emoji to react with (e.g., '❤️', '👍', '😂')"
                            },
                            "conversation_id": {
                                "type": "string",
                                "description": "The conversation ID"
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["message_id", "emoji", "conversation_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="delete_dm",
                    description="Delete a direct message",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message_id": {
                                "type": "string",
                                "description": "The ID of the message to delete"
                            },
                            "ct0": {
                                "type": "string",
                                "description": "Twitter ct0 cookie (required)"
                            },
                            "auth_token": {
                                "type": "string",
                                "description": "Twitter auth_token cookie (required)"
                            }
                        },
                        "required": ["message_id", "ct0", "auth_token"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
            """Handle tool calls"""
            try:
                # Extract cookies from arguments
                ct0 = arguments.get("ct0")
                auth_token = arguments.get("auth_token")
                if not ct0 or not auth_token:
                    return [types.TextContent(type="text", text="Error: Both ct0 and auth_token cookies are required for all operations")]

                # Get authenticated client
                client = await self._get_authenticated_client(ct0, auth_token)
                
                if name == "authenticate":
                    result = await self._test_authentication(client)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "tweet":
                    result = await self._post_tweet(client, arguments["text"])
                    return [types.TextContent(type="text", text=f"Tweet posted successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "get_user_info":
                    result = await self._get_user_info(client, arguments["username"])
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "search_tweets":
                    count = arguments.get("count", 20)
                    product = arguments.get("product", "Latest")
                    # Ensure the product value is only 'Top' or 'Latest'
                    if product not in ("Top", "Latest"):
                        product = "Latest"
                    
                    result = await self._search_tweets(client, arguments["query"], count, product)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_timeline":
                    count = arguments.get("count", 20)
                    result = await self._get_timeline(client, count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_latest_timeline":
                    count = arguments.get("count", 20)
                    result = await self._get_latest_timeline(client, count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "like_tweet":
                    result = await self._like_tweet(client, arguments["tweet_id"])
                    return [types.TextContent(type="text", text=f"Tweet liked successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "retweet":
                    result = await self._retweet(client, arguments["tweet_id"])
                    return [types.TextContent(type="text", text=f"Tweet retweeted successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "send_dm":
                    result = await self._send_dm(client, arguments["recipient_username"], arguments["text"])
                    return [types.TextContent(type="text", text=f"DM sent successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "get_dm_history":
                    count = arguments.get("count", 20)
                    result = await self._get_dm_history(client, arguments["recipient_username"], count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "add_reaction_to_message":
                    result = await self._add_reaction_to_message(client, arguments["message_id"], arguments["emoji"], arguments["conversation_id"])
                    return [types.TextContent(type="text", text=f"Reaction added successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "delete_dm":
                    result = await self._delete_dm(client, arguments["message_id"])
                    return [types.TextContent(type="text", text=f"DM deleted successfully: {json.dumps(result, indent=2)}")]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")

            except Exception as e:
                return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    async def _get_authenticated_client(self, ct0: str, auth_token: str) -> Client:
        """Get or create an authenticated client for the given cookies"""
        # Use ct0 as cache key since it's shorter and unique per session
        cache_key = ct0
        
        # Check if we already have an authenticated client for these cookies
        if cache_key in self.authenticated_clients:
            return self.authenticated_clients[cache_key]
        
        # Create new client and authenticate
        client = Client('en-US')
        
        # Set the cookies directly
        cookies = {
            'ct0': ct0,
            'auth_token': auth_token
        }
        client.set_cookies(cookies)
        
        # Test authentication by getting user info
        try:
            # Use user_id() to test authentication instead of get_me()
            user_id = await client.user_id()
            if not user_id:
                raise ValueError("Failed to get user ID")
        except Exception as e:
            raise ValueError(f"Authentication failed with provided cookies: {str(e)}")
        
        # Cache the authenticated client
        self.authenticated_clients[cache_key] = client
        return client

    async def _test_authentication(self, client: Client) -> Dict[str, Any]:
        """Test authentication and return user info"""
        # Get user ID first, then use it to get user details
        user_id = await client.user_id()
        user = await client.user(user_id)
        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "username": user.screen_name,
                "name": user.name,
                "followers_count": user.followers_count,
                "following_count": user.following_count,
                "tweet_count": user.statuses_count,
                "verified": user.verified
            }
        }

    async def _post_tweet(self, client: Client, text: str) -> Dict[str, Any]:
        """Post a tweet"""
        tweet = await client.create_tweet(text=text)
        return {
            "id": tweet.id,
            "text": tweet.text,
            "created_at": str(tweet.created_at),
            "author": tweet.user.screen_name
        }

    async def _get_user_info(self, client: Client, username: str) -> Dict[str, Any]:
        """Get user information"""
        user = await client.get_user_by_screen_name(username)
        return {
            "id": user.id,
            "username": user.screen_name,
            "name": user.name,
            "description": user.description,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "tweet_count": user.statuses_count,
            "verified": user.verified,
            "created_at": str(user.created_at)
        }

    async def _search_tweets(self, client: Client, query: str, count: int = 20, product: str = "Latest") -> List[Dict[str, Any]]:
        """Search for tweets"""
        tweets = await client.search_tweet(query, product=product, count=count)
        return [
            {
                "id": tweet.id,
                "text": tweet.text,
                "author": tweet.user.screen_name,
                "author_name": tweet.user.name,
                "created_at": str(tweet.created_at),
                "like_count": tweet.favorite_count,
                "retweet_count": tweet.retweet_count,
                "reply_count": tweet.reply_count
            }
            for tweet in tweets
        ]

    async def _get_timeline(self, client: Client, count: int = 20) -> List[Dict[str, Any]]:
        """Get timeline tweets"""
        # Use get_timeline() instead of get_home_timeline()
        tweets = await client.get_timeline(count=count)
        return [
            {
                "id": tweet.id,
                "text": tweet.text,
                "author": tweet.user.screen_name,
                "author_name": tweet.user.name,
                "created_at": str(tweet.created_at),
                "like_count": tweet.favorite_count,
                "retweet_count": tweet.retweet_count,
                "reply_count": tweet.reply_count
            }
            for tweet in tweets
        ]

    async def _get_user_tweets(self, client: Client, username: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get tweets from a specific user"""
        user = await client.get_user_by_screen_name(username)
        tweets = await client.get_user_tweets(user.id, tweet_type='Tweets', count=count)
        return [
            {
                "id": tweet.id,
                "text": tweet.text,
                "author": tweet.user.screen_name,
                "author_name": tweet.user.name,
                "created_at": str(tweet.created_at),
                "like_count": tweet.favorite_count,
                "retweet_count": tweet.retweet_count,
                "reply_count": tweet.reply_count
            }
            for tweet in tweets
        ]

    async def _like_tweet(self, client: Client, tweet_id: str) -> Dict[str, Any]:
        """Like a tweet"""
        result = await client.favorite_tweet(tweet_id)
        return {"success": True, "tweet_id": tweet_id}

    async def _retweet(self, client: Client, tweet_id: str) -> Dict[str, Any]:
        """Retweet a tweet"""
        result = await client.retweet(tweet_id)
        return {"success": True, "tweet_id": tweet_id}

    async def _get_latest_timeline(self, client: Client, count: int = 20) -> List[Dict[str, Any]]:
        """Get latest timeline tweets"""
        # Use get_latest_timeline() instead of get_home_timeline()
        tweets = await client.get_latest_timeline(count=count)
        return [
            {
                "id": tweet.id,
                "text": tweet.text,
                "author": tweet.user.screen_name,
                "author_name": tweet.user.name,
                "created_at": str(tweet.created_at),
                "like_count": tweet.favorite_count,
                "retweet_count": tweet.retweet_count,
                "reply_count": tweet.reply_count
            }
            for tweet in tweets
        ]

    async def _send_dm(self, client: Client, recipient_username: str, text: str) -> Dict[str, Any]:
        """Send a direct message to a user"""
        # First get the user_id from the username
        user = await client.get_user_by_screen_name(recipient_username)
        user_id = user.id
        
        result = await client.send_dm(user_id, text)
        return {
            "success": True,
            "recipient_username": recipient_username,
            "recipient_user_id": user_id,
            "text": text,
            "message_id": result.id,
            "created_at": str(result.time)
        }

    async def _get_dm_history(self, client: Client, recipient_username: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get direct message history with a user"""
        # First get the user_id from the username
        user = await client.get_user_by_screen_name(recipient_username)
        user_id = user.id
        
        result = await client.get_dm_history(user_id)
        messages = []
        for i, message in enumerate(result):
            if i >= count:  # Limit to requested count
                break
            messages.append({
                "id": message.id,
                "text": message.text,
                "time": str(message.time),
                "sender_id": getattr(message, 'sender_id', None),
                "recipient_id": getattr(message, 'recipient_id', None),
                "attachment": getattr(message, 'attachment', None)
            })
        return messages

    async def _add_reaction_to_message(self, client: Client, message_id: str, emoji: str, conversation_id: str) -> Dict[str, Any]:
        """Add a reaction (emoji) to a direct message"""
        result = await client.add_reaction_to_message(message_id, conversation_id, emoji)
        return {
            "success": True,
            "message_id": message_id,
            "emoji": emoji,
            "conversation_id": conversation_id
        }

    async def _delete_dm(self, client: Client, message_id: str) -> Dict[str, Any]:
        """Delete a direct message"""
        result = await client.delete_dm(message_id)
        return {
            "success": True,
            "message_id": message_id
        }

    async def run(self):
        """Run the MCP server"""
        # Import here to avoid issues with event loop
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="twitter-mcp",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )

async def main():
    """Main entry point"""
    server = TwitterMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())