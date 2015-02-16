import datetime
import optparse
import re
import socket
import sys
import time
import inspect

from multiprocessing import Queue

from bwctl.dependencies.requests.exceptions import HTTPError

#-B|--local_address <address>     Use this as a local address for control connection and tests
#-E|--no_endpoint                 Allow tests to occur when the receiver isn't running bwctl (Default: False)
#-o|--flip                        Have the receiver connect to the sender (Default: False)
#
#Scheduling Arguments
#-I|--test_interval <seconds>     Time between repeated bwctl tests
#-L|--latest_time <seconds>       Latest time into an interval to allow a test to run
#-n|--num_tests <num>             Number of tests to perform (Default: 1)
#-R|--randomize <percent>         Randomize the start time within this percentage of the test's interval (Default: 10%)
#--schedule <schedule>            Specify the specific times when a test should be run (e.g. --schedule 11:00,13:00,15:00)
#--streaming                      Request the next test as soon as the current test finishes
#
#Test Arguments
#-b|--bandwidth <bandwidth>       Bandwidth to use for tests (bits/sec KM) (Default: 1Mb for UDP tests, unlimited for TCP tests)
#-D|--dscp <dscp>                 RFC 2474-style DSCP value for TOS byte
#-i|--report_interval <seconds>   Tool reporting interval
#-l|--buffer_length <bytes>       Size of read/write buffers
#-O|--omit <seconds>              Omit time (currently only for iperf3)
#-P|--parallel <num>              Number of concurrent connections
#-S|--tos <tos>                   Type-Of-Service for outgoing packets
#-u|--udp                         Perform a UDP test
#-w|--window <bytes>              TCP window size (Default: system default)
#-W|--dynamic_window <bytes>      Dynamic TCP window fallback size (Default: system default)
#--tester_port <port>             For an endpoint-less test, use this port as the server port (Default: tool specific)
#
#Output Arguments
#-d|--output_dir <directory>      Directory to save session files to (only if -p)
#-e|--facility <facility>         Syslog facility to log to
#-f|--units <unit>                Type of measurement units to return (Default: tool specific)
#-p|--print                       Print results filenames to stdout (Default: False)
#-q|--quiet                       Silent mode (Default: False)
#-r|--syslog_to_stderr            Send syslog to stderr (Default: False)
#-v|--verbose                     Display verbose output
#-x|--both                        Output both sender and receiver results
#-y|--format <format>             Output format to use (Default: tool specific)
#--parsable                       Set the output format to the machine parsable version for the select tool, if available
#
#Misc Arguments
#-V|--version                     Show version number

from bwctl.protocol.v2.client import Client
from bwctl.tools import get_tools, get_tool, ToolTypes, configure_tools, get_available_tools
from bwctl.tool_runner import ToolRunner
from bwctl.models import Test, Endpoint, SchedulingParameters, ClientSettings
from bwctl.utils import get_ip, is_ipv6, timedelta_seconds, discover_source_address
from bwctl.config import get_config
from bwctl.utils import init_logging

def parse_endpoint(endpoint):
    m = re.match("^[(.*)]:(\d+)", endpoint)
    if m:
        return (m.group(1), m.group(2))

    m = re.match("^[(.*)]", endpoint)
    if m:
        return (m.group(1), 4824)

    try:
        if is_ipv6(endpoint):
            return (endpoint, 4824)
    except:
        pass

    m = re.match("^(.*):(\d+)", endpoint)
    if m:
        return (m.group(1), m.group(2))

    return (endpoint, 4824)

def add_traceroute_test_options(oparse):
    oparse.add_option("-F", "--first_ttl", dest="first_ttl", default=0, type="int",
                      help="minimum TTL for traceroute"
                     )
    oparse.add_option("-M", "--max_ttl", dest="max_ttl", default=0, type="int",
                      help="maximum TTL for traceroute"
                     )
    oparse.add_option("-l", "--packet_size", dest="packet_size", default=0, type="int",
                      help="Size of packets (bytes)"
                     )
    oparse.add_option("-t", "--test_duration", dest="test_duration", default=10, type="int",
                      help="Maximum time to wait for traceroute to finish (seconds) (Default: 10)"
                     )

