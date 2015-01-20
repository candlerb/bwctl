from bwctl.tool_types.latency_base import LatencyBase

class Owamp(LatencyBase):
    name = "owamp"
    known_parameters = [ "packet_count", "inter_packet_time", " packet_size", "receiver_connects" ]

    def config_options(self):
        return {
            "owping_cmd":  "string(default='owping')",
            "owampd_cmd":  "string(default='owampd')",
            "owamp_ports": "string(default='')",
            "disable_owamp": "boolean(default=False)",
        }

    def build_command_line(self, test):
        cmd_line = []

        if test.local_client:
            cmd_line.extend(self.get_config_item('owping_cmd'))

            if "packet_count" in test.tool_parameters:
                cmd_line.extend(["-c", test.tool_parameters['packet_count']])

            if "inter_packet_time" in test.tool_parameters:
                cmd_line.extend(["-i", test.tool_parameters['inter_packet_time']])

            if "packet_size" in test.tool_parameters:
                cmd_line.extend(["-s", test.tool_parameters['packet_size']])

            if test.local_receiver:
                cmd_line.extend([test.sender_endpoint.address])
            else:
                cmd_line.extend(["-t", test.receiver_endpoint.address])
        else:
            cmd_line.extend(self.get_config_item('owampd_cmd'))

            cmd_line.extend(["-S", test.receiver_endpoint.address])

        return cmd_line
