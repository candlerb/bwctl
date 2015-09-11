'''
Created on 12.02.2015

@author: Hakan Calim <Hakan.Calim@fau.de>
'''

import re

from bwctl.server.limits import Limit, LimitsDB, ListLimit
from bwctl.exceptions import ValidationException

# AB: Long term, the V1 format is going away. I think it'd make more sense to
# completely separate the V1 and V2 parsing even if there are some happenstance
# similarities in the formats. 
class LimitsParser(object):
    '''
    Main class
    '''
    def __init__(self, limits_file_path):
        self.pattern_get_assigns = 'assign.*\n'
        self.limits_as_string = ""                
        self.limits_classes = {}
        self.open_limits_file(limits_file_path)        
        
    def open_limits_file(self, limits_file=None):
        try:
            limit_file_object = open(limits_file, 'r')
            self.limits_as_string = limit_file_object.read()
            #Remove double quotes code from unicode
            self.limits_as_string = re.sub('\xe2\x80\x9d','"',self.limits_as_string)
            self.limits_as_string = re.sub('\xe2\x80\x9c','"',self.limits_as_string)
            limit_file_object.close()
        except IOError as e:
            print "Cannot open limits file: " + limits_file
            raise

    def parse(self):
        self.parse_limits()
        self.parse_assign()
    
    def parse_assign(self):
        assigns = re.findall(self.pattern_get_assigns, self.limits_as_string)
        self.assign_counter = len(assigns)
        for assign in assigns:
            match = re.search(r'assign\s+(\w+)\s+(\S+)\s*(\S*)\s*', assign, re.DOTALL)            
            if match:
                elements = match.groups()
                parent = elements[2] if elements[2] != '' else elements[1]
                assign_type = elements[0]
                assign_value = elements[1] if elements[2] != '' else ""
                parent = parent.replace('"', '')
                if parent in self.limits_classes: #found class
                    if not assign_type in self.limits_classes[parent]['ASSIGN']: # check if assign type exist
                        self.limits_classes[parent]['ASSIGN'] = { assign_type : [assign_value] } # Make new  assign entry
                    else:
                        self.limits_classes[parent]['ASSIGN'][assign_type].append(assign_value)
                    self.assign_counter = self.assign_counter + 1
                else:
                    raise Exception("Class name: %s not exist. Please check your limits file." % parent)
    
    def get_value_by_pattern(self, pattern,string):
        match = re.search(pattern, string)
        if match:
            return match.group(1)
        else:
            return None
    def get_limits_classes(self):
        '''
        Returns the limit file as a python dict after parsing.
        The structure is as follow:
        dict{CLASSNAME}
                    {LIMITTYPES] include all limittypes as list
                    {ASSIGN} include all assign types. Each type has his values as list
                    {PARENT} if class name is parent it includes None otherwise it includes: parent=CLASSNAME
        '''
        return self.limits_classes
        

