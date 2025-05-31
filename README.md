# Twitter MCP Server

A Model Context Protocol (MCP) server that provides Twitter functionality using the `twikit` library. This server allows AI assistants to interact with Twitter through a standardized protocol with **cookie-based authentication** - the LLM model provides `ct0` and `auth_token` cookies directly in tool calls.

## Features

- **Cookie Authentication**: LLM model provides `ct0` and `auth_token` cookies directly in tool calls
- **Session Caching**: Automatically caches authenticated sessions for efficiency  
- **Timeline Access**: Get tweets from your timeline
- **User Information**: Retrieve user profiles and statistics
- **Tweet Search**: Search for tweets with specific queries
- **Tweet Management**: Post, like, and retweet tweets
- **User Tweets**: Get tweets from specific users
- **Authentication Testing**: Test cookies before use

## Disclaimer

**This project utilizes an unofficial API to interact with X (formerly Twitter) through the `twikit` library. The methods employed for authentication and data retrieval are not officially endorsed by X/Twitter and may be subject to change or discontinuation without notice.**

**This tool is intended for educational and experimental purposes only. Users should be aware of the potential risks associated with using unofficial APIs, including but not limited to account restrictions or suspension. The developers of this project are not responsible for any misuse or consequences arising from the use of this tool.**

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd twitter-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
python server.py
```

## Authentication

The server expects the LLM model to provide Twitter cookies directly in each tool call via the `ct0` and `auth_token` parameters. No pre-configuration is required!

### Getting Twitter Cookies

The LLM model will need to provide both Twitter cookies. Here's how to obtain them:

1. Open your browser and go to Twitter/X
2. Log in to your account
3. Open Developer Tools (F12)
4. Go to Application/Storage → Cookies → twitter.com (or x.com)
5. Find and copy these cookie values:
   - `ct0` - CSRF token cookie
   - `auth_token` - Authentication token cookie

Both cookies are required for all operations.

## Usage

### Available Tools

#### 1. Authenticate
Test authentication with cookies:
```json
{
  "tool": "authenticate",
  "arguments": {
    "ct0": "your_ct0_cookie_here",
    "auth_token": "your_auth_token_cookie_here"
  }
}
```

#### 2. Tweet
Post a new tweet:
```json
{
  "tool": "tweet",
  "arguments": {
    "text": "Hello from MCP! 🚀",
    "ct0": "your_ct0_cookie_here",
    "auth_token": "your_auth_token_cookie_here"
  }
}
```

#### 3. Get User Info
Get information about a Twitter user:
```json
{
  "tool": "get_user_info",
  "arguments": {
    "username": "elonmusk",
    "ct0": "your_ct0_cookie_here",
    "auth_token": "your_auth_token_cookie_here"
  }
}
```

#### 4. Search Tweets
Search for tweets:
```json
{
  "tool": "search_tweets",
  "arguments": {
    "query": "artificial intelligence",
    "count": 10,
    "ct0": "your_ct0_cookie_here",
    "auth_token": "your_auth_token_cookie_here"
  }
}
```

#### 5. Get Timeline
Get tweets from your timeline:
```json
{
  "tool": "get_timeline",
  "arguments": {
    "count": 20,
    "ct0": "your_ct0_cookie_here",
    "auth_token": "your_auth_token_cookie_here"
  }
}
```

#### 6. Like Tweet
Like a tweet by ID:
```json
{
  "tool": "like_tweet",
  "arguments": {
    "tweet_id": "1234567890123456789",
    "ct0": "your_ct0_cookie_here",
    "auth_token": "your_auth_token_cookie_here"
  }
}
```

#### 7. Retweet
Retweet a tweet by ID:
```json
{
  "tool": "retweet",
  "arguments": {
    "tweet_id": "1234567890123456789",
    "ct0": "your_ct0_cookie_here",
    "auth_token": "your_auth_token_cookie_here"
  }
}
```

### Available Resources

Resources can be accessed but require the `TWITTER_CT0` and `TWITTER_AUTH_TOKEN` environment variables as a fallback:

#### 1. Timeline
```
twitter://timeline
```

#### 2. User Tweets
```
twitter://user-tweets#username
```

#### 3. Search
```
twitter://search#query
```

## Configuration

### Environment Variables (Optional)

- `TWITTER_CT0`: Default Twitter ct0 cookie (optional, used for resources only)
- `TWITTER_AUTH_TOKEN`: Default Twitter auth_token cookie (optional, used for resources only)

### Session Management

The server automatically caches authenticated sessions per `ct0` cookie to avoid repeated authentication and improve performance.

## Security Features

- **Cookie Caching**: Sessions are cached using ct0 as the key
- **Session Isolation**: Each set of cookies gets its own session cache
- **Direct Cookie Usage**: Cookies are used directly without modification
- **Automatic Validation**: Cookies are tested on first use

## Error Handling

The server includes comprehensive error handling for:
- Authentication failures
- Invalid cookies
- Rate limiting
- Network errors
- Invalid requests

## Rate Limiting

Twitter has rate limits for API requests. The server will handle rate limiting gracefully, but be mindful of:
- Search: 300 requests per 15 minutes
- Timeline: 300 requests per 15 minutes
- User lookup: 300 requests per 15 minutes
- Tweet posting: 300 tweets per 3 hours

## Security Notes

1. **Cookie Security**: Cookies are cached temporarily for performance but not persisted to disk
2. **Session Caching**: Sessions are cached with ct0 as the key
3. **Automatic Testing**: Cookies are validated on first use
4. **Per-session Isolation**: Each ct0 maintains its own session

## Troubleshooting

### Authentication Issues
- Use the `authenticate` tool to test cookies before other operations
- Ensure both `ct0` and `auth_token` cookies are valid and not expired
- Check that the cookies are from the correct Twitter/X domain
- Make sure you're logged into Twitter in the browser where you copied the cookies

### Rate Limiting
- Reduce the frequency of requests
- The server respects Twitter's rate limits automatically
- Monitor usage across different cookie sets

### Network Issues
- Check your internet connection
- Verify Twitter's service status
- Ensure no firewall is blocking the requests

## Dependencies

- `mcp`: Model Context Protocol implementation
- `twikit`: Twitter API client library  
- `pydantic`: Data validation library
- `python-dotenv`: Environment variable management
- `asyncio`: Asynchronous programming support

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Search existing issues
3. Create a new issue with detailed information 