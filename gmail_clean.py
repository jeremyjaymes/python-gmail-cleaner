"""
Gmail Cleaner - Learning Edition (with argparse)

Usage examples:
  python gmail_cleaner.py --query "category:promotions older_than:6m"
  python gmail_cleaner.py --query "category:social" --action archive --dry-run
  python gmail_cleaner.py --query "category:updates older_than:1y" --action trash --live
  python gmail_cleaner.py --query "from:newsletter@example.com" --max 30

Learning focus:
- argparse (command-line interfaces)
- Clean function design
- Safety patterns (dry-run by default)
- Working with external APIs
"""

import argparse
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If you change scopes, delete token.json
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError(
                    "credentials.json not found. Download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def search_messages(service, query: str, max_results: int = 50) -> list[dict]:
    """Search messages using a Gmail query. Raises HttpError on failure."""
    results = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return results.get("messages", [])


def get_message_preview(service, msg_id: str) -> str:
    """Return a short readable preview of a message. Raises HttpError on failure."""
    msg = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=msg_id,
            format="metadata",
            metadataHeaders=["From", "Subject"],
        )
        .execute()
    )

    headers = msg.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
    sender = next((h["value"] for h in headers if h["name"] == "From"), "(Unknown)")

    return f"From: {sender}\nSubject: {subject}"


def modify_messages(service, message_ids: list[str], action: str, dry_run: bool = True, label_name: str = None) -> None:
    """
    Perform an action on messages.
    
    Supported actions:
    - archive  → remove INBOX label
    - trash    → move to Trash
    """
    if not message_ids:
        print("No messages to process.")
        return

    action = action.lower()
    count = len(message_ids)

    if dry_run:
        if action == "label":
            print(f"\n[DRY RUN] Would apply label '{label_name}' to {count} messages.")
        else:
            print(f"\n[DRY RUN] Would {action} {count} messages.")
        return

    try:
        if action == "archive":
            service.users().messages().batchModify(
                userId="me",
                body={"ids": message_ids, "removeLabelIds": ["INBOX"]},
            ).execute()
            print(f"Archived {count} messages.")

        elif action == "trash":
            service.users().messages().batchModify(
                userId="me",
                body={"ids": message_ids, "addLabelIds": ["TRASH"]},
            ).execute()
            print(f"Moved {count} messages to Trash.")

        elif action == "label":
            if not label_name:
                print("Error: --label is required when using --action label")
                return

            label_id = get_or_create_label(service, label_name)
            service.users().messages().batchModify(
                userId="me",
                body={"ids": message_ids, "addLabelIds": [label_id]},
            ).execute()
            print(f"Applied Label '{label_name}' to {count} messages.")

        else:
            print(f"Unknown action: {action}")

    except HttpError as error:
        print(f"Error while performing '{action}': {error}")

def get_or_create_label(service, label_name: str) -> str:
    """
    Get the ID of a label. Create it if it doesn't exist.
    Returns the label ID.
    """

    # Get existing labels
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])

    for label in labels:
            if label["name"].lower() == label_name.lower():
                return label["id"]

    # Label doesn't exist -> create it
    new_label = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show"
    }
    created = service.users().labels().create(userId="me", body=new_label).execute()
    print(f"Created new label: {label_name}")
    return created["id"]

def max_results_arg(value: str) -> int:
    """argparse type: an int between 1 and 500 (Gmail's messages.list limit)."""
    number = int(value)
    if not 1 <= number <= 500:
        raise argparse.ArgumentTypeError("must be between 1 and 500")
    return number


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Gmail Cleaner - Learn Python while decluttering your inbox"
    )

    parser.add_argument(
        "--query",
        required=True,
        help='Gmail search query (e.g. "category:promotions older_than:6m")',
    )
    parser.add_argument(
        "--action",
        choices=["preview", "archive", "trash", "label"],
        default="preview",
        help="What to do with matching messages (default: preview)",
    )
    parser.add_argument(
        "--max",
        type=max_results_arg,
        default=25,
        help="Maximum number of messages to process, 1-500 (default: 25)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually perform the action (default is dry-run)",
    )

    parser.add_argument(
        "--label",
        help="Name of the label to apply (required when --action label)"
    )

    args = parser.parse_args()
    if args.action == "label" and not args.label:
        parser.error("--label is required when using --action label")
    return args


def main():
    args = parse_args()

    print("Gmail Cleaner - Learning Edition\n")
    print(f"Query   : {args.query}")
    print(f"Action  : {args.action}")
    print(f"Max     : {args.max}")
    print(f"Mode    : {'LIVE' if args.live else 'DRY-RUN'}\n")

    service = get_gmail_service()
    print("✓ Authenticated\n")

    try:
        messages = search_messages(service, args.query, max_results=args.max)
    except HttpError as error:
        raise SystemExit(f"Search failed: {error}")

    if not messages:
        print("No messages found.")
        return

    print(f"Found {len(messages)} messages:\n")
    print("-" * 70)

    message_ids = []
    failed_ids = []
    for i, msg in enumerate(messages, 1):
        try:
            preview = get_message_preview(service, msg["id"])
        except HttpError as error:
            print(f"{i}. [Error reading message {msg['id']}: {error}]\n")
            failed_ids.append(msg["id"])
            continue
        print(f"{i}. {preview}\n")
        message_ids.append(msg["id"])

    print("-" * 70)

    if failed_ids:
        print(f"\n{len(failed_ids)} message(s) could not be previewed.")
        if args.live:
            raise SystemExit("Aborting live action. Re-run once every message previews cleanly.")

    if args.action == "preview":
        print("\nPreview only — no changes made.")
    else:
        modify_messages(
            service,
            message_ids,
            action=args.action,
            dry_run=not args.live,
            label_name=args.label
        )

    print("\nTips for learning:")
    print("- Try different --query values")
    print("- Always test with dry-run first")
    print("- Add a new action (e.g. 'label') as an exercise")
    print("- Experiment with argparse options")


if __name__ == "__main__":
    main()