def fill_traceroute_tool_parameters(opts, tool_parameters):
    if opts.first_ttl:
        tool_parameters["first_ttl"] = opts.first_ttl

    if opts.max_ttl:
        tool_parameters["last_ttl"] = opts.max_ttl

    if opts.packet_size:
        tool_parameters["packet_size"] = opts.packet_size

    if opts.test_duration:
        tool_parameters["maximum_duration"] = opts.test_duration

def add_latency_test_options(oparse):
    oparse.add_option("-i", "--packet_interval", dest="packet_interval", default=1.0, type="float",
                      help="Delay between packets (seconds) (Default: 1.0)"
                     )
    oparse.add_option("-l", "--packet_size", dest="packet_size", default=0, type="int",
                      help="Size of packets (bytes)"
                     )
    oparse.add_option("-N", "--num_packets", dest="num_packets", default=10, type="int",
                      help="Number of packets to send (Default: 10)"
                     )
    oparse.add_option("-t", "--ttl", dest="ttl", default=0, type="int",
                      help="TTL for packets"
                     )

def fill_latency_tool_parameters(opts, tool_parameters):
    if opts.num_packets:
        tool_parameters["packet_count"] = opts.num_packets

    if opts.packet_interval:
        tool_parameters["inter_packet_time"] = opts.packet_interval

    if opts.packet_size:
        tool_parameters["packet_size"] = opts.packet_size

    if opts.ttl:
        tool_parameters["packet_ttl"] = opts.ttl


def add_throughput_test_options(oparse):
    oparse.add_option("-t", "--test_duration", dest="test_duration", default=10, type="int",
                      help="Duration for test (seconds) (Default: 10)"
                     )
    oparse.add_option("-b", "--bandwidth", dest="bandwidth", default=0, type="int",
                      help="Bandwidth to use for tests (Mbits/sec) (Default: 1Mb for UDP tests, unlimited for TCP tests)"
                     )
    oparse.add_option("-i", "--report_interval", dest="report_interval", default=2, type="int",
                      help="Reporting interval (seconds) (Default: 2 seconds)"
                     )
    oparse.add_option("-l", "--buffer_length", dest="buffer_length", default=0, type="int",
                      help="Size of read/write buffers (Kb)"
                     )
    oparse.add_option("-O", "--omit", dest="omit", default=0, type="int",
                      help="Omit time. Currently only for iperf3 (seconds)"
                     )
    oparse.add_option("-P", "--parallel", dest="parallel", default=1, type="int",
                      help="Number of concurrent connections"
                     )
    oparse.add_option("-w", "--window_size", dest="window_size", default=0, type="int",
                      help="TCP window size (Kb) (Default: system default)"
                     )
    oparse.add_option("-u", "--udp", dest="udp", action="store_true", default=False,
                      help="Perform a UDP test"
                     )

def fill_throughput_tool_parameters(opts, tool_parameters):
    if opts.test_duration:
        tool_parameters["duration"] = opts.test_duration

    if opts.bandwidth:
        tool_parameters["bandwidth"] = opts.bandwidth

    if opts.report_interval:
        tool_parameters["report_interval"] = opts.report_interval

    if opts.buffer_length:
        tool_parameters["buffer_length"] = opts.buffer_length

    if opts.omit:
        tool_parameters["omit_interval"] = opts.omit

    if opts.parallel:
        tool_parameters["parallel_streams"] = opts.parallel

    if opts.window_size:
        tool_parameters["window_size"] = opts.window_size

    if opts.udp:
        tool_parameters["protocol"] = "udp"

