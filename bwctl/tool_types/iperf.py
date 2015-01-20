from bwctl.tool_types.base import Base
from bwctl.tools import ToolTypes

class Iperf(Base):
    name = "iperf"
    type = ToolTypes.THROUGHPUT
    known_parameters = [ "duration", "protocol", "bandwidth", "parallel_streams", "report_interval", "window_size", "buffer_size", "omit_seconds", "tos_bits", "units", "output_format" ]

    def config_options(self):
        return {
            "iperf_cmd":  "string(default='iperf')",
            "iperf_ports": "string(default='')",
            "disable_iperf": "boolean(default=False)",
        }

    def build_command_line(self, test):
        cmd_line = []

        cmd_line.extend(["iperf"])

        # Print the MTU as well
        cmd_line.extend(["-m"])

        if test.local_receiver:
            cmd_line.extend(["-B", test.receiver_endpoint.address])
        else:
            cmd_line.extend(["-B", test.sender_endpoint.address])

        if test.local_receiver:
            cmd_line.extend(["-s"])
        else:
            cmd_line.extend(["-c", test.receiver_endpoint.address])
            cmd_line.extend(["-p", test.receiver_endpoint.test_port])

        cmd_line.extend(["-t", test.tool_parameters['duration']])

        if "units" in test.tool_parameters:
            cmd_line.extend(["-f", test.tool_parameters['units']])

        if "tos_bts" in test.tool_parameters:
            cmd_line.extend(["-S", test.tool_parameters['tos_bits']])

        if "output_format" in test.tool_parameters:
            cmd_line.extend(["-y", test.tool_parameters['output_format']])

        if "parallel_streams" in test.tool_parameters:
            cmd_line.extend(["-P", test.tool_parameters['parallel_streams']])

        return cmd_line
