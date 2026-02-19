import http.client, uuid, sys
filename='tmp_test_upload.py'
content = b"# temp test\nx = " + b"eval" + b"('2 + 2')\n"
boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
part = []
part.append(f'--{boundary}')
part.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"')
part.append('Content-Type: text/x-python\r\n')
body = '\r\n'.join(part).encode('utf-8') + b"\r\n" + content + ('\r\n--%s--\r\n' % boundary).encode('utf-8')
conn = http.client.HTTPConnection('127.0.0.1', 8000)
conn.request('POST', '/scan-file?include_ai=true', body, {'Content-Type': 'multipart/form-data; boundary=' + boundary})
res = conn.getresponse()
print(res.status, res.reason)
print(res.read().decode('utf-8'))
