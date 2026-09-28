# Gmail Cleaner

A small Python command-line tool for reviewing Gmail search results and, when explicitly requested, archiving, moving to Trash, or labeling matching messages. It is also a learning project: the code keeps authentication, search, preview, argument parsing, and actions in separate functions so the path from a command to a Gmail API call is easy to follow.

## Why this exists

Inbox cleanup is a useful exercise in working with a real API. The goal is to understand OAuth, Gmail search queries, message metadata, batch label changes, and the difference between previewing a proposed action and performing it. The script starts in preview or dry-run mode so you can inspect a query before changing mail.

## How it works

1. A local OAuth flow grants the script the `gmail.modify` scope. Google stores the downloaded desktop app client configuration in `credentials.json`; the script saves the resulting user token in `token.json` for later runs.
2. `--query` is sent to Gmail's `messages.list` endpoint. The script reads only the first page of results, up to `--max` messages.
3. For each result, `messages.get` fetches the **From** and **Subject** headers for display.
4. The default `preview` action makes no mailbox changes. For `archive`, `trash`, or `label`, the script also makes no changes unless `--live` is present. A live archive removes the `INBOX` label with `messages.batchModify`; a live trash action calls `messages.trash` once per message. If a trash request fails, the script reports how many messages it already moved.
5. For a live `label` action, `get_or_create_label` searches existing labels by name without regard to capitalization. If it finds one, the script applies its ID to the matching messages. Otherwise it attempts to create a new label, then applies it. A dry run only prints the proposed label name; it does not look up or create a label.

This operates on **messages**, which may be individual members of a conversation. Gmail's search results and label behavior are documented in the [Gmail API guide](https://developers.google.com/workspace/gmail/api/guides/list-messages) and [label guide](https://developers.google.com/workspace/gmail/api/guides/labels).

## Setup

### 1. Prepare Google Cloud

You need a Google account with Gmail enabled and a Google Cloud project. In the [Google Cloud console](https://console.cloud.google.com/):

1. Create or select a project, then enable the **Gmail API** for it.
2. Open **Google Auth Platform → Branding** and configure the OAuth consent screen. For a personal Google account, choose an **External** audience; **Internal** is for eligible Google Workspace organizations. If the app is in Testing, add the Gmail account you will use under **Audience → Test users**.
3. In **Data Access**, add the Gmail scope `https://www.googleapis.com/auth/gmail.modify`. It permits reading and modifying mail and is a restricted scope; review the access requested before granting consent. Public distribution can require Google's OAuth verification.
4. Open **Google Auth Platform → Clients**, create an OAuth client with application type **Desktop app**, download its JSON file, and save it as `credentials.json` in this directory.

Google's [Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) has the current console walkthrough. Its sample uses a read-only scope; this project requires [`gmail.modify`](https://developers.google.com/workspace/gmail/api/auth/scopes) for archive, trash, and label actions.

### 2. Install Python dependencies

Use Python 3.10.7 or newer. From this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. Preview a small search

Run commands **from this directory**, because the script looks for `credentials.json` and `token.json` in the current working directory.

```sh
python gmail_cleaner.py --query "category:promotions older_than:6m" --max 10
```

The first run opens a browser for Google authorization. After consent, the script creates `token.json`. An External app in Testing may require reauthorization when its test-user authorization expires; see [Google's audience guidance](https://support.google.com/cloud/answer/15549945).

## Usage

```sh
# List matching sender and subject headers; no mailbox changes.
python gmail_cleaner.py --query "from:newsletter@example.com" --max 10

# Show what an archive would do; still no mailbox changes.
python gmail_cleaner.py --query "category:promotions older_than:6m" --action archive --max 10

# Perform the archive after reviewing the query and preview.
python gmail_cleaner.py --query "category:promotions older_than:6m" --action archive --max 10 --live

# Move matching messages to Trash.
python gmail_cleaner.py --query "category:updates older_than:1y" --action trash --max 10 --live

# Preview applying an existing Gmail label.
python gmail_cleaner.py --query "from:newsletter@example.com" --action label --label "Newsletters" --max 10

# Apply that label after reviewing the dry run.
python gmail_cleaner.py --query "from:newsletter@example.com" --action label --label "Newsletters" --max 10 --live
```

`--action` accepts `preview` (the default), `archive`, `trash`, or `label`. `--action label` requires `--label NAME`; the name may contain spaces if quoted. `--label` is ignored for other actions. `--max` defaults to 25 and must be between 1 and 500, Gmail's limit for one `messages.list` request. The script does not paginate, so a larger matching set will not be processed in full.

**Before using `--live`:** review the query, the displayed messages, and the result count. A failed search exits with an error. If any message fails to preview, a dry run leaves it out of the count, and a live run aborts without changing anything. Gmail may also change between preview and the action; this is a small learning tool, not an audited bulk-mail workflow.

## Local data and secrets

- `credentials.json` contains the OAuth client configuration; `token.json` contains user authorization tokens. Keep both private. The included `.gitignore` prevents Git from adding them in a new repository, but it cannot remove files already committed elsewhere.
- The script writes `token.json` readable only by your user (mode `600`). `credentials.json` keeps whatever permissions it was downloaded with; restrict it on a shared computer, for example with `chmod 600 credentials.json` on macOS or Linux.
- The script prints sender and subject information to the terminal. Avoid sharing terminal output or logs containing private mail details.
- If you change the OAuth scope in the code, delete your local `token.json` and authorize again, as noted in the script.
