from __future__ import print_function
import pickle, json, re, base64, email, random
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

country_regex = re.compile(r"(address|country)\:\s+(\w+)$")
ip_regex = re.compile(r"The IP ([\d\.]+) has")
phone_regex = re.compile(r"(?:p|P)hone(?:[\s\:]*)\+([\d]{1,2})")

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def main():


	"""Shows basic usage of the Gmail API.
	Lists the user's Gmail labels.
	"""
	creds = None
	# The file token.pickle stores the user's access and refresh tokens, and is
	# created automatically when the authorization flow completes for the first
	# time.
	if os.path.exists('token.pickle'):
		with open('token.pickle', 'rb') as token:
			creds = pickle.load(token)
	# If there are no (valid) credentials available, let the user log in.
	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file(
				'credentials.json', SCOPES)
			creds = flow.run_local_server(port=0)
		# Save the credentials for the next run
		with open('token.pickle', 'wb') as token:
			pickle.dump(creds, token)


	service = build('gmail', 'v1', credentials=creds)
	fail2ban_id = 'Label_2855184894679463985'

	results = service.users().messages().list(userId='me', labelIds=[fail2ban_id]).execute()
	messages = []

	if 'messages' in results:
		messages = results.get('messages', [])
		message_handler(service, messages)


	while 'nextPageToken' in results:
		page_token = results['nextPageToken']
		results = service.users().messages().list(userId='me', labelIds=[fail2ban_id], pageToken=page_token).execute()
		messages = results.get('messages', [])
		message_handler(service, messages)


	for k,v in ALL_BANS.items():
		if v['count'] > 1:
			print(" {} : {} ".format(k, v))


	with open(os.path.abspath('country_weights.json'), 'w+') as f:
		json.dump(COUNTRY_WEIGHTS, f, indent=4)

	with open(os.path.abspath('phone_codes.json'), 'w+') as f:
		json.dump(PHONE_CODES, f, indent=4)

	with open(os.path.abspath('bans.js'), 'w+') as f:
		json.dump(ALL_BANS, f, indent=4)

	# Call the Gmail API
	#results = service.users().labels().list(userId='me').execute()
	#labels = results.get('labels', [])
	#if not labels:
	#	print('No labels found.')
	#else:
	#	print('Labels:')
	#	for label in labels:
	#		print(label['name'])

def message_handler(service, messages):

	message_ids = [x['id'] for x in messages]
	for id in message_ids:

		POTENTIAL = []
		ip = ''
		country = ''
		encoded_msg = service.users().messages().get(userId='me', format='raw', id=id).execute()
		snippet = encoded_msg.get('snippet', '')
		ip_match = ip_regex.search(snippet)
		if ip_match:
			ip = ip_match.group(1)
			# print('Found IP {} in snippet'.format(ip))

		msg_bytes = base64.urlsafe_b64decode(encoded_msg['raw'].encode('ASCII'))
		msg_str = msg_bytes.decode()
		email_msg = email.message_from_string(msg_str)
		date = email_msg.get('Date', '')
		# print('date: ', date)

		body = email_msg.get_payload()
		body_list = body.split("\r")

		country_list = []
		address_list = []
		phone_code = ""
		POTENTIAL_MATCHES = []

		for _li in body_list:
			li = _li.lower()

			LI = li.upper()

			if POTENTIAL:

				for x in POTENTIAL:
					s = "(?:address|country)(?:[\:\s\,\w]*?)({})".format(x.lower())
					regex = re.compile(r"{}".format(s))
					match = regex.search(li)
					if match:
						POTENTIAL_MATCHES.append(COUNTRY_CODES[match.group(1)])
						#country_list.append(COUNTRY_CODES[match.group(1)])


			phone_match = phone_regex.search(LI)
			if phone_match:
				phone_code = phone_match.group(1)
				# print("phone_code: ", phone_code)

			if not ip:
				ip_match = ip_regex.search(LI)
				if ip_match:
					ip = ip_match.group(1)
					# print('ip: ', ip)

			if 'country' in li:
				country_match = country_regex.search(li)
				if country_match:
					cmatch = country_match.group(2).upper()
					country_list.append(cmatch)
					POTENTIAL.append(ABBREVIATIONS[cmatch].lower())
					# print('country: ', country_match.group(2))
				else:
					print('No re match for country in: {}'.format(LI))

			if 'address' in li:
				# print('\n ** ', li)
				address_list.append(li)

		if len(address_list) > 0:
			# print('last address element: ', address_list[-1])
			match = country_regex.search(address_list[-1])
			if match:
				country_list.append(match.group(2).upper())
			else:
				print('No re match for country in: {}'.format(LI))

		weighted_vals = []
		for x in country_list:
			if x not in COUNTRY_WEIGHTS.keys():
				COUNTRY_WEIGHTS[x] = 1

			weighted_vals.append(COUNTRY_WEIGHTS[x])

		weighted = [x for x in country_list if COUNTRY_WEIGHTS[x] == max(weighted_vals)]

		if len(weighted) > 1:
			# print('weighted: ', weighted)
			country = random.choice(weighted)
		elif weighted:
			country = weighted[0]

		if phone_code:
			if phone_code not in PHONE_CODES.keys():
				if country:
					PHONE_CODES[str(phone_code)] = country
				else:
					PHONE_CODES[str(phone_code)] = "??"

		if not ip:
			continue
		else:
			print("NEW ENTRY: {:<15} {:^15} {:>}".format(ip, country, date))

		if ip not in ALL_BANS.keys():
			ALL_BANS[ip] = {}
			ALL_BANS[ip]['count'] = 0

		if id in ALL_BANS[ip].keys():
			continue
		else:
			ALL_BANS[ip]['count'] += 1
			ALL_BANS[ip][id] = {}
			ALL_BANS[ip][id]['country'] = country.upper()
			ALL_BANS[ip][id]['date'] = date
			ALL_BANS[ip][id]['choices'] = country_list
			ALL_BANS[ip][id]['stats'] = {}
			if POTENTIAL:
				ALL_BANS[ip][id]['POTENTIAL'] = POTENTIAL
			if POTENTIAL_MATCHES:
				ALL_BANS[ip][id]['POTENTIAL_MATCHES'] = POTENTIAL_MATCHES
			if len(set(country_list)) > 1:
				ALL_BANS[ip][id]['stats']['ratio'] = {}
				for x in set(country_list):
					ALL_BANS[ip][id]['stats']['ratio'][x] = country_list.count(x)




def get_item_list(path):
	all_items = ''
	mode = "w+" if not os.path.exists(path) else "r"
	with open(path, mode) as f:
		all_items = json.load(f) if os.path.getsize(path)>0 else {}

	if len(all_items) > 0:
		sorted_dict = dict(all_items.items())
		return sorted_dict
	else:
		return all_items

ALL_BANS = get_item_list(os.path.abspath('bans.js'))
COUNTRY_WEIGHTS = get_item_list(os.path.abspath('country_weights.json'))
PHONE_CODES = get_item_list(os.path.abspath('phone_codes.json'))
ABBREVIATIONS = get_item_list(os.path.abspath('abbreviations.json'))
COUNTRY_CODES = {k.lower():v for k,v in get_item_list(os.path.abspath('country_codes.json')).items()}

if __name__ == '__main__':
	main()
