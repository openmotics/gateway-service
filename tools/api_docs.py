import json
import re
import urllib

def document_v0_api():
        import gateway
        def_regex = re.compile(r'^\s*?def ([^(]+)\((.*?)\):')
        with open('{0}/webservice.py'.format(gateway.__path__[0]), 'r') as source:
            contents = source.readlines()
        calls = {}
        found_call = False
        for line in contents:
            if found_call is True:
                # This line is a call definition and needs to be parsed/loaded
                match = def_regex.match(line)
                if match is not None:
                    groups = match.groups()
                    calls[groups[0]] = [argument.split('=')[0] for argument in groups[1].split(', ')
                                        if argument != 'self']
                found_call = False
            elif '@openmotics_api' in line:
                found_call = True
        return calls


if __name__ == "__main__":
    docs = {'info': {"name": "OpenMotics - Gateway API v0",
                     "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                     "description": "The Gateway API v0"},
            'item': []}

    api_endpoints = document_v0_api()
    for api_name in sorted(api_endpoints):
        endpoint = "/{}".format(api_name)
        api_params = api_endpoints[api_name]
        print(api_params)
        item = {"name": endpoint,
                "description": endpoint,
                "item": [{"name": endpoint,
                          "request": {
                             "method": "GET",
                              "header": [],
                              "url": {"raw": "{{gw-ip}}/%s?%s" % (api_name, urllib.urlencode({api_param: '{}_value'.format(api_param) for api_param in api_params})),
                                      "host": ["{{gw-ip}}"],
                                      "path": ["{}".format(api_name)],
                                      "query": [{"key": key, "value": "{{%s}}" % key} for key in api_params]},
                              "description": "{}".format(endpoint)
                          },
                          "response": [
                            {
                                "name": endpoint,
                                "originalRequest": {
                                    "method": "GET",
                                    "header": [],
                                    "url": {
                                        "raw": "{{gw-ip}}/%s" % api_name,
                                        "host": ["{{gw-ip}}"],
                                        "path": ["{}".format(api_name)]
                                    }
                                },
                                "_postman_previewlanguage": "json",
                                "header": None,
                                "cookie": [],
                                "body": ""
                            }
                        ]
                    }]}
        docs['item'].append(item)
    api_docs = open('gw-postman-collection.json', 'w')
    api_docs.write(json.dumps(docs))
    print(docs)

