import urllib.request, json
try:
    req = urllib.request.Request('http://localhost:8000/api/auth/register', data=json.dumps({'email': 'test@example.com', 'username': 'testuser', 'password': 'TestPassword123!'}).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    print(urllib.request.urlopen(req).read().decode('utf-8'))
except Exception as e:
    print(e.read().decode('utf-8'))