def valid_tool(tool_name, tool_type=None):
    try:
        tool_obj = get_tool(tool_name)
        if tool_type and tool_obj.type != tool_type:
            raise Exception
        return True
    except:
        pass

    return False

def select_tool(sender_tools=[], receiver_tools=[], requested_tools=[], tool_type=None):
    common_tools = []
    for tool in receiver_tools:
        if valid_tool(tool, tool_type=tool_type) and \
           tool in sender_tools:
                common_tools.append(tool)

    for tool in sender_tools:
        if valid_tool(tool, tool_type=tool_type) and \
           tool in receiver_tools and \
           not tool in common_tools:
            common_tools.append(tool)

    for tool in requested_tools:
        if valid_tool(tool, tool_type=tool_type) and \
           tool in sender_tools and \
           tool in receiver_tools:
            return tool, common_tools

    return None, common_tools

def add_tool_options(oparse, tool_type=ToolTypes.UNKNOWN):
    available_tools = []
    for tool in get_tools():
        if tool.type == tool_type:
            available_tools.append(tool.name)

    default_str = ""
    if tool_type == ToolTypes.THROUGHPUT:
        default_str="iperf3,nuttcp,iperf"
    elif tool_type == ToolTypes.LATENCY:
        default_str="ping,owamp"
    elif tool_type == ToolTypes.TRACEROUTE:
        default_str="traceroute,tracepath,paris-traceroute"

    available_tools_str = ", ".join(available_tools)

    oparse.add_option("-T", "--tools", dest="tools", default=default_str,
                      help="The tool to use for the test. Available: %s" % available_tools_str
                     )

