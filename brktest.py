python3 -c "
import requests, os
from dotenv import load_dotenv
load_dotenv()

server = os.environ['SERVER']
site = os.environ['SITE_NAME']
pat_name = os.environ['PAT_NAME']
pat_value = os.environ['PAT_VALUE']

# Sign in
auth = requests.post(f'{server}/api/3.19/auth/signin', json={
    'credentials': {
        'personalAccessTokenName': pat_name,
        'personalAccessTokenSecret': pat_value,
        'site': {'contentUrl': site}
    }
})
token = auth.json()['credentials']['token']
site_id = auth.json()['credentials']['site']['id']

# Query datasources
headers = {'x-tableau-auth': token}
ds = requests.get(f'{server}/api/3.19/sites/{site_id}/datasources?filter=name:eq:jujutest', headers=headers)
for d in ds.json()['datasources']['datasource']:
    print('Name:', d['name'], '| LUID:', d['id'])
"