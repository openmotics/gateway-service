#! /bin/bash

IP=192.168.0.154
SECRET=DsFeQrLf_R19Aksz
FILENAME=gw_service.zip


gpg --sign $FILENAME

curl -X POST -vvv -k -H 'X-API-Secret: $SECRET' -F file=@$FILENAME.gpg https://$IP:8002/v1/packages/file