def bwctl_client():
    """Entry point for bwctl client"""

    # Determine the type of test we're running
    script_name = inspect.stack()[-1][1]
    if "bwtraceroute" in script_name:
        tool_type = ToolTypes.TRACEROUTE
    elif "bwping" in script_name:
        tool_type = ToolTypes.LATENCY
    elif "bwctl" in script_name:
        tool_type = ToolTypes.THROUGHPUT

    argv = sys.argv
    oparse = optparse.OptionParser()
    oparse.add_option("-4", "--ipv4", action="store_true", dest="require_ipv4", default=False,
                      help="Use IPv4 only")
    oparse.add_option("-6", "--ipv6", action="store_true", dest="require_ipv6", default=False,
                      help="Use IPv6 only")
    oparse.add_option("-L", "--latest_time", dest="latest_time", default=300, type="int",
                      help="Latest time into an interval to allow a test to run (seconds) (Default: 300)")
    oparse.add_option("-c", "--receiver", dest="receiver", type="string",
                      help="The host that will act as the receiving side for a test")
    oparse.add_option("-s", "--sender", dest="sender", type="string",
                      help="The host that will act as the sending side for a test")

    add_tool_options(oparse, tool_type=tool_type)

    if tool_type == ToolTypes.TRACEROUTE:
        add_traceroute_test_options(oparse)
    elif tool_type == ToolTypes.LATENCY:
        add_latency_test_options(oparse)
    elif tool_type == ToolTypes.THROUGHPUT:
        add_throughput_test_options(oparse)

    oparse.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False)

    (opts, args) = oparse.parse_args(args=argv)

    # Initialize the logger
    init_logging(script_name, debug=opts.verbose)

    # Initialize the configuration
    config = get_config() # config_file=config_file)

    # Setup the tool configuration
    configure_tools(config)

    if not opts.receiver and not opts.sender:
        print "Error: a sender or a receiver must be specified\n"
        oparse.print_help()
        sys.exit(1)

    # Setup the endpoint handlers
    endpoints = {}

    if not opts.receiver:
        endpoints['receiver']=LocalEndpoint(is_sender=False, tool_type=tool_type)
    else:
        (receiver_address, receiver_port) = parse_endpoint(opts.receiver)
        if not receiver_address:
            print "Invalid address %s" % opts.receiver
            sys.exit(1)

        receiver_ip = get_ip(receiver_address, require_ipv6=opts.require_ipv6, require_ipv4=opts.require_ipv4)
        if not receiver_ip:
            print "Could not find a suitable address for %s" % receiver_address
            sys.exit(1)

        endpoints['receiver']=ClientEndpoint(
                            address=receiver_ip,
                            port=receiver_port,
                            path="/bwctl",
                            is_sender=False,
                        )

    if not opts.sender:
        endpoints['sender']=LocalEndpoint(is_sender=True, tool_type=tool_type)
    else:
        (sender_address, sender_port) = parse_endpoint(opts.sender)
        if not sender_address:
            print "Invalid address %s" % opts.sender
            sys.exit(1)

        sender_ip = get_ip(sender_address, require_ipv6=opts.require_ipv6, require_ipv4=opts.require_ipv4)
        if not sender_ip:
            print "Could not find a suitable address for %s" % sender_address
            sys.exit(1)

        endpoints['sender']=ClientEndpoint(
                            address=sender_ip,
                            port=sender_port,
                            path="/bwctl",
                            is_sender=True,
                        )

    if not opts.sender:
        endpoints['sender'].initialize(remote_endpoint=endpoints['receiver'])
        endpoints['receiver'].initialize(remote_endpoint=endpoints['sender'])
    elif not opts.receiver:
        endpoints['receiver'].initialize(remote_endpoint=endpoints['sender'])
        endpoints['sender'].initialize(remote_endpoint=endpoints['receiver'])
    else:
        endpoints['sender'].initialize(remote_endpoint=endpoints['receiver'])
        endpoints['receiver'].initialize(remote_endpoint=endpoints['sender'])

    # Have the endpoint objects point at each other
    endpoints['receiver'].remote_endpoint = endpoints['sender']
    endpoints['sender'].remote_endpoint   = endpoints['receiver']

    requested_tools = opts.tools.split(",")

    selected_tool, common_tools = select_tool(requested_tools=requested_tools,
                                              receiver_tools=endpoints['receiver'].available_tools,
                                              sender_tools=endpoints['sender'].available_tools,
                                              tool_type=tool_type)

    if not selected_tool:
        print "Requested tools not available by both servers."
        print "Available tools that support the requested options: %s" % ",".join(common_tools)
        sys.exit(1)

    tool_parameters = {}

    if tool_type == ToolTypes.THROUGHPUT:
        fill_throughput_tool_parameters(opts, tool_parameters)
    elif tool_type == ToolTypes.LATENCY:
        fill_latency_tool_parameters(opts, tool_parameters)
    elif tool_type == ToolTypes.TRACEROUTE:
        fill_traceroute_tool_parameters(opts, tool_parameters)

    requested_time=datetime.datetime.now()+datetime.timedelta(seconds=3)
    latest_time=requested_time+datetime.timedelta(seconds=opts.latest_time)

    reservation_time = requested_time
    reservation_end_time = None
    reservation_completed = False

    while not reservation_completed:
        for endpoint in endpoints.values():
            reservation_time, reservation_end_time = endpoint.request_test(tool=selected_tool,
                                                                           tool_parameters=tool_parameters, 
                                                                           requested_time=reservation_time,
                                                                           latest_time=latest_time)

            if endpoint.remote_endpoint.has_complete_reservation and \
               endpoint.has_complete_reservation and \
               reservation_time == endpoint.remote_endpoint.test_start_time:

               reservation_completed = True
               break

    # We need to accept the remote endpoints first, and then the local one (if
    # applicable) so that the local one can post its' acceptance to the server.
    for endpoint in endpoints.values():
        if endpoint.is_remote:
            endpoint.accept_test()

    for endpoint in endpoints.values():
        if not endpoint.is_remote:
            endpoint.remote_accept_test()

    # Wait for the servers to accept the test
    reservation_confirmed = False
    reservation_failed    = False
    while not reservation_confirmed and not reservation_failed:
        time.sleep(.5)

        reservation_confirmed = True

        for endpoint in endpoints.values():
            if not endpoint.is_pending:
                reservation_confirmed = False

            if endpoint.is_finished:
                reservation_failed = True
                break

    if reservation_confirmed:
        for endpoint in endpoints.values():
            if not endpoint.is_remote:
                endpoint.spawn_tool_runner()

        # Wait until the just after the end of the test for the results to be available
        sleep_time = timedelta_seconds(reservation_end_time - datetime.datetime.now() + datetime.timedelta(seconds=1))

        print "Waiting %s seconds for results" % sleep_time

        time.sleep(sleep_time)

    sender_results = endpoints['sender'].get_test_results()
    receiver_results = endpoints['receiver'].get_test_results()

    print "Sender:"
    if not sender_results:
        print "No test results found"
    else:
        if sender_results.results:
            if "command_line" in sender_results.results:
                print "Command-line: %s" % sender_results.results['command_line']
            print "Results:\n%s" % sender_results.results['output']

        if len(sender_results.bwctl_errors) > 0:
            print "Errors:"
            for error in sender_results.bwctl_errors:
                print "%d) %s" % (error.error_code, error.error_msg)

    print "Receiver:"
    if not receiver_results:
        print "No test results found"
    else:
        if receiver_results.results:
            if "command_line" in receiver_results.results:
                print "Command-line: %s" % receiver_results.results['command_line']
            print "Results:\n%s" % receiver_results.results['output']

        if len(receiver_results.bwctl_errors) > 0:
            print "Errors:"
            for error in receiver_results.bwctl_errors:
                print "%d) %s" % (error.error_code, error.error_msg)

