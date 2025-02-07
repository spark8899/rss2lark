# rss2lark
Monitor GitHub release information and send it to Lark.

# Install Dependencies
```
python3 -m venv venv
source venv/bin/activate
pip install feedparser requests python-dotenv
```

# Copy the template and modify the configuration
```
cp env_template .env
vim .env
```

# add crontab
```
10 * * * * /<path>/rss2lark/main.py >/dev/null 2>&1
````
