'''
    Copyright (C) 2019 Gitcoin Core

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published
    by the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program. If not, see <http://www.gnu.org/licenses/>.

'''
import csv
import json
import os
import pdfrw
import warnings

from django.core.management.base import BaseCommand
from dashboard.models import Bounty, Profile, Tip

warnings.filterwarnings("ignore", category=DeprecationWarning)


# Constants
DATETIME = 'datetime'
COUNTER_PARTY_NAME = 'counter_party_name'
COUNTER_PARTY_GITHUB_USERNAME = 'counter_party_github_username'
COUNTER_PARTY_LOCATION = 'counter_party_location'
TOKEN_AMOUNT = 'token_amount'
TOKEN_NAME = 'token_name'
USD_VALUE = 'usd_value'
WORKER_TYPE = 'worker_type'
COUNTRY_CODE = 'country_code'
COUNTRY_NAME = 'country_name'
COUNTRY = 'country'
LOCALITY = 'locality'
CITY = 'city'
CODE = 'code'
US = 'US'

NO_NAME = 'Name not found'
NO_USERNAME = 'Username not found'
NO_LOCATION = 'Location not found'
NO_PROFILE = 'Profile not found'

WEB3_NETWORK = 'rinkeby'
BOUNTY = 'bounty'
TIP = 'tip'
GRANT = 'grant'

TAX_REPORT_PATH = 'tax_report'
TAX_YEAR = 2018

MISC_1099_TEMPLATE_PATH = 'misc_1099_templates'
MISC_1099_COPY_1_TEMPLATE_PATH = os.path.join(MISC_1099_TEMPLATE_PATH, 'copy_1_template.pdf')
MISC_1099_COPY_2_TEMPLATE_PATH = os.path.join(MISC_1099_TEMPLATE_PATH, 'copy_2_template.pdf')
MISC_1099_COPY_B_TEMPLATE_PATH = os.path.join(MISC_1099_TEMPLATE_PATH, 'copy_b_template.pdf')
MISC_1099_COPY_C_TEMPLATE_PATH = os.path.join(MISC_1099_TEMPLATE_PATH, 'copy_c_template.pdf')
MISC_1099_TEMPLATES = [
                    (MISC_1099_COPY_1_TEMPLATE_PATH, 'misc_1099_copy_1.pdf'), 
                    (MISC_1099_COPY_2_TEMPLATE_PATH, 'misc_1099_copy_2.pdf'),
                    (MISC_1099_COPY_B_TEMPLATE_PATH, 'misc_1099_copy_b.pdf'),
                    (MISC_1099_COPY_C_TEMPLATE_PATH, 'misc_1099_copy_c.pdf')  
                    ]

MISC_1099_OUTPUT_PATH = 'misc_1099'

PAYER = 'payer'
NAME = 'name'
ADDRESS = 'address'
RECIPIENT = 'recipient'
LOCATION = 'location'

ANNOT_KEY = '/Annots'
ANNOT_FIELD_KEY = '/T'
ANNOT_VAL_KEY = '/V'
ANNOT_RECT_KEY = '/Rect'
SUBTYPE_KEY = '/Subtype'
WIDGET_SUBTYPE_KEY = '/Widget'


def send_email():
    print("send_email")


def create_csv_record(profiles_obj, wt_obj, worker_type, us_workers, b_ff=None):
    record = {DATETIME: wt_obj.created_on}
    counter_party_name = ''
    counter_party_github_username = ''
    counter_party_location = ''

    if worker_type == BOUNTY:
        counter_party_github_username = b_ff.fulfiller_github_username if b_ff.fulfiller_github_username else NO_USERNAME
    elif worker_type == TIP:
        counter_party_github_username = wt_obj.username if wt_obj.username else NO_USERNAME
    elif worker_type == GRANT:
        print('grant')

    if counter_party_github_username is not NO_USERNAME:
        profiles = profiles_obj.filter(handle__iexact=counter_party_github_username)
        if profiles.exists():
            profile = profiles.first()
            counter_party_name = profile.name if profile.name else NO_NAME
            counter_party_location, us_worker = get_profile_location(profile)
            if us_worker:
                if counter_party_github_username not in us_workers.keys():
                    us_workers[counter_party_github_username] = 0
                if worker_type == BOUNTY:
                    us_workers[counter_party_github_username] += wt_obj._val_usd_db
                elif worker_type == TIP:
                    us_workers[counter_party_github_username] += wt_obj.value_in_usdt
        else:
            counter_party_name = NO_PROFILE

    if worker_type == BOUNTY:
        record[USD_VALUE] = wt_obj._val_usd_db
        record[TOKEN_AMOUNT] = wt_obj.value_in_token
        record[TOKEN_NAME] = wt_obj.token_name
    elif worker_type == TIP:
        record[USD_VALUE] = wt_obj.value_in_usdt
        record[TOKEN_AMOUNT] = wt_obj.amount
        record[TOKEN_NAME] = wt_obj.tokenName
    elif worker_type == GRANT:
        print('grant')

    record[COUNTER_PARTY_NAME] = counter_party_name
    record[COUNTER_PARTY_GITHUB_USERNAME] = counter_party_github_username
    record[COUNTER_PARTY_LOCATION] = counter_party_location
    record[WORKER_TYPE] = worker_type

    return record, us_workers