class ClientEndpoint:
   def __init__(self, address="", port=4824, path="/bwctl", is_sender=True):
       self.is_remote = True

       self.remote_endpoint = None

       self.is_sender = is_sender

       self.address = address
       self.test_port = None

       self.port    = int(port)
       self.path    = path
       self.test_id = ""

       self.time_offset      = 0   # difference between the local clock and the far clock
       self.server_ntp_error = 0
       self.server_version   = 2.0
       self.available_tools  = []

       self.server_test_description = None

       self.sent_accept = False

       self.test_start_time = None
       self.test_end_time = None
       client_url = "http://[%s]:%d%s" % (self.address, self.port, self.path)
       self.client = Client(client_url)

   @property
   def has_complete_reservation(self):
       if self.test_start_time == None:
           return False

       if self.server_test_description == None:
           return False

       # Verify that the test ports have been passed around
       if self.is_sender and self.remote_endpoint.test_port and \
           self.server_test_description.receiver_endpoint.test_port != self.remote_endpoint.test_port:
           return False

       if not self.is_sender and self.test_port and \
           self.server_test_description.sender_endpoint.test_port != self.test_port:
           return False

       # Verify that the test ID has been passed around
       if self.server_test_description.sender_endpoint.posts_endpoint_status == False and \
          not self.server_test_description.sender_endpoint.test_id:
           return False

       if self.server_test_description.receiver_endpoint.posts_endpoint_status == False and \
          not self.server_test_description.receiver_endpoint.test_id:
           return False

       return True

   def initialize(self, remote_endpoint):
       # XXX: handle failure condition
       status = self.client.get_status()
       current_time = datetime.datetime.now()

       # XXX: we should probably try to account for the network delay
       self.time_offset = timedelta_seconds(current_time - status.time)

       self.protocol = status.protocol
       self.server_ntp_error = status.ntp_error
       self.server_version   = status.version
       self.available_tools = status.available_tools

       self.remote_endpoint = remote_endpoint

   def time_c2s(self, time):
       return time - datetime.timedelta(seconds=self.time_offset)

   def time_s2c(self, time):
       return time + datetime.timedelta(seconds=self.time_offset)

   def request_test(self, requested_time=None, latest_time=None, tool="", tool_parameters={}):
       # Convert our time to the time that the server expects
       if requested_time:
           requested_time = self.time_c2s(requested_time)

       if latest_time:
           latest_time    = self.time_c2s(latest_time)

       test = self.server_test_description
       if test == None:
           if self.is_sender:
               receiver_endpoint = self.remote_endpoint.endpoint_obj(local=False)
               sender_endpoint = self.endpoint_obj(local=True)
           else:
               sender_endpoint = self.remote_endpoint.endpoint_obj(local=False)
               receiver_endpoint = self.endpoint_obj(local=True)

           test = Test(
                        client=ClientSettings(time=datetime.datetime.now()),
                        sender_endpoint=sender_endpoint,
                        receiver_endpoint=receiver_endpoint,
                        tool=tool,
                        tool_parameters=tool_parameters,
                        scheduling_parameters=SchedulingParameters(requested_time=requested_time, latest_acceptable_time=latest_time)
                      )

       if tool:
           test.tool = tool

       if tool_parameters:
           test.tool_parameters = tool_parameters

       if requested_time:
           test.scheduling_parameters.requested_time = requested_time

       if latest_time:
           test.scheduling_parameters.latest_acceptable_time = latest_time

       if self.is_sender:
           test.receiver_endpoint = self.remote_endpoint.endpoint_obj(local=False)
           test.sender_endpoint   = self.endpoint_obj(local=True)
       else:
           test.sender_endpoint = self.remote_endpoint.endpoint_obj(local=False)
           test.receiver_endpoint   = self.endpoint_obj(local=True)

       # XXX: handle failure
       if self.test_id:
           print "Updating test: %s" % self.test_id
           ret_test = self.client.update_test(self.test_id, test)
       else:
           print "Requesting new test"
           ret_test = self.client.request_test(test)

       # Save the test id since we use it for creating the Endpoint, and a few
       # other things.
       self.test_id = ret_test.id

       # Save the test port since we use it for creating our Endpoint
       # representation
       if self.is_sender:
           self.test_port = ret_test.sender_endpoint.test_port
       else:
           self.test_port = ret_test.receiver_endpoint.test_port

       self.test_start_time = self.time_s2c(ret_test.scheduling_parameters.test_start_time)
       self.test_end_time = self.time_s2c(ret_test.scheduling_parameters.reservation_end_time)

       self.server_test_description = ret_test

       print "Setting remote start time to %s" % self.test_start_time
       print "Setting remote end time to %s" % self.test_end_time

       return self.test_start_time, self.test_end_time

   def get_test(self):
       # XXX: handle failure
       return self.client.get_test(self.test_id)

   def get_test_results(self):
       # XXX: handle failure
       retval = None
       try:
           retval = self.client.get_test_results(self.test_id)
       except HTTPError:
           retval = None

       return retval

   @property
   def is_pending(self):
       test = self.get_test()

       return test.status == "pending"

   @property
   def is_finished(self):
       test = self.get_test()

       return test.finished

   def accept_test(self):
       # XXX: handle failure
       if self.sent_accept:
           return

       self.sent_accept = True

       return self.client.accept_test(self.test_id)

   def cancel_test(self):
       # XXX: handle failure

       return self.client.cancel_test(self.test_id)

   def endpoint_obj(self, local=False):
    return Endpoint(
                    address=self.address,
                    test_port=self.test_port,

                    bwctl_protocol=2.0,
                    peer_port=self.port,
                    base_path=self.path,
                    test_id=self.test_id,

                    local=local,

                    ntp_error=self.server_ntp_error,
                    client_time_offset=self.time_offset,

                    legacy_client_endpoint=False,
                    posts_endpoint_status=False
                    )

