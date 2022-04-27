import logging
import uuid

import cherrypy

from gateway.api.V1.webservice import ApiResponse, RestAPIEndpoint, expose, \
    openmotics_api_v1


SCHEMA = {
    "room": {
        "type": "object",
        "required": ["id"],
        "actions": ["list"],
        "properties": {
            "id": {
                "type": "integer",
                "maximum": 254,
                "readOnly": True
            },
            "name": {
                "type": "string",
                "maxLength": 255
            }
        },
        "definitions": {
        }
    },
    "ventilation_unit": {
        "type": "object",
        "required": ["id", "name", "room"],
        "actions": ["list", "update"],
        "properties": {
            "id": {
                "type": "integer",
                "readOnly": True
            },
            "name": {
                "type": "string",
                "maxLength": 255
            },
            "room": {
                "$ref": "#/definitions/room_id"
            },
            "amount_of_levels": {
                "type": "integer",
                "readOnly": True
            },
            "source": {
                "enum": ["plugin"],
                "readOnly": True
            },
            "device": {
                "type": "object",
                "properties": {
                    "vendor": {
                        "type": "string",
                        "default": "",
                        "readOnly": True
                    },
                    "type": {
                        "type": "string",
                        "default": "",
                        "readOnly": True
                    },
                    "serial": {
                        "type": "string",
                        "default": "",
                        "readOnly": True
                    }
                }
            }
        },
        "dependencies": {
            "source": {
                "oneOf": [
                    {
                        "properties": {
                            "source": {"const": "plugin"},
                            "plugin": {
                                "$ref": "#/definitions/plugin_id",
                                "readOnly": True
                            },
                            "external_id": {
                                "type": "string",
                                "readOnly": True
                            }
                        }
                    }
                ]
            }
        },
        "definitions": {
            "room_id": {
                "type": ["integer", "null"],
                "maximum": 254,
                "format": "entity-dropdown",
                "format:options": {
                    "empty": True
                },
                "entity": "rooms"
            },
            "plugin_id": {
                "type": ["integer"],
                "format": "entity-dropdown",
                "entity": "plugins"
            }
        }
    }
}


@expose
class Schema(RestAPIEndpoint):
    API_ENDPOINT = '/api/schema'

    def __init__(self):
        # type: () -> None
        super(Schema, self).__init__()
        self.route_dispatcher = cherrypy.dispatch.RoutesDispatcher()
        self.route_dispatcher.connect('retrieve', '',
                                      controller=self, action='retrieve',
                                      conditions={'method': ['GET']})

    @openmotics_api_v1(auth=False)
    def retrieve(self):
        return ApiResponse(body=SCHEMA)