class LimitsFileParser(LimitsParser):
    '''
    This class parsers limits files built on version 2 syntaxt. The limits file has the form like example below:
    <class "root_users">
    # No parent class

    # Applies to all tests
    <default_limits>
        duration     60
        bandwidth    100M
    </default_limits>

    # Applies to all throughput tests (i.e. iperf, iperf3, nuttcp), overriding
    # the defaults. Note: unlike in the previous syntax, you can go above the
    # defaults.
    <limits "throughput">
        duration      30
        bandwidth     10G
        allow_udp     1
    </limits>

    # Applies to all latency tests (i.e. ping and owamp).
    <limits "latency">
        # Only permit latency tests of 100 pps or less
        packets_per_second      100
    </limits>
    </class>
    The file can have more class entries. If given string has similar definition like above this class will parse the string to a pytho dict data structure.
    '''
    def __init__(self, limits_file_path):
        self.pattern_limit_type_value = '[\w+.:]+'
        #self.pattern_get_limits = r'<class \S+>.*\s*(?:parent.*){0,1}\s*.*(?:<.*limits.*>(?:\s*\w*\s*(?:\w+(?:\.\w){0,3}){1}\s*){0,}.*\s*</.*limits>\s*){1,}</class>'
        self.pattern_get_limits = r'<class \S+>.*\s*(?:parent.*){0,1}\s*.*(?:<.*limits.*>(?:\s*\w*\s*%s\s*){0,}.*\s*</.*limits>\s*){1,}</class>' % self.pattern_limit_type_value

        super(LimitsFileParser, self).__init__(limits_file_path)
          
    def parse_limits(self):
        self.limits_as_string = re.sub('#.*\\n',"",self.limits_as_string) #remove all comments first
        limits = re.findall(self.pattern_get_limits, self.limits_as_string, re.M)
        if len(limits) < 1:
            raise Exception("No Limits defined in format 2.x ")
         
        for limit in limits:
            class_name = self.get_class_names(limit)
            parent = self.get_class_parent(limit)
            if class_name:
                all_sub_limits = re.findall(r'<.*limits.*>(?:\s*\w+\s*%s\s*){0,}.*\s*</.*limits>' % self.pattern_limit_type_value, limit,re.M)
                self.limits_classes[class_name] = {}
                self.limits_classes[class_name]['PARENT'] = parent
                self.limits_classes[class_name]['LIMITTYPES'] = {}
                self.limits_classes[class_name]['ASSIGN'] = {}
                self.limits_classes[class_name]['LIMITTYPES'] = self.get_limits_types(all_sub_limits)
        
        
    
    def get_class_names(self, limit):
        class_name = self.get_value_by_pattern(r'<class (\S+)>', limit)
        return class_name.replace('"','') if class_name else class_name
    def get_class_parent(self, limit):
        return self.get_value_by_pattern(r'parent.* \"(\w+)\".*\s*', limit)
    def get_limits_types(self, sub_limits):
        limits = {}
        for sub_limit in sub_limits:
            limit_id = self.get_limit_id(sub_limit)
            limits[limit_id] = {}
            #match = re.match(r'<.*limits.*>(?:\s*(\w+)\s*(%s)\s*){1,100}.*\s*</.*limits>' % self.pattern_limit_type_value,sub_limit,re.M)
            match = re.match(r'<.*limits.*>((?:\s*\w+\s*%s\s*){0,}.*\s*)</.*limits>' % self.pattern_limit_type_value,sub_limit,re.M)
            if match:
                all_limittypes = re.findall('\w+\s+%s' % self.pattern_limit_type_value,match.group(1),re.M)
                for limit_type in all_limittypes:
                    match = re.match(r'(\w+)\s+(%s)' % self.pattern_limit_type_value,limit_type)
                    type,value = match.group(1),match.group(2)
                    if type in ListLimit.types:
                        if type not in  limits[limit_id]:
                             limits[limit_id][type] = list([value])
                        else:
                             limits[limit_id][type].append(value)
                    else:     
                        limits[limit_id][type] = value

        return limits
                    
    def get_limit_id(self,limit_str):
        limit_id = self.get_default_limit_name(limit_str)        
        if limit_id:
            return limit_id
        else:
            return self.get_limit_name(limit_str)
    def get_default_limit_name(self,limit_str):
        return self.get_value_by_pattern('(default)', limit_str)

    def get_limit_name(self,limit_str):
        return self.get_value_by_pattern('limits "(\w+)"', limit_str)
        
        

                    


