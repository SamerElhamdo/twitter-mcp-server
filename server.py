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
from mcp.server.stdio import stdio_server

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
                ),
                Tool(
                    name="get_tweet_replies",
                    description="Get replies to a specific tweet",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tweet_id": {
                                "type": "string",
                                "description": "The ID of the tweet to get replies for"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of replies to retrieve (default: 20)",
                                "default": 20
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
                    name="get_trends",
                    description="Get trending topics on Twitter",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "The category of trends to retrieve",
                                "enum": ["trending", "for-you", "news", "sports", "entertainment"],
                                "default": "trending"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of trends to retrieve (default: 20)",
                                "default": 20,
                                "minimum": 1,
                                "maximum": 50
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
                    name="delete_tweet",
                    description="Delete a tweet by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tweet_id": {
                                "type": "string",
                                "description": "The ID of the tweet to delete"
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
                    name="follow_user",
                    description="Follow a user by username",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "username": {
                                "type": "string",
                                "description": "The username (without @) to follow"
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
                    name="unfollow_user",
                    description="Unfollow a user by username",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "username": {
                                "type": "string",
                                "description": "The username (without @) to unfollow"
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
                    name="unretweet",
                    description="Undo a retweet by tweet ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tweet_id": {
                                "type": "string",
                                "description": "The ID of the tweet to unretweet"
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
                    name="join_community",
                    description="Join a Twitter community by its ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "community_id": {
                                "type": "string",
                                "description": "The ID of the community to join"
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
                        "required": ["community_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_community_members",
                    description="Retrieve members of a Twitter community by its ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "community_id": {
                                "type": "string",
                                "description": "The ID of the community"
                            },
                            "count": {
                                "type": "integer",
                                "description": "The number of members to retrieve (default: 20)",
                                "default": 20
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
                        "required": ["community_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="leave_community",
                    description="Leave a Twitter community by its ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "community_id": {
                                "type": "string",
                                "description": "The ID of the community to leave"
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
                        "required": ["community_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_community_tweets",
                    description="Retrieve tweets from a Twitter community by its ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "community_id": {
                                "type": "string",
                                "description": "The ID of the community"
                            },
                            "tweet_type": {
                                "type": "string",
                                "description": "The type of tweets to retrieve ('Top', 'Latest', 'Media')",
                                "enum": ["Top", "Latest", "Media"],
                                "default": "Latest"
                            },
                            "count": {
                                "type": "integer",
                                "description": "The number of tweets to retrieve (default: 40)",
                                "default": 40
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
                        "required": ["community_id", "tweet_type", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_notifications",
                    description="Retrieve notifications by type (All, Verified, Mentions)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": "Type of notifications to retrieve ('All', 'Verified', 'Mentions')",
                                "enum": ["All", "Verified", "Mentions"],
                                "default": "All"
                            },
                            "count": {
                                "type": "integer",
                                "description": "Number of notifications to retrieve (default: 40)",
                                "default": 40
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
                        "required": ["type", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_dm_history_by_id",
                    description="Retrieve DM conversation history with a specific user by user_id (with optional max_id)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "The ID of the user with whom the DM conversation history will be retrieved"
                            },
                            "max_id": {
                                "type": "string",
                                "description": "If specified, retrieves messages older than the specified max_id",
                                "default": None
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
                        "required": ["user_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_friends_ids",
                    description="Fetch the IDs of the friends (following users) of a specified user (by user_id or screen_name)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "The ID of the user for whom to return results",
                                "default": None
                            },
                            "screen_name": {
                                "type": "string",
                                "description": "The screen name of the user for whom to return results",
                                "default": None
                            },
                            "count": {
                                "type": "integer",
                                "description": "The maximum number of IDs to retrieve (default: 5000)",
                                "default": 5000
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
                    name="get_user_followers",
                    description="Retrieve a list of followers for a given user by user_id",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "The ID of the user for whom to retrieve followers"
                            },
                            "count": {
                                "type": "integer",
                                "description": "The number of followers to retrieve (default: 20)",
                                "default": 20
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
                        "required": ["user_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="unlock",
                    description="Unlock the account using the provided CAPTCHA solver.",
                    inputSchema={
                        "type": "object",
                        "properties": {
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
                    name="get_cookies",
                    description="Get the current session cookies.",
                    inputSchema={
                        "type": "object",
                        "properties": {
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
                    name="set_cookies",
                    description="Set cookies for the client session. You can skip the login procedure by loading saved cookies.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cookies": {
                                "type": "object",
                                "description": "The cookies to be set as key value pair."
                            },
                            "clear_cookies": {
                                "type": "boolean",
                                "description": "Clear existing cookies first.",
                                "default": False
                            }
                        },
                        "required": ["cookies"]
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
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "delete_dm":
                    result = await self._delete_dm(client, arguments["message_id"])
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_tweet_replies":
                    count = arguments.get("count", 20)
                    result = await self._get_tweet_replies(client, arguments["tweet_id"], count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_trends":
                    category = arguments.get("category", "trending")
                    count = arguments.get("count", 20)
                    result = await self._get_trends(client, category, count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "delete_tweet":
                    result = await self._delete_tweet(client, arguments["tweet_id"])
                    return [types.TextContent(type="text", text=f"Tweet deleted successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "follow_user":
                    result = await self._follow_user(client, arguments["username"])
                    return [types.TextContent(type="text", text=f"Followed user successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "unfollow_user":
                    result = await self._unfollow_user(client, arguments["username"])
                    return [types.TextContent(type="text", text=f"Unfollowed user successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "unretweet":
                    result = await self._unretweet(client, arguments["tweet_id"])
                    return [types.TextContent(type="text", text=f"Unretweeted successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "join_community":
                    result = await self._join_community(client, arguments["community_id"])
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_community_members":
                    count = arguments.get("count", 20)
                    result = await self._get_community_members(client, arguments["community_id"], count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "leave_community":
                    result = await self._leave_community(client, arguments["community_id"])
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_community_tweets":
                    tweet_type = arguments.get("tweet_type", "Latest")
                    count = arguments.get("count", 40)
                    result = await self._get_community_tweets(client, arguments["community_id"], tweet_type, count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_notifications":
                    notif_type = arguments.get("type", "All")
                    count = arguments.get("count", 40)
                    result = await self._get_notifications(client, notif_type, count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_dm_history_by_id":
                    max_id = arguments.get("max_id")
                    result = await self._get_dm_history_by_id(client, arguments["user_id"], max_id)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_friends_ids":
                    user_id = arguments.get("user_id")
                    screen_name = arguments.get("screen_name")
                    count = arguments.get("count", 5000)
                    result = await self._get_friends_ids(client, user_id, screen_name, count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_user_followers":
                    count = arguments.get("count", 20)
                    result = await self._get_user_followers(client, arguments["user_id"], count)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "unlock":
                    result = await self._unlock(client)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "get_cookies":
                    result = await self._get_cookies(client)
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
                elif name == "set_cookies":
                    result = await self._set_cookies(arguments["cookies"], arguments.get("clear_cookies", False))
                    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
                
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
        # user = await client.user()
        return {
            "authenticated": True,
            "user": {
                "id": user_id,
                # "username": user.screen_name,
                # "name": user.name,
                # "followers_count": user.followers_count,
                # "following_count": user.following_count,
                # "tweet_count": user.statuses_count,
                # "verified": user.verified
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

    async def _add_reaction_to_message(self, client: Client, message_id: str, emoji: str, conversation_id: str) -> dict:
        """Add a reaction (emoji) to a direct message using asyncadd_reaction_to_message"""
        response = await client.add_reaction_to_message(message_id, conversation_id, emoji)
        # Try to parse response if possible
        try:
            data = response.json() if hasattr(response, 'json') else str(response)
        except Exception:
            data = str(response)
        return {
            "success": True,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "emoji": emoji,
            "response": data
        }

    async def _delete_dm(self, client: Client, message_id: str) -> dict:
        """Delete a direct message by its ID using asyncdelete_dm"""
        response = await client.delete_dm(message_id)
        # Try to parse response if possible
        try:
            data = response.json() if hasattr(response, 'json') else str(response)
        except Exception:
            data = str(response)
        return {
            "success": True,
            "message_id": message_id,
            "response": data
        }

    async def _get_tweet_replies(self, client: Client, tweet_id: str, count: int = 20) -> List[Dict[str, Any]]:
        """Get replies to a specific tweet"""
        try:
            # Get the tweet by ID, which should include replies
            tweet = await client.get_tweet_by_id(tweet_id)
            
            if not tweet:
                return {"error": "Tweet not found"}
            
            replies_data = []
            
            # Check if tweet has replies attribute and it's not None
            if hasattr(tweet, 'replies') and tweet.replies is not None:
                # The replies attribute should be a Result object that we can iterate over
                reply_count = 0
                for reply in tweet.replies:
                    if reply_count >= count:
                        break
                    
                    replies_data.append({
                        "id": reply.id,
                        "text": reply.text,
                        "author_id": reply.user.id,
                        "author_username": reply.user.screen_name,
                        "author_name": reply.user.name,
                        "created_at": reply.created_at,
                        "reply_count": reply.reply_count,
                        "retweet_count": reply.retweet_count,
                        "favorite_count": reply.favorite_count,
                        "in_reply_to": reply.in_reply_to
                    })
                    reply_count += 1
            
            return {
                "original_tweet": {
                    "id": tweet.id,
                    "text": tweet.text,
                    "author": tweet.user.screen_name,
                    "reply_count": tweet.reply_count
                },
                "replies": replies_data,
                "total_replies_retrieved": len(replies_data)
            }
            
        except Exception as e:
            return {"error": f"Failed to get tweet replies: {str(e)}"}

    async def _get_trends(self, client: Client, category: str, count: int) -> List[Dict[str, Any]]:
        """Get trending topics on Twitter"""
        trends = await client.get_trends(category, count)
        return [
            {
                "name": trend.name,
                "tweets_count": trend.tweets_count,
                "domain_context": trend.domain_context,
                "grouped_trends": trend.grouped_trends
            }
            for trend in trends
        ]

    async def _delete_tweet(self, client: Client, tweet_id: str) -> Dict[str, Any]:
        """Delete a tweet by ID"""
        result = await client.delete_tweet(tweet_id)
        return {
            "success": True,
            "tweet_id": tweet_id
        }

    async def _follow_user(self, client: Client, username: str) -> Dict[str, Any]:
        """Follow a user by username"""
        user = await client.get_user_by_screen_name(username)
        result = await client.follow_user(user.id)
        return {
            "success": True,
            "username": username,
            "user_id": user.id
        }

    async def _unfollow_user(self, client: Client, username: str) -> Dict[str, Any]:
        """Unfollow a user by username"""
        user = await client.get_user_by_screen_name(username)
        result = await client.unfollow_user(user.id)
        return {
            "success": True,
            "username": username,
            "user_id": user.id
        }

    async def _unretweet(self, client: Client, tweet_id: str) -> Dict[str, Any]:
        """Undo a retweet by tweet ID"""
        result = await client.delete_retweet(tweet_id)
        return {
            "success": True,
            "tweet_id": tweet_id
        }

    async def _join_community(self, client: Client, community_id: str) -> dict:
        """Join a community by its ID"""
        community = await client.join_community(community_id)
        return {
            "id": getattr(community, "id", None),
            "name": getattr(community, "name", None)
        }

    async def _get_community_members(self, client: Client, community_id: str, count: int = 20) -> list:
        """Retrieve members of a community by its ID"""
        members_result = await client.get_community_members(community_id, count=count)
        members = []
        for member in members_result:
            members.append({
                "id": getattr(member, "id", None),
                "username": getattr(member, "screen_name", None),
                "name": getattr(member, "name", None),
                "description": getattr(member, "description", None),
                "joined_at": str(getattr(member, "joined_at", ""))
            })
        return members

    async def _leave_community(self, client: Client, community_id: str) -> dict:
        """Leave a community by its ID"""
        community = await client.leave_community(community_id)
        return {
            "id": getattr(community, "id", None),
            "name": getattr(community, "name", None)
        }

    async def _get_community_tweets(self, client: Client, community_id: str, tweet_type: str = "Latest", count: int = 40) -> list:
        """Retrieve tweets from a community by its ID"""
        tweets_result = await client.get_community_tweets(community_id, tweet_type=tweet_type, count=count)
        tweets = []
        for tweet in tweets_result:
            tweets.append({
                "id": getattr(tweet, "id", None),
                "text": getattr(tweet, "text", None),
                "author": getattr(tweet.user, "screen_name", None) if hasattr(tweet, "user") else None,
                "author_name": getattr(tweet.user, "name", None) if hasattr(tweet, "user") else None,
                "created_at": str(getattr(tweet, "created_at", "")),
                "like_count": getattr(tweet, "favorite_count", None),
                "retweet_count": getattr(tweet, "retweet_count", None),
                "reply_count": getattr(tweet, "reply_count", None)
            })
        return tweets

    async def _get_notifications(self, client: Client, notif_type: str = "All", count: int = 40) -> list:
        """Retrieve notifications by type"""
        notifications_result = await client.get_notifications(notif_type, count=count)
        notifications = []
        for notif in notifications_result:
            notifications.append({
                "id": getattr(notif, "id", None),
                "type": getattr(notif, "type", None),
                "text": getattr(notif, "text", None),
                "created_at": str(getattr(notif, "created_at", "")),
                "user": getattr(notif, "user", None)
            })
        return notifications

    async def _get_dm_history_by_id(self, client: Client, user_id: str, max_id: str = None) -> list:
        """Retrieve DM conversation history with a specific user by user_id (with optional max_id)"""
        result = await client.get_dm_history(user_id, max_id=max_id)
        messages = []
        for message in result:
            messages.append({
                "id": getattr(message, "id", None),
                "text": getattr(message, "text", None),
                "time": str(getattr(message, "time", "")),
                "sender_id": getattr(message, "sender_id", None),
                "recipient_id": getattr(message, "recipient_id", None),
                "attachment": getattr(message, "attachment", None)
            })
        return messages

    async def _get_friends_ids(self, client: Client, user_id: str = None, screen_name: str = None, count: int = 5000) -> list:
        """Fetch the IDs of the friends (following users) of a specified user (by user_id or screen_name)"""
        result = await client.get_friends_ids(user_id=user_id, screen_name=screen_name, count=count)
        ids = list(result) if result else []
        return ids

    async def _get_user_followers(self, client: Client, user_id: str, count: int = 20) -> list:
        """Retrieve a list of followers for a given user by user_id"""
        result = await client.get_user_followers(user_id, count=count)
        followers = []
        for user in result:
            followers.append({
                "id": getattr(user, "id", None),
                "username": getattr(user, "screen_name", None),
                "name": getattr(user, "name", None),
                "description": getattr(user, "description", None),
                "followers_count": getattr(user, "followers_count", None),
                "following_count": getattr(user, "following_count", None),
                "tweet_count": getattr(user, "statuses_count", None),
                "verified": getattr(user, "verified", None),
                "created_at": str(getattr(user, "created_at", ""))
            })
        return followers

    async def _unlock(self, client: Client) -> dict:
        """Unlock the account using the provided CAPTCHA solver."""
        result = await client.unlock()
        return {"success": True, "result": str(result)}

    async def _get_cookies(self, client: Client) -> dict:
        """Get the current session cookies."""
        cookies = client.get_cookies() if hasattr(client, 'get_cookies') else {}
        return cookies

    async def _set_cookies(self, cookies: dict, clear_cookies: bool = False) -> dict:
        """Set cookies for the client session."""
        client = Client('en-US')
        client.set_cookies(cookies, clear_cookies=clear_cookies)
        return {"success": True, "cookies_set": list(cookies.keys()), "clear_cookies": clear_cookies}

    async def run(self):
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

def main():
    server = TwitterMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()