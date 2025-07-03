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
<<<<<<< HEAD
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
=======
                    name="block_user",
                    description="Block a user by user_id",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "User ID to block"},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["user_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="unblock_user",
                    description="Unblock a user by user_id",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "User ID to unblock"},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["user_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="create_poll",
                    description="Create a poll card.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "choices": {"type": "array", "items": {"type": "string"}, "description": "Poll answers (2-4)"},
                            "duration_minutes": {"type": "integer", "description": "Poll duration (5-10080 min)"},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["choices", "duration_minutes", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="vote",
                    description="Vote on an existing poll.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "poll_id": {"type": "string", "description": "Poll/card URI."},
                            "choice_index": {"type": "integer", "description": "Index of selected choice (0-3)."},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["poll_id", "choice_index", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="delete_retweet",
                    description="Undo a retweet.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tweet_id": {"type": "string", "description": "Original tweet ID."},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["tweet_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="upload_media",
                    description="Upload photo/video/GIF.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "media_path": {"type": "string", "description": "File path or binary payload."},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["media_path", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="login",
                    description="Log in to a Twitter account.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "auth_info_1": {"type": "string", "description": "First identifier (username/email/phone)."},
                            "password": {"type": "string", "description": "Account password."},
                            "auth_info_2": {"type": "string", "description": "Second identifier (email/phone)."},
                            "totp_secret": {"type": "string", "description": "TOTP secret for 2-FA."},
                            "cookies_file": {"type": "string", "description": "Path to persist cookies JSON."},
                            "enable_ui_metrics": {"type": "boolean", "description": "Send UI-metrics payload."}
                        },
                        "required": ["auth_info_1", "password"]
                    }
                ),
                Tool(
                    name="logout",
                    description="Log out of the authenticated account.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="unlock",
                    description="Unlock a locked account via CAPTCHA solver.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="get_cookies",
                    description="Return current session cookies.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="save_cookies",
                    description="Save cookies to a JSON file.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Destination file-path."},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["path", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="set_cookies",
                    description="Inject cookies dict to skip login.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "cookies": {"type": "object", "description": "Cookie key/value pairs."},
                            "clear_cookies": {"type": "boolean", "description": "Clear existing cookies first."},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["cookies", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="load_cookies",
                    description="Load cookies from a JSON file.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Source file-path."},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["path", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="set_delegate_account",
                    description="Act on behalf of another account.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "Target user-ID (None to clear)."},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["user_id", "ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="user_id",
                    description="Get the authenticated user's ID.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="user",
                    description="Get detailed profile of the authenticated user.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["ct0", "auth_token"]
                    }
                ),
                Tool(
                    name="search_user",
                    description="Search user profiles.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Username/name to search."},
                            "ct0": {"type": "string", "description": "Twitter ct0 cookie (required)"},
                            "auth_token": {"type": "string", "description": "Twitter auth_token cookie (required)"}
                        },
                        "required": ["query", "ct0", "auth_token"]
                    }
>>>>>>> see
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
                
<<<<<<< HEAD
                elif name == "unretweet":
                    result = await self._unretweet(client, arguments["tweet_id"])
                    return [types.TextContent(type="text", text=f"Unretweeted successfully: {json.dumps(result, indent=2)}")]
