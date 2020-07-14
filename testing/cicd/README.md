# Integration Tests

The testing toolbox uses the following environment variables to connect to the
tester and dut gateways.  The tests also expects the event_observer and
syslog_receiver (debugging only) plugins to be installed on the tester gateway.

```
OPENMOTICS_TESTER_AUTH=username:password
OPENMOTICS_TESTER_HOST=gateway-tester.qa.openmotics.com
OPENMOTICS_DUT_AUTH=username:password
OPENMOTICS_DUT_HOST=gateway-testee-debian.qa.openmotics.com
```

- quick smoketest

```
pytest testing/cicd/tests --disable-warnings --hypothesis-profile once -m smoke
```

- full testrun

```
pytest testing/cicd/tests --disable-warnings --log-cli-level INFO --log-level DEBUG -m 'smoke or slow'
```

## Updating Firmware

The tests can also target specific firmware versions, in which case the gateway
will retrieve firmware from the cloud and flash it before running the tests.
This uses the `/update_firmware` api which requires a cloud_url to be configured.

```
OPENMOTICS_MASTER_FIRMWARE=3.143.93 pytest testing/cicd/tests --disable-warnings -m smoke
```

## Debugging

For debugging it can be useful to use the Toolbox interactively.

```
ipython -i testing/cicd/tests/conftest.py
In [1]: t = Toolbox()

In [2]: t.dut.login()
Out[2]: u'44b789c29aeb47eb8b93bff5f1c4113d'
```

## Target gateway deployment

The test system is also deployed slightly differently.

- syslog to the plugin running on the tester system

```
rsync rsyslog/99-openmotics-tester.conf target:/etc/rsyslog.d/
ssh target -- systemctl restart rsyslog
```

- run gateway services using systemd

```
rsync -a systemd/ target:/etc/systemd/system/
```

```
systemctl stop supervisor
systemctl disable supervisor

systemctl daemon-reload

systemctl enable openmotics
systemctl enable openmotics-led
systemctl enable openmotics-vpn
systemctl enable openmotics-watchdog

systemctl start openmotics
systemctl start openmotics-led
systemctl start openmotics-vpn
systemctl start openmotics-watchdog
```
