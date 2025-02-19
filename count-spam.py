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
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
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
    """Retrieves spam emails for the past 31 days and counts them by date."""

    today = datetime.date.today()
    daily_counts = defaultdict(int)

    try:
        # Get all messages in the SPAM folder
        results = service.users().messages().list(
            userId='me', labelIds=['SPAM']).execute()
        messages = results.get('messages', [])

        while 'nextPageToken' in results:  # Handle pagination
            page_token = results['nextPageToken']
            results = service.users().messages().list(userId='me', labelIds=[
                'SPAM'], pageToken=page_token).execute()
            messages.extend(results.get('messages', []))

        if not messages:
            print('No spam messages found.')
            return daily_counts

        # Process Each Message to extract date
        for message in messages:
            msg = service.users().messages().get(userId='me',
                                                 id=message['id'], format='metadata', metadataHeaders=['Date']).execute()
            headers = msg['payload']['headers']
            date_str = None
            for header in headers:
                if header['name'] == 'Date':
                    date_str = header['value']
                    break

            if date_str:
                try:
                    # Parse the date string.  RFC 2822 format.  Handle timezone.
                    # Example: "Fri, 20 Oct 2023 15:01:23 -0700" or "21 Oct 2023 00:48:13 +0200"
                    # Remove timezone offset, as datetime.strptime doesn't easily handle varying timezones.

                    date_str = ' '.join(date_str.split()[:-1])

                    # Use strptime to create a datetime object
                    dt = datetime.datetime.strptime(
                        date_str, '%a, %d %b %Y %H:%M:%S')  # Weekday

                except ValueError:
                    try:
                        dt = datetime.datetime.strptime(
                            date_str, '%d %b %Y %H:%M:%S')  # No Weekday
                    except ValueError:
                        print(f"Could not parse date: {date_str}")
                        continue  # skip current message

                email_date = dt.date()

                # Check if the email is within the past 31 days
                if (today - email_date).days <= 31:
                    daily_counts[email_date] += 1

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
            # Print the results
            print("Spam email counts for the past 31 days:")
            for date, count in sorted(spam_counts.items()):  # Sort by date
                print(f"{date}: {count}")
    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    main()