=======
                elif name == "block_user":
                    result = await self._block_user(client, arguments["user_id"])
                    return [types.TextContent(type="text", text=f"User blocked successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "unblock_user":
                    result = await self._unblock_user(client, arguments["user_id"])
                    return [types.TextContent(type="text", text=f"User unblocked successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "create_poll":
                    result = await self._create_poll(client, arguments["choices"], arguments["duration_minutes"])
                    return [types.TextContent(type="text", text=f"Poll created successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "vote":
                    result = await self._vote(client, arguments["poll_id"], arguments["choice_index"])
                    return [types.TextContent(type="text", text=f"Vote cast successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "delete_retweet":
                    result = await self._delete_retweet(client, arguments["tweet_id"])
                    return [types.TextContent(type="text", text=f"Retweet deleted successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "upload_media":
                    result = await self._upload_media(client, arguments["media_path"])
                    return [types.TextContent(type="text", text=f"Media uploaded successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "login":
                    result = await self._login(client, arguments["auth_info_1"], arguments["password"], arguments["auth_info_2"], arguments["totp_secret"], arguments["cookies_file"], arguments["enable_ui_metrics"])
                    return [types.TextContent(type="text", text=f"Login successful: {json.dumps(result, indent=2)}")]
                
                elif name == "logout":
                    result = await self._logout(client)
                    return [types.TextContent(type="text", text=f"Logout successful: {json.dumps(result, indent=2)}")]
                
                elif name == "unlock":
                    result = await self._unlock(client)
                    return [types.TextContent(type="text", text=f"Account unlocked: {json.dumps(result, indent=2)}")]
                
                elif name == "get_cookies":
                    result = await self._get_cookies(client)
                    return [types.TextContent(type="text", text=f"Current cookies: {json.dumps(result, indent=2)}")]
                
                elif name == "save_cookies":
                    result = await self._save_cookies(client, arguments["path"])
                    return [types.TextContent(type="text", text=f"Cookies saved successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "set_cookies":
                    result = await self._set_cookies(client, arguments["cookies"], arguments["clear_cookies"])
                    return [types.TextContent(type="text", text=f"Cookies set successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "load_cookies":
                    result = await self._load_cookies(client, arguments["path"])
                    return [types.TextContent(type="text", text=f"Cookies loaded successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "set_delegate_account":
                    result = await self._set_delegate_account(client, arguments["user_id"])
                    return [types.TextContent(type="text", text=f"Delegate account set successfully: {json.dumps(result, indent=2)}")]
                
                elif name == "user_id":
                    result = await self._user_id(client)
                    return [types.TextContent(type="text", text=f"Authenticated user ID: {json.dumps(result, indent=2)}")]
                
                elif name == "user":
                    result = await self._user(client)
                    return [types.TextContent(type="text", text=f"Authenticated user profile: {json.dumps(result, indent=2)}")]
                
                elif name == "search_user":
                    result = await self._search_user(client, arguments["query"])
                    return [types.TextContent(type="text", text=f"Search results: {json.dumps(result, indent=2)}")]
>>>>>>> see
                
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

<<<<<<< HEAD
    async def _unretweet(self, client: Client, tweet_id: str) -> Dict[str, Any]:
        """Undo a retweet by tweet ID"""
=======
    async def _block_user(self, client: Client, user_id: str) -> Dict[str, Any]:
        """Block a user by user_id"""
        result = await client.block_user(user_id)
        return {
            "success": True,
            "user_id": user_id
        }

    async def _unblock_user(self, client: Client, user_id: str) -> Dict[str, Any]:
        """Unblock a user by user_id"""
        result = await client.unblock_user(user_id)
        return {
            "success": True,
            "user_id": user_id
        }

    async def _create_poll(self, client: Client, choices: List[str], duration_minutes: int) -> Dict[str, Any]:
        """Create a poll card"""
        result = await client.create_poll(choices, duration_minutes)
        return {
            "poll_id": result.id,
            "url": result.url
        }

    async def _vote(self, client: Client, poll_id: str, choice_index: int) -> Dict[str, Any]:
        """Vote on an existing poll"""
        result = await client.vote(poll_id, choice_index)
        return {
            "success": True,
            "poll_id": result.id,
            "url": result.url
        }

    async def _delete_retweet(self, client: Client, tweet_id: str) -> Dict[str, Any]:
        """Undo a retweet"""
>>>>>>> see
        result = await client.delete_retweet(tweet_id)
        return {
            "success": True,
            "tweet_id": tweet_id
        }
<<<<<<< HEAD
        """Run the MCP server"""
        # Import here to avoid issues with event loop


    async def run(self):
        """Run the MCP server using stdio."""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
=======

    async def _upload_media(self, client: Client, media_path: str) -> Dict[str, Any]:
        """Upload photo/video/GIF"""
        result = await client.upload_media(media_path)
        return {
            "success": True,
            "media_id": result.id,
            "url": result.url
        }

    async def _login(self, client: Client, auth_info_1: str, password: str, auth_info_2: str, totp_secret: str, cookies_file: str, enable_ui_metrics: bool) -> Dict[str, Any]:
        """Log in to a Twitter account"""
        result = await client.login(auth_info_1, password, auth_info_2, totp_secret, cookies_file, enable_ui_metrics)
        return {
            "success": True,
            "cookies_file": cookies_file
        }

    async def _logout(self, client: Client) -> Dict[str, Any]:
        """Log out of the authenticated account"""
        result = await client.logout()
        return {
            "success": True
        }

    async def _unlock(self, client: Client) -> Dict[str, Any]:
        """Unlock a locked account via CAPTCHA solver"""
        result = await client.unlock()
        return {
            "success": True
        }

    async def _get_cookies(self, client: Client) -> Dict[str, Any]:
        """Return current session cookies"""
        result = await client.get_cookies()
        return result

    async def _save_cookies(self, client: Client, path: str) -> Dict[str, Any]:
        """Save cookies to a JSON file"""
        result = await client.save_cookies(path)
        return {
            "success": True,
            "path": path
        }

    async def _set_cookies(self, client: Client, cookies: Dict[str, str], clear_cookies: bool) -> Dict[str, Any]:
        """Inject cookies dict to skip login"""
        result = await client.set_cookies(cookies, clear_cookies)
        return {
            "success": True
        }

    async def _load_cookies(self, client: Client, path: str) -> Dict[str, Any]:
        """Load cookies from a JSON file"""
        result = await client.load_cookies(path)
        return {
            "success": True,
            "path": path
        }

    async def _set_delegate_account(self, client: Client, user_id: str) -> Dict[str, Any]:
        """Act on behalf of another account"""
        result = await client.set_delegate_account(user_id)
        return {
            "success": True,
            "user_id": user_id
        }

    async def _user_id(self, client: Client) -> Dict[str, Any]:
        """Get the authenticated user's ID"""
        result = await client.user_id()
        return {
            "user_id": result
        }

    async def _user(self, client: Client) -> Dict[str, Any]:
        """Get detailed profile of the authenticated user"""
        result = await client.user()
        return {
            "user": {
                "id": result.id,
                "username": result.screen_name,
                "name": result.name,
                "followers_count": result.followers_count,
                "following_count": result.following_count,
                "tweet_count": result.statuses_count,
                "verified": result.verified
            }
        }

    async def _search_user(self, client: Client, query: str) -> List[Dict[str, Any]]:
        """Search user profiles"""
        result = await client.search_user(query)
        return [
            {
                "id": user.id,
                "username": user.screen_name,
                "name": user.name,
                "description": user.description,
                "followers_count": user.followers_count,
                "following_count": user.following_count,
                "tweet_count": user.statuses_count,
                "verified": user.verified
            }
            for user in result
        ]

    async def run(self):
        """Run the MCP server as a TCP server on localhost:8765 instead of stdio."""
        import asyncio
        from mcp.server.tcp import tcp_server

        async with tcp_server(host="0.0.0.0", port=8765) as (read_stream, write_stream):
>>>>>>> see
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