from bwctl import jsonobject
from bwctl.tools import get_tool
from bwctl.jsonobject.exceptions import BadValueError

# Valid states:
#  accepted: rejected, failed, scheduled
#  rejected:
#  failed:
#  scheduled: client-confirmed, failed
#  client-confirmed: server-confirmed, finished, failed
#  server-confirmed: finished, failed
#  finished:

valid_test_status_changes = {
    "":[
         "accepted",
         "rejected",
         "failed"
    ],
    "accepted":[
        "scheduled",
        "cancelled",
        "failed"
    ],
    "rejected":[],
    "failed":[],
    "scheduled":[
         "client-confirmed",
         "rejected",
         "failed"
    ],
    "client-confirmed":[
         "server-confirmed",
         "rejected",
         "failed"
    ],
    "server-confirmed":[
         "rejected",
         "failed",
         "finished"
    ],
    "finished":[],
}

def valid_status(new_state):
    if not new_state in valid_test_status_changes:
        raise BadValueError("Test can't go to state %s" % new_state)

def valid_state_change(old_state, new_state):
    if not old_state:
        old_state = ""

    if not new_state in valid_test_status_changes:
        raise BadValueError("Test can't go to state %s" % new_state)

    if not new_state in valid_test_status_changes[old_state]:
        raise BadValueError("Test can't go from state %s to state %s" % (old_state, new_state))

    return

class BWCTLError(jsonobject.JsonObject):
    error_code = jsonobject.IntegerProperty(required=True)
    error_msg  = jsonobject.StringProperty(required=True)

class Results(jsonobject.JsonObject):
    status = jsonobject.StringProperty(exclude_if_none=True, required=True)
    results = jsonobject.DictProperty(unicode, exclude_if_none=True)
    bwctl_errors = jsonobject.ListProperty(BWCTLError, exclude_if_none=True)

class ClientSettings(jsonobject.JsonObject):
    address   = jsonobject.StringProperty(exclude_if_none=True, required=True)
    protocol  = jsonobject.FloatProperty(exclude_if_none=True, default=2.0, required=True)
    time      = jsonobject.DateTimeProperty(exact=True, exclude_if_none=True, required=True)
    ntp_error = jsonobject.FloatProperty(exclude_if_none=True)

class SchedulingParameters(jsonobject.JsonObject):
    priority               = jsonobject.FloatProperty(exclude_if_none=True)
    requested_time         = jsonobject.DateTimeProperty(exact=True, exclude_if_none=True, required=True)
    latest_acceptable_time = jsonobject.DateTimeProperty(exact=True, exclude_if_none=True)
    accepted_time          = jsonobject.DateTimeProperty(exact=True, exclude_if_none=True)

class Endpoint(jsonobject.JsonObject):
    address   = jsonobject.StringProperty(exclude_if_none=True, required=True)
    test_port = jsonobject.IntegerProperty(exclude_if_none=True)

    bwctl_protocol = jsonobject.FloatProperty(exclude_if_none=True, default=2.0, required=True)
    peer_port = jsonobject.IntegerProperty(exclude_if_none=True)
    base_path = jsonobject.StringProperty(exclude_if_none=True)
    test_id   = jsonobject.StringProperty(exclude_if_none=True)

    legacy_client_endpoint = jsonobject.BooleanProperty(exclude_if_none=True)
    posts_endpoint_status  = jsonobject.BooleanProperty(exclude_if_none=True)

    client_time_offset = jsonobject.IntegerProperty(exclude_if_none=True, default=0)
    ntp_error = jsonobject.FloatProperty(exclude_if_none=True)

class Test(jsonobject.JsonObject):
    id                    = jsonobject.StringProperty(exclude_if_none=True)

    status                = jsonobject.StringProperty(exclude_if_none=True, validators=valid_status)

    client                = jsonobject.ObjectProperty(ClientSettings, exclude_if_none=True)

    # The endpoints of the test
    sender_endpoint       = jsonobject.ObjectProperty(Endpoint, exclude_if_none=True, required=True)
    receiver_endpoint     = jsonobject.ObjectProperty(Endpoint, exclude_if_none=True, required=True)

    scheduling_parameters = jsonobject.ObjectProperty(SchedulingParameters, exclude_if_none=True, required=True)

    # Tool parameters
    tool                  = jsonobject.StringProperty(exclude_if_none=True, required=True)
    tool_parameters       = jsonobject.JsonObject(exclude_if_none=True, required=True)

    def change_state(self, new_state):
        valid_state_change(self.status, new_state)
        self.status = new_state

    @property
    def fuzz(self):
        offset = 0
        if self.sender_endpoint:
            offset = offset + self.sender_endpoint.client_time_offset

        if self.sender_endpoint:
            offset = offset - self.sender_endpoint.client_time_offset

        if offset < 0:
            offset = -offset

        return offset

    @property
    def test_type(self):
        tool = get_tool(self.tool)
        if not tool:
            raise SystemProblemException("Unknown tool type")

        return tool.type

    @property
    def duration(self):
        tool = get_tool(self.tool)
        if not tool:
            raise SystemProblemException("Unknown tool type")

        return tool.duration(self)

    @property
    def bandwidth(self):
        tool = get_tool(self.tool)
        if not tool:
            raise SystemProblemException("Unknown tool type")

        return tool.bandwidth(self)
