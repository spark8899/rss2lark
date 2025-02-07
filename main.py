import os
import logging
from logging.handlers import RotatingFileHandler
import feedparser
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Configure logging with rotation
log_file = os.getenv("LOG_FILE")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            log_file, maxBytes=1 * 1024 * 1024, backupCount=5  # 1MB size, keep 5 logs
        ),
        logging.StreamHandler(),  # Log to console
    ],
)
logger = logging.getLogger(__name__)

# File to track sent releases
SENT_RELEASES_FILE = os.getenv("SENT_RELEASES_FILE", "sent_releases.txt")

def load_sent_releases():
    """Load the list of sent releases from the file."""
    if not os.path.exists(SENT_RELEASES_FILE):
        return set()
    with open(SENT_RELEASES_FILE, "r") as file:
        return set(file.read().splitlines())

def save_sent_release(release_id):
    """Save a release ID to the file."""
    with open(SENT_RELEASES_FILE, "a") as file:
        file.write(release_id + "\n")

def send_to_lark(project_name, title, link, updated):
    """Send a formatted Markdown message to Lark group via Webhook."""
    lark_webhook_url = os.getenv("LARK_WEBHOOK_URL")
    if not lark_webhook_url:
        logger.error("LARK_WEBHOOK_URL is not configured. Please set it in the .env file.")
        return

    # Format the message using Markdown
    message = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "content": f"**Project:** {project_name}\n\n"
                                  f"**New Release:** {title}\n\n"
                                  f"**Updated:** {updated}\n\n"
                                  f"[View Release]({link})",
                        "tag": "lark_md"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "content": "Open Release",
                                "tag": "plain_text"
                            },
                            "type": "primary",
                            "url": link
                        }
                    ]
                }
            ]
        }
    }

    try:
        response = requests.post(lark_webhook_url, json=message, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            logger.info(f"Message sent to Lark group for project: {project_name}.")
        else:
            logger.error(f"Failed to send message to Lark: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error sending message to Lark: {e}")

def check_releases():
    projects = os.getenv("PROJECTS")
    if not projects:
        logger.error("PROJECTS is not configured. Please set it in the .env file.")
        return

    sent_releases = load_sent_releases()

    for project in projects.split(","):
        project_name, rss_url = project.split(":", 1)
        project_name = project_name.strip()
        rss_url = rss_url.strip()

        if not project_name or not rss_url:
            logger.warning(f"Invalid project configuration: {project}")
            continue

        try:
            # Parse the RSS feed
            feed = feedparser.parse(rss_url)
            if feed.bozo:  # Check for RSS parsing errors
                logger.error(f"RSS parsing failed for project {project_name}: {feed.bozo_exception}")
                continue

            # Iterate through all entries
            new_releases = []
            for entry in feed.entries:
                release_id = entry.id  # Use the entry ID as a unique identifier
                if release_id not in sent_releases:
                    new_releases.append(entry)
                    sent_releases.add(release_id)
                    save_sent_release(release_id)

            # Send only the latest release for this project
            if new_releases:
                # Filter out entries without a valid updated_parsed field
                valid_releases = [entry for entry in new_releases if hasattr(entry, 'updated_parsed')]
                if valid_releases:
                    latest_release = max(valid_releases, key=lambda x: x.updated_parsed)
                    logger.info(f"Latest release found for project {project_name}: {latest_release.title}")
                    send_to_lark(project_name, latest_release.title, latest_release.link, latest_release.updated)
                else:
                    logger.warning(f"No valid releases found for project {project_name} with an updated_parsed field.")
            else:
                logger.info(f"No new releases found for project {project_name}.")

        except Exception as e:
            logger.error(f"Error checking releases for project {project_name}: {e}")

if __name__ == "__main__":
    logger.info("Starting GitHub Release monitoring...")
    check_releases()
    logger.info("Monitoring completed.")
