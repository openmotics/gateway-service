import requests
import ujson as json

BASE_URL = 'http://localhost:8088/'  # set the port and IP address correct
USERNAME = '<Your username here>'
PASSWD = '<Your password here>'
TOKEN = ''  # will be filled in by the login request
VERBOSE = 1  # verbose 0 => No output, 1 => minimal output, 2 => full output


def create_url(endpoint):
    url = '{}{}'.format(BASE_URL, endpoint)
    return url


def pretty_print_dict(data, prefix=''):
    result = ''
    if data is None:
        return '\n'
    for k, v in data.items():
        result += '{}{}: {}\n'.format(prefix, k, v)
    return result


def pretty_print_output(output):
    try:
        json_dict = json.loads(output)
        json_str = json.dumps(json_dict, indent=4)
        return json_str
    except Exception:
        return output


def api_call(endpoint, method='get', headers=None, params=None, body=None, authenticated=True, verbose=None):
    if verbose is None:
        verbose = VERBOSE
    if headers is None:
        headers = {}
    if TOKEN != '' and authenticated:
        headers.update({'Authorization': 'Bearer {}'.format(TOKEN)})

    method = method.lower()
    url = create_url(endpoint)

    if params is None:
        params = {}

    if verbose == 1:
        print('Perform request: {}'.format(url))
    elif verbose == 2:
        headers_str = pretty_print_dict(headers, prefix='    ')
        params_str = pretty_print_dict(params, prefix='    ')
        print('Perform request:\n  url: {},\n  method: {},\n  headers:\n{}  params:\n{}  body: {}\n'
              .format(url, method, headers_str, params_str, body))

    if method == 'get':
        response = requests.get(url=url, headers=headers, params=params)
    elif method == 'post':
        response = requests.post(url=url, headers=headers, params=params, data=body)

    resp_body = '\n'.join([str(x.decode()) for x in response.iter_lines()])
    if verbose == 1:
        print('  => Response body: {}'.format(resp_body))
        print('--------------------------------------------')
    elif verbose == 2:
        headers = pretty_print_dict(response.headers, prefix='    ')
        body = pretty_print_output(resp_body)
        body_indent = ''
        for line in body.splitlines():
            body_indent += '    {}\n'.format(line)

        print('Response:\n  code: {},\n  headers:\n{}  body:\n{}'
              .format(response.status_code, headers, body_indent))
        print('--------------------------------------------')
    return response


def login(verbose=None):
    global TOKEN
    if verbose == None:
        verbose = VERBOSE
    params = {'username': USERNAME, 'password': PASSWD}
    resp = api_call('login', params=params, authenticated=False, verbose=verbose)
    resp_json = resp.json()
    if 'token' in resp_json:
        token = resp.json()['token']
        TOKEN = token
        if verbose > 0:
            print(' => logged in and received token: {}'.format(token))
            print('--------------------------------------------')
    else:
        raise RuntimeError('Could not log in to the gateway')
    return token


def main():
    # do requests here
    # Example requests to the get_version endpoint
    login(verbose=1)
    api_call('get_version', authenticated=False)
    api_call('get_version', authenticated=True)
    api_call('get_version', verbose=2, authenticated=False)
    api_call('get_version', verbose=2, authenticated=True)


if __name__ == '__main__':
    main()