# AB: Could the parser be integrated into the LimitsDB file as a static method
# that returns a LimitsDB?
#  e.g.
#
#  @staticmethod
#  def parse_file(cls, file_path):
#     parse the files into a LimitsDB object
#     return creates LimitsDB file
class LimitsDBfromFileCreator(object):
    '''
    This class creates a limits DB from the dict which is created with the limits file parser class. 
    It takes a LimitsFileParser class as a argument:
    It returns a LimitDB which is used by server.
    '''
    def __init__(self, limits_file_path):
        self.limits_db = LimitsDB()
        self.limits_file_path = limits_file_path
        self.limits_classes = {}
    def get_limitsdb(self):
        '''
        Creaes from limits file an limits db data structure.
        '''
	# AB: I'm not sure it makes sense to support the v1 parsing as anything
	# more than an upgrade script, so it may make more sense to axe the v1
	# parsing in here, and only support creating a limits db from v2. We'd
	# include an "upgrade_limits.py" script that would convert the v1
	# limits into a v2 limits file.
        
        lfp = LimitsFileParser(self.limits_file_path)
        lfp.parse()
                
        self.limits_classes = lfp.get_limits_classes()
        self.create_limitsdb()
        return self.limits_db

    def create_limitsdb(self):
        for class_name in self.limits_classes:
            self.create_class(class_name)

            # Add all the elements to the class
            self.add_all_class_elements(self.limits_classes, class_name)

    def create_class(self, class_name):
	# Things can get redundant depending on ordering that the classes get
	# added.
        if self.limits_db.get_limit_class_by_name(class_name):
            return

        # Make sure the parent class exists first
        parentname = self.limits_classes[class_name]['PARENT']
        if parentname:
            if not self.limits_db.get_limit_class_by_name(parentname):
                self.create_class(parentname)

        # Actually create this class
        try:
            self.limits_db.create_limit_class(class_name, parent=parentname)
        except Exception as e:
            raise ValidationException("Problem adding class %s: %s" % (class_name, e))

    def add_all_class_elements(self, limits_classes, class_name):
        limit_types = limits_classes[class_name]['LIMITTYPES']
        self.add_limits_types_to_limitsdb(class_name, limit_types)
        for assign_type, value in limits_classes[class_name]['ASSIGN'].items():
            if assign_type == 'network':
                self.add_class_network(class_name, value)
            elif assign_type == 'user':
                self.add_class_user(class_name, value)
            elif assign_type == 'default':
                self.add_class_default(class_name)
            elif assign_type == 'loopback':
                self.add_class_loopback(class_name)
            else:
                raise ValidationException("Unknown assignment type: %s" % assign_type)
        
    def add_limits_types_to_limitsdb(self, class_name, limits):
        for limit_tool in limits:
            limit_type_class = None
            limit_types = limits[limit_tool]
            for limit_type_name in limit_types:
                limit_type_value = limits[limit_tool][limit_type_name]
		# AB: I added a few more limit objects that aren't handled
		# here. It'd probably be good to generalize the limit creation
		# using the the 'type' class attribute should handle the below.
		# I don't see a situation where we'll have a difference between
		# the name of a limit in the v1 parsing and the v2 parsing.
		# However, it might make sense to have the parsers themselves
		# create these limit objects instead of generalizing it.
                for limit_class in Limit.get_subclasses():
                    if limit_class.type and limit_type_name == limit_class.type:
                        limit_type_class = limit_class(limit_type_value)
                        break

                if limit_type_class:
                    self.limits_db.add_limit(class_name, limit_type_class, limit_tool)
                else:
                    raise ValidationException("This limit type is not supported in v2: %s" % limit_type_name)

    # AB: We'll need an add_class_user option as well
    def add_class_network(self, class_name, networks):
        for network in networks:
            self.limits_db.add_network(network, class_name)
    def add_class_user(self, class_name, users):
        for user in users:
            self.limits_db.add_user(user, class_name)
    def add_class_default(self, class_name):
        self.limits_db.set_default_limit_class(class_name)
    def add_class_loopback(self, class_name):
        self.limits_db.set_loopback_limit_class(class_name)

    def get_limits_classes(self):
        return  self.limits_db.get_limits()
    


              

             

                 
        