def create_1099(form, recipient_path, template_path):
    data_dict = {
        'payer_details':form[PAYER][NAME] + '\n' + form[PAYER][ADDRESS] + '\n' + form[PAYER][LOCATION],
        'recipient_name':form[RECIPIENT][NAME],
        'street_address':form[RECIPIENT][ADDRESS],
        'location_details':form[RECIPIENT][LOCATION],
        'field_3':str(form[USD_VALUE]), # other income
        'field_18_a':'0', # state income a
        'field_18_b':'0' # statw income b
    } 
    template_pdf = pdfrw.PdfReader(template_path[0])
    annotations = template_pdf.pages[0][ANNOT_KEY]
    for annotation in annotations:
        if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
            if annotation[ANNOT_FIELD_KEY]:
                key = annotation[ANNOT_FIELD_KEY][1:-1]
                if key in data_dict.keys():
                    annotation.update(pdfrw.PdfDict(V='{}'.format(data_dict[key])))
    pdfrw.PdfWriter().write(os.path.join(recipient_path, template_path[1]) , template_pdf)


def get_profile_location(profile):
    us_worker = False
    location = NO_LOCATION
    location_temp = ''
    if profile.location:
        location_components = json.loads(profile.location)
        if LOCALITY in location_components:
            location_temp += location_components[LOCALITY] 
        if COUNTRY in location_components:
            country = location_components[COUNTRY]
            if location_temp:
                location_temp += ', ' + country
            else:
                location_temp += country
        if CODE in location_components:
            code = location_components[CODE]
            if location_temp:
                location_temp += ', ' + code
            else:
                location_temp += code
            # check if the user is from US
            if code == US:
                us_worker = True
    elif profile.locations:
        location_components = profile.locations[-1]
        if CITY in location_components:
            location_temp += location_components[CITY]
        if COUNTRY_NAME in location_components:
            country_name = location_components[COUNTRY_NAME]
            if location_temp:
                location_temp += ', ' + country_name
            else:
                location_temp += country_name
        if COUNTRY_CODE in location_components:
            country_code = location_components[COUNTRY_CODE]
            if location_temp:
                location_temp += ', ' + country_code
            else:
                location_temp += country_code
            if location_components[COUNTRY_CODE] == US:
                us_worker = True
    if location_temp:
        location = location_temp
    return location, us_worker
    
    
class Command(BaseCommand):

    help = 'the tax report for last year'

    def handle(self, *args, **options):
        profiles = Profile.objects.all()
        tax_path = os.path.join(os.getcwd(), TAX_REPORT_PATH)
        if not tax_path:
            os.makedirs(tax_path)
        for p in profiles:
            csv_record = []
            us_workers = {}
            # Bounty
            for b in p.get_sent_bounties:
                if not b._val_usd_db \
                    or b._val_usd_db <= 0 \
                    or b.status != 'done' \
                    or b.is_open is True \
                    or b.network != WEB3_NETWORK \
                    or p.username.lower() != b.bounty_owner_github_username.lower() \
                    or b.fulfillment_accepted_on.date().year != TAX_YEAR:
                    continue
                else:
                    for fulfiller in b.fulfillments.filter(accepted=True):
                        record, us_workers = create_csv_record(profiles, b, BOUNTY, us_workers, fulfiller)
                        csv_record.append(record)
            # Tip
            for t in p.get_sent_tips:
                if not t.value_in_usdt \
                    or t.value_in_usdt <= 0 \
                    or t.network != WEB3_NETWORK \
                    or p.username.lower() != t.from_username.lower() \
                    or p.username.lower() == t.username.lower() \
                    or t.created_on.date().year != TAX_YEAR:
                    continue
                else:
                    record, us_workers = create_csv_record(profiles, t, TIP, us_workers)
                    csv_record.append(record)
            # Grant
            '''for g in p.get_my_grants:
                if g.network != WEB3_NETWORK \
                    or g.created_on.date().year != TAX_YEAR:
                    continue
                else:
                    record, us_workers = create_csv_record(profiles, g, GRANT, us_workers)
                    csv_record.append(record)'''
            if len(csv_record) > 0:
                # check for create 1099
                username_path = os.path.join(os.getcwd(), TAX_REPORT_PATH, p.username)
                if not os.path.isdir(username_path):
                    os.makedirs(username_path)
                misc_path = os.path.join(username_path, MISC_1099_OUTPUT_PATH)
                if not os.path.isdir(misc_path):
                    os.makedirs(misc_path)
                for us_w, usd_value in us_workers.items():
                    recipient_profiles = profiles.filter(handle__iexact=us_w)
                    if recipient_profiles.exists():
                        recipient_profile = recipient_profiles.first()
                        if(usd_value>600):
                            recipient_path = os.path.join(misc_path, recipient_profile.username)
                            if not os.path.isdir(recipient_path):
                                os.makedirs(recipient_path)
                            form_data = {}
                            form_data[PAYER] = {}
                            form_data[PAYER][NAME] = p.name
                            form_data[PAYER][LOCATION] = get_profile_location(p)[0]
                            form_data[PAYER][ADDRESS] = p.address
                            form_data[RECIPIENT] = {}
                            form_data[RECIPIENT][NAME] = recipient_profile.name
                            form_data[RECIPIENT][LOCATION] = get_profile_location(recipient_profile)[0]
                            form_data[RECIPIENT][ADDRESS] = recipient_profile.address
                            form_data[USD_VALUE] = usd_value
                            for template in MISC_1099_TEMPLATES:
                                create_1099(form_data, recipient_path, template)
                # create csv
                csv_columns = [DATETIME, 
                            COUNTER_PARTY_NAME, 
                            COUNTER_PARTY_GITHUB_USERNAME, 
                            COUNTER_PARTY_LOCATION, 
                            TOKEN_AMOUNT, 
                            TOKEN_NAME, 
                            USD_VALUE, 
                            WORKER_TYPE]
                csv_file_path = os.path.join(username_path, p.username + '_tax_report.csv')
                try:
                    with open(csv_file_path, 'w') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                        writer.writeheader()
                        for row in csv_record:
                            writer.writerow(row)
                except IOError:
                    print("I/O error")
                if os.path.isfile(csv_file_path):
                    send_email()
                
