#! /bin/bash

IP=
SECRET=
FILENAME=gw_service.zip


gpg --sign $FILENAME

curl -X POST -vvv -k -H 'X-API-Secret: $SECRET' -F file=@$FILENAME.gpg https://$IP:8002/v1/packages/file