class LocalEndpoint:
   def __init__(self, tool_type=None, is_sender=True):
       self.is_remote = False

       self.address = None

       self.test_start_time = None
       self.test_end_time = None

       self.tool_type = tool_type
       self.is_sender = is_sender
       self.tool_runner_proc = None

       self.test_port = None

       self.tool = ""
       self.tool_parameters = {}

       self.available_tools = []

       self.remote_endpoint = None

       self.results_queue = Queue()

       self.results = None

   def initialize(self, remote_endpoint):
       self.remote_endpoint = remote_endpoint

       self.address = discover_source_address(remote_endpoint.address)
       if not self.address:
           raise Exception("Error: couldn't figure out which address to use to connect to %s" % remote_endpoint.address)

       self.available_tools = get_available_tools()

   @property
   def has_complete_reservation(self):
       return True

   def request_test(self, requested_time=None, latest_time=None, tool="", tool_parameters={}):
       if not self.test_port:
           self.test_port = get_tool(tool).port_range.get_port()

       if self.is_sender:
           receiver_endpoint = self.remote_endpoint.endpoint_obj(local=False)
           sender_endpoint = self.endpoint_obj(local=True)
       else:
           sender_endpoint = self.remote_endpoint.endpoint_obj(local=False)
           receiver_endpoint = self.endpoint_obj(local=True)

       self.test = Test(
                        id="local test",
                        client=ClientSettings(time=datetime.datetime.now()),
                        sender_endpoint=sender_endpoint,
                        receiver_endpoint=receiver_endpoint,
                        tool=tool,
                        tool_parameters=tool_parameters,
                        scheduling_parameters=SchedulingParameters(
                            requested_time=requested_time,
                            latest_acceptable_time=latest_time,
                        )
                      )

       # Just grab the other time's reservation end time if it's already been
       # scheduled.
       if self.remote_endpoint and \
           requested_time == self.remote_endpoint.test_start_time:
           end_time = self.remote_endpoint.test_end_time
       else:
           end_time = requested_time + datetime.timedelta(seconds=self.test.duration + 1)

       self.tool = tool
       self.tool_parameters = tool_parameters

       self.test_start_time = requested_time
       self.test_end_time = end_time

       # Fill-in the scheduling parameters
       self.test.scheduling_parameters.reservation_start_time = requested_time - datetime.timedelta(seconds=0.5) # Makes sure the server starts slightly early
       self.test.scheduling_parameters.test_start_time = requested_time
       self.test.scheduling_parameters.reservation_end_time = end_time

       print "Setting start time to %s" % requested_time
       print "Setting end time to %s" % end_time

       return requested_time, end_time

   def get_test_results(self):
       if not self.results:
           try:
               self.results = self.results_queue.get_nowait()
           except:
               pass

       return self.results

   @property
   def is_pending(self):
       return True

   @property
   def is_finished(self):
       return not self.results

   def remote_accept_test(self):
       client_url = "http://[%s]:%d%s" % (self.remote_endpoint.address, self.remote_endpoint.port, self.remote_endpoint.path)
       self.client = Client(client_url)

       return self.client.remote_accept_test(self.remote_endpoint.test_id, self.test)

   def cancel_test(self):
       if self.tool_runner_proc:
            self.tool_runner_proc.kill_children()
            self.tool_runner_proc.terminate()

       return

   def spawn_tool_runner(self):
       def handle_results_cb(results):
           self.results_queue.put(results)

       self.tool_runner_proc = ToolRunner(test=self.test, results_cb=handle_results_cb)
       self.tool_runner_proc.start()

   def endpoint_obj(self, local=False):
    return Endpoint(
                    address=self.address,
                    test_port=self.test_port,

                    local=local,

                    ntp_error=0, # XXX; figure this out

                    client_time_offset=0,

                    legacy_client_endpoint=False,
                    posts_endpoint_status=True
                    )
