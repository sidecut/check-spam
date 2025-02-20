import os.path
import datetime
import base64
from collections import defaultdict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def authenticate_gmail():
    """Authenticates with the Gmail API using OAuth 2.0."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)  # Download credentials.json from Google Cloud Console
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def get_spam_counts(service):
    """Retrieves spam emails for the past 31 days and counts them by date using internalDate."""

    today = datetime.date.today()
    daily_counts = defaultdict(int)
    spinner_chars = ['|', '/', '-', '\\']
    message_count = 0

    try:
        # Get all messages in the SPAM folder, only fetch id and internalDate
        # Use maxResults=500 (max allowed) to reduce API calls
        messages = []
        next_page_token = None

        while True:
            results = service.users().messages().list(
                userId='me',
                labelIds=['SPAM'],
                maxResults=500,
                pageToken=next_page_token,
                fields='messages(id),nextPageToken'  # Only fetch needed fields
            ).execute()

            if 'messages' in results:
                messages.extend(results['messages'])

            if 'nextPageToken' not in results:
                break
            next_page_token = results['nextPageToken']

        if not messages:
            print('No spam messages found.')
            return daily_counts

        # Batch get messages in groups of 50 to reduce API calls
        for i in range(0, len(messages), 50):
            batch = messages[i:i + 50]

            # Create batch request
            batch_request = service.new_batch_http_request()

            def callback(request_id, response, exception):
                nonlocal message_count
                if exception is None:
                    # Convert internalDate to date and increment counter
                    internal_date_ms = int(response['internalDate'])
                    email_date = datetime.datetime.fromtimestamp(
                        internal_date_ms / 1000).date()

                    if (today - email_date).days <= 31:
                        daily_counts[email_date] += 1

                # Update spinner
                print(
                    f'\rProcessing messages... {spinner_chars[message_count % 4]}', end='')
                message_count += 1

            # Add each message to the batch request
            for msg in batch:
                batch_request.add(
                    service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='minimal',  # Only fetch minimal data
                        fields='internalDate'  # Only fetch the date field
                    ),
                    callback=callback
                )

            # Execute the batch request
            batch_request.execute()

        # Clear the spinner line when done
        print('\rProcessed {} messages.          '.format(message_count))

    except HttpError as error:
        print(f'An error occurred: {error}')
        return None

    return daily_counts


def main():
    """Main function to authenticate and get spam counts."""

    creds = authenticate_gmail()
    try:
        # Build the Gmail service
        service = build('gmail', 'v1', credentials=creds)

        # Get spam counts
        spam_counts = get_spam_counts(service)

        if spam_counts is not None:
            print("Spam email counts for the past 31 days (based on internalDate):")
            for date, count in sorted(spam_counts.items()):
                # Format date to include day of week abbreviation
                day_of_week = date.strftime("%a")
                print(f"{day_of_week} {date}: {count}")
    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    main